from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / ".bootstrap"
GROUPS = [
    ("Add persistence and database migrations", ["group1.tar.gz"]),
    ("Implement analytics providers and recommendation services", ["group2.part00", "group2.part01", "group2.part02"]),
    ("Build Persian Streamlit and Docker deployment", ["group3.part00", "group3.part01"]),
    ("Add comprehensive application tests", ["group4.part00", "group4.part01"]),
    ("Expand documentation and continuous integration", ["group5.part00", "group5.part01"]),
]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

for index, (message, parts) in enumerate(GROUPS, start=1):
    archive = BOOTSTRAP / f"assembled-{index}.tar.gz"
    with archive.open("wb") as output:
        for part in parts:
            output.write((BOOTSTRAP / part).read_bytes())
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
run("git", "push", "origin", "HEAD:agent/deployable-irma-v1")
