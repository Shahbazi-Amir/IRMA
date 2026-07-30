from __future__ import annotations

import base64
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / ".bootstrap"
GROUPS = [
    ("Add persistence and database migrations", "group1", 0),
    ("Implement analytics providers and recommendation services", "group2", 12),
    ("Build Persian Streamlit and Docker deployment", "group3", 0),
    ("Add comprehensive application tests", "group4", 5),
    ("Expand documentation and continuous integration", "group5", 6),
]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def archive_bytes(name: str, part_count: int) -> bytes:
    if part_count == 0:
        return (BOOTSTRAP / f"{name}.tar.gz").read_bytes()
    encoded = "".join(
        (BOOTSTRAP / name / f"part-{index:02d}.b64").read_text()
        for index in range(part_count)
    )
    return base64.b64decode(encoded, validate=True)


run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

for index, (message, name, part_count) in enumerate(GROUPS, start=1):
    archive = BOOTSTRAP / f"assembled-{index}.tar.gz"
    archive.write_bytes(archive_bytes(name, part_count))
    with tarfile.open(archive, "r:gz") as payload:
        payload.extractall(ROOT, filter="data")
    archive.unlink()
    run("git", "add", "-A")
    run("git", "commit", "-m", message)

shutil.rmtree(BOOTSTRAP)
Path(__file__).unlink()
(ROOT / ".github" / "workflows" / "bootstrap.yml").unlink()
run("git", "add", "-A")
run("git", "commit", "-m", "Remove temporary bootstrap workflow")
run("git", "push", "--force", "origin", "HEAD:agent/deployable-irma-v1")
