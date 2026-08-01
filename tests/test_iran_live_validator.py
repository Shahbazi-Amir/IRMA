from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "iran_live_validator.py"
SPEC = importlib.util.spec_from_file_location("iran_live_validator", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def result(code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.mark.parametrize("value", ["nope", "1.2.3.999", "github.com", ""])
def test_invalid_ip(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        validator.validate_ip(value)


def test_valid_ip() -> None:
    assert validator.validate_ip("192.0.2.1") == "192.0.2.1"
    assert validator.validate_ip("2001:db8::1") == "2001:db8::1"


def test_username_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = iter([result(255), result(255), result(0, "IRMA_SSH_OK")])
    monkeypatch.setattr(validator, "run", lambda *args, **kwargs: next(attempts))
    host = validator.discover_ssh("192.0.2.1", ("root", "ubuntu", "debian"))
    assert host.user == "debian"


@pytest.mark.parametrize("failure", ["timeout", "key rejected"])
def test_ssh_failure_is_classified(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    monkeypatch.setattr(validator, "run", lambda *args, **kwargs: result(255, stderr=failure))
    with pytest.raises(validator.ValidatorError, match="No usable SSH key") as exc:
        validator.discover_ssh("192.0.2.1", ("root",))
    assert exc.value.status == "ssh_auth_required"


@pytest.mark.parametrize(
    ("release", "arch", "expected"),
    [
        ('ID=ubuntu\nVERSION_ID="22.04"', "x86_64", "ubuntu"),
        ('ID=ubuntu\nVERSION_ID="24.04"', "amd64", "ubuntu"),
        ('ID=debian\nVERSION_ID="12"', "x86_64", "debian"),
    ],
)
def test_supported_os(release: str, arch: str, expected: str) -> None:
    assert validator.parse_os_release(release, arch)["id"] == expected


@pytest.mark.parametrize(
    ("release", "arch"),
    [("ID=centos\nVERSION_ID=9", "x86_64"), ("ID=ubuntu\nVERSION_ID=24.04", "aarch64")],
)
def test_unsupported_os(release: str, arch: str) -> None:
    with pytest.raises(validator.ValidatorError) as exc:
        validator.parse_os_release(release, arch)
    assert exc.value.status == "unsupported_os"


def test_secret_redaction() -> None:
    text = "password=hunter2 token: abc postgresql+psycopg://irma:secret@127.0.0.1/db"
    redacted = validator.redact(text)
    assert "hunter2" not in redacted
    assert "secret" not in redacted


def test_idempotency_success_and_failure() -> None:
    first = {"fund_count": 4, "history_count": 2, "metric_count": 1, "source_count": 1}
    assert validator.compare_counts(first, dict(first))["status"] == "success"
    second = dict(first, history_count=4)
    report = validator.compare_counts(first, second)
    assert report == {"status": "failed", "differences": {"history_count": [2, 4]}}


@pytest.mark.parametrize(
    ("status", "content_type", "valid_json", "classification"),
    [
        (502, "text/html", False, "html_502"),
        (200, "application/json", False, "invalid_json"),
        (200, "application/json", True, "reachable"),
        (None, "", False, "unreachable"),
        (503, "text/plain", False, "http_error"),
    ],
)
def test_diagnostic_classification(
    status: int | None, content_type: str, valid_json: bool, classification: str
) -> None:
    assert validator.classify_diagnostic(status, content_type, valid_json) == classification


def test_upload_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(validator, "run", lambda *args, **kwargs: result(1, stderr="network"))
    with pytest.raises(validator.ValidatorError) as exc:
        validator.upload(validator.Host("192.0.2.1", "root"), tmp_path / "source", "/tmp/source")
    assert exc.value.status == "source_upload_failed"


def test_structured_auth_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = validator.ValidatorError("ssh_auth_required", "No usable SSH key was found.")
    monkeypatch.setattr(validator, "discover_ssh", lambda server: (_ for _ in ()).throw(error))
    assert validator.main(["--server", "192.0.2.1"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ssh_auth_required"


def test_remote_script_covers_deployment_and_failure_modes() -> None:
    script = (SCRIPT.parent / "iran_live_validator_remote.sh").read_text()
    for expected in (
        "dependency_install_failed",
        "bootstrap_first_failed",
        "bootstrap_second_failed",
        "fipiran-12181-validation.json",
        "iran-network-diagnostics.json",
        "postgresql",
        "fixture_used",
    ):
        assert expected in script


def test_clone_and_github_independent_upload_modes_exist() -> None:
    script = (SCRIPT.parent / "iran_live_validator_remote.sh").read_text()
    assert "/tmp/irma-source.tar.gz" in script
    assert "git clone" in script
    assert "IRMA_DEPLOYMENT_MODE" in script
