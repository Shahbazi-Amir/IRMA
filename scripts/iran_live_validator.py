#!/usr/bin/env python3
"""Provision and run IRMA live validation on a trusted SSH host in Iran."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/opt/irma-validator"
REMOTE_STATE = "/var/lib/irma-validator"
REMOTE_ARTIFACTS = "/tmp/irma-validator-artifacts"
USERS = ("root", "ubuntu", "debian", "admin", "linux")
SSH_OPTIONS = (
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "LogLevel=ERROR",
)
SECRET_ASSIGNMENT = re.compile(r"(?i)(password|token|authorization)\s*[=:]\s*\S+")
DATABASE_CREDENTIALS = re.compile(r"(postgresql(?:\+psycopg)?://)[^\s@]+@")


class ValidatorError(RuntimeError):
    """A classified controller failure."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Host:
    server: str
    user: str
    port: int = 22


def validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("server must be a valid IPv4 or IPv6 address") from exc


def redact(text: str) -> str:
    text = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return DATABASE_CREDENTIALS.sub(r"\1[REDACTED]@", text)


def server_fingerprint(server: str) -> str:
    return f"sha256:{hashlib.sha256(server.encode()).hexdigest()[:16]}"


def run(
    command: Sequence[str], *, check: bool = True, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command), input=input_text, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        detail = redact((result.stderr or result.stdout).strip())
        raise ValidatorError("command_failed", detail or f"command exited {result.returncode}")
    return result


def ssh_command(host: Host, remote_command: str) -> list[str]:
    return ["ssh", *SSH_OPTIONS, "-p", str(host.port), f"{host.user}@{host.server}", remote_command]


def discover_ssh(server: str, users: Sequence[str] = USERS, port: int = 22) -> Host:
    for user in users:
        candidate = Host(server, user, port)
        result = run(ssh_command(candidate, "printf IRMA_SSH_OK"), check=False)
        if result.returncode == 0 and result.stdout == "IRMA_SSH_OK":
            return candidate
    raise ValidatorError("ssh_auth_required", "No usable SSH key was found.")


def parse_os_release(text: str, architecture: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    os_id, version = values.get("ID", ""), values.get("VERSION_ID", "")
    if architecture not in {"x86_64", "amd64"}:
        raise ValidatorError("unsupported_os", f"unsupported architecture: {architecture}")
    if (os_id, version) not in {("ubuntu", "22.04"), ("ubuntu", "24.04"), ("debian", "12")}:
        raise ValidatorError("unsupported_os", f"unsupported operating system: {os_id} {version}")
    return {"id": os_id, "version": version, "architecture": architecture}


def inspect_host(host: Host) -> dict[str, str]:
    result = run(ssh_command(host, "cat /etc/os-release; printf '\\nIRMA_ARCH='; uname -m"))
    release, architecture = result.stdout.rsplit("IRMA_ARCH=", 1)
    return parse_os_release(release, architecture.strip())


def source_sha(ref: str) -> str:
    result = run(["git", "rev-parse", f"{ref}^{{commit}}"], check=False)
    if result.returncode:
        fetched = run(["git", "fetch", "--no-tags", "origin", ref], check=False)
        if fetched.returncode:
            raise ValidatorError("invalid_ref", f"could not resolve Git ref: {ref}")
        result = run(["git", "rev-parse", "FETCH_HEAD^{commit}"])
    return result.stdout.strip()


def create_source_bundle(ref: str, destination: Path) -> str:
    sha = source_sha(ref)
    raw_tar = destination.with_suffix(".tar")
    run(["git", "archive", "--format=tar", "-o", str(raw_tar), sha], check=True)
    with tarfile.open(raw_tar) as source, tarfile.open(destination, "w:gz") as target:
        for member in source.getmembers():
            fileobj = source.extractfile(member) if member.isfile() else None
            target.addfile(member, fileobj)
    raw_tar.unlink()
    return sha


def compare_counts(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    keys = ("fund_count", "history_count", "metric_count", "source_count")
    differences = {
        key: [first.get(key), second.get(key)] for key in keys if first.get(key) != second.get(key)
    }
    return {"status": "success" if not differences else "failed", "differences": differences}


def classify_diagnostic(status: int | None, content_type: str, valid_json: bool) -> str:
    if status == 502:
        return "html_502" if "html" in content_type else "upstream_502"
    if status is None:
        return "tcp_failure"
    if status >= 400:
        return "http_error"
    if "json" in content_type and not valid_json:
        return "invalid_json"
    return "reachable"


def write_error(status: str, server: str, message: str) -> None:
    safe = redact(message).replace(server, server_fingerprint(server))
    print(
        json.dumps(
            {"status": status, "server": server_fingerprint(server), "message": safe},
            ensure_ascii=False,
        )
    )


def _public_key_info(path: Path) -> dict[str, str] | None:
    result = run(["ssh-keygen", "-lf", str(path)], check=False)
    if result.returncode:
        return None
    fields = result.stdout.split()
    if len(fields) < 4:
        return None
    key = path.read_text().strip()
    if not key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")):
        return None
    return {"type": key.split()[0], "path": str(path), "fingerprint": fields[1], "public_key": key}


def public_keys(ssh_dir: Path | None = None) -> list[dict[str, str]]:
    root = ssh_dir or Path.home() / ".ssh"
    candidates = [root / "id_ed25519.pub", root / "id_ecdsa.pub", root / "id_rsa.pub"]
    return [info for path in candidates if path.is_file() and (info := _public_key_info(path))]


def doctor(ref: str, artifacts: Path) -> dict[str, Any]:
    commands = {
        name: shutil.which(name) is not None for name in ("git", "ssh", "scp", "rsync", "tar")
    }
    repo = run(["git", "rev-parse", "--show-toplevel"], check=False)
    origin = (
        run(["git", "remote", "get-url", "origin"], check=False)
        if repo.returncode == 0
        else result_placeholder()
    )
    ref_ok = True
    ref_error = None
    try:
        resolved = source_sha(ref)
    except ValidatorError as exc:
        ref_ok, resolved, ref_error = False, None, str(exc)
    artifacts.mkdir(parents=True, exist_ok=True)
    writable = os.access(artifacts, os.W_OK)
    keys = public_keys()
    agent = bool(os.environ.get("SSH_AUTH_SOCK"))
    ready = (
        all(commands.values())
        and repo.returncode == 0
        and origin.returncode == 0
        and ref_ok
        and writable
        and bool(keys or agent)
    )
    return {
        "status": "ready" if ready else "not_ready",
        "python": sys.version.split()[0],
        **commands,
        "repository": repo.returncode == 0,
        "origin": origin.returncode == 0,
        "target_ref": ref,
        "target_sha": resolved,
        "ref_error": ref_error,
        "ssh_agent": agent,
        "public_keys": [{k: v for k, v in item.items() if k != "public_key"} for item in keys],
        "artifact_directory_writable": writable,
    }


def result_placeholder() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 1, "", "")


def upload(host: Host, local: Path, remote: str) -> None:
    result = run(
        [
            "scp",
            *SSH_OPTIONS,
            "-P",
            str(host.port),
            str(local),
            f"{host.user}@{host.server}:{remote}",
        ],
        check=False,
    )
    if result.returncode:
        raise ValidatorError("source_upload_failed", redact(result.stderr.strip()))


def retrieve(host: Host, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            "scp",
            *SSH_OPTIONS,
            "-P",
            str(host.port),
            "-r",
            f"{host.user}@{host.server}:{REMOTE_ARTIFACTS}/.",
            str(destination),
        ],
        check=False,
    )
    if result.returncode:
        raise ValidatorError("artifact_retrieval_failed", redact(result.stderr.strip()))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=validate_ip)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--show-public-key", action="store_true")
    parser.add_argument("--ssh-user")
    parser.add_argument("--ssh-port", type=int, default=22)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--provision-only", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--deployment-mode", choices=("auto", "upload", "clone"), default="auto")
    parser.add_argument(
        "--artifacts", type=Path, default=ROOT / "artifacts" / "iran-live-validation"
    )
    args = parser.parse_args(argv)
    if args.doctor:
        print(json.dumps(doctor(args.ref, args.artifacts), indent=2))
        return 0
    if args.show_public_key:
        keys = public_keys()
        print(
            json.dumps(
                {"status": "success", **keys[0]} if keys else {"status": "ssh_public_key_missing"},
                indent=2,
            )
        )
        return 0 if keys else 1
    if not args.server:
        parser.error("--server is required for remote modes")
    try:
        host = (
            Host(args.server, args.ssh_user, args.ssh_port)
            if args.ssh_user
            else discover_ssh(args.server, port=args.ssh_port)
        )
        os_info = inspect_host(host)
        with tempfile.TemporaryDirectory(prefix="irma-validator-") as temporary:
            temporary_path = Path(temporary)
            remote_script = ROOT / "scripts" / "iran_live_validator_remote.sh"
            upload(host, remote_script, "/tmp/irma-live-validator-remote.sh")
            action = (
                "preflight"
                if args.preflight
                else "provision"
                if args.provision_only
                else "validate"
            )
            sha = ""
            deployment_mode = "upload" if args.deployment_mode == "auto" else args.deployment_mode
            if action == "validate" and deployment_mode == "upload":
                bundle = temporary_path / "source.tar.gz"
                sha = create_source_bundle(args.ref, bundle)
                upload(host, bundle, "/tmp/irma-source.tar.gz")
            elif action == "validate":
                sha = source_sha(args.ref)
            env = {
                "IRMA_ACTION": action,
                "IRMA_SERVER_HASH": server_fingerprint(args.server).removeprefix("sha256:"),
                "IRMA_TARGET_REF": args.ref,
                "IRMA_TARGET_SHA": sha,
                "IRMA_CLEANUP": "1" if args.cleanup else "0",
                "IRMA_DEPLOYMENT_MODE": deployment_mode,
            }
            prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())
            remote = f"{prefix} bash /tmp/irma-live-validator-remote.sh"
            result = run(ssh_command(host, remote), check=False)
            if action != "provision":
                retrieve(host, args.artifacts)
            if result.stdout:
                print(redact(result.stdout), end="")
            if result.returncode:
                raise ValidatorError("remote_validation_failed", redact(result.stderr.strip()))
        print(json.dumps({"status": "success", "os": os_info, "artifacts": str(args.artifacts)}))
        return 0
    except ValidatorError as exc:
        write_error(exc.status, args.server, str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
