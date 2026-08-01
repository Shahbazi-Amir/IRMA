# Iran-hosted live validation

## Architecture

IRMA uses a trusted controller to connect over SSH to an ephemeral validation environment on an
Iran-hosted VPS. The VPS reaches FIPIRAN directly and returns JSON artifacts over SCP. It never
receives a GitHub token. This is a second validation path; the existing GitHub-hosted workflow is
unchanged.

The controller accepts any local Git ref, resolves it to an immutable commit SHA, creates a clean
source archive with `git archive`, and uploads that archive. This controller-upload deployment is
the default and works when FIPIRAN is reachable from Iran but GitHub is not. Network diagnostics
still report GitHub reachability. `--deployment-mode clone` provides direct public cloning when
GitHub is reachable; `upload` is the first-class fallback and `auto` safely defaults to upload.

## Threat model

The repository is public, so a permanent self-hosted GitHub Actions runner would expose a trusted
Iran host to potentially untrusted workflow code. The SSH-driven design only runs when a trusted
controller explicitly invokes it. No persistent runner, GitHub token, private key, server address,
or database password is stored in the repository or artifacts.

The controller uses `BatchMode=yes`, an eight-second connection timeout, and
`StrictHostKeyChecking=accept-new`. It checks `root`, `ubuntu`, `debian`, `admin`, and `linux`, using
the caller's SSH agent, SSH config, and standard keys. It never prompts for a password or copies a
private key. If authentication fails it emits `ssh_auth_required` JSON.

## Supported hosts and provisioning

Ubuntu 22.04/24.04 and Debian 12 on x86-64 are supported. Provisioning creates the locked-down
`irma-validator` system account and `/opt/irma-validator`, `/var/lib/irma-validator`, and
`/var/log/irma-validator`. It installs native Python, Git, rsync, CA certificates, and PostgreSQL.
The application never runs as root. PostgreSQL binds locally under its package defaults and gets a
random runtime password that is not logged or retained in artifacts. If UFW is present, incoming
traffic is denied except OpenSSH; outbound traffic remains allowed. No API, web, or database port
is opened.

Provisioning is idempotent. The same user and directories are reused, packages are reconciled by
the OS package manager, and the PostgreSQL role/database are only created when absent. Run it with:

```bash
python scripts/iran_live_validator.py --server 1.2.3.4 --provision-only
```

## Network and dependency behavior

Preflight records DNS, TCP 443, HTTP status, content type, latency, UTC time, disk, OS, and
architecture for FIPIRAN, GitHub, PyPI, Python package files, and the OS package repository. TLS
verification is always enabled. HTML error pages are not treated as JSON. Restrictions are detected
and reported; the validator implements no proxy, geo-restriction, or sanctions bypass.

Python dependencies first use normal TLS-verified pip installation. A controller-supplied official
wheelhouse at `/tmp/irma-wheelhouse` is supported as an offline fallback. No unknown mirror is
configured. Failure of both paths is reported as `dependency_install_failed`.

Read-only preflight performs no provisioning:

```bash
python scripts/iran_live_validator.py --server 1.2.3.4 --preflight
```

## Full validation and artifacts

The full run provisions the host, deploys the selected ref, diagnoses connectivity, migrates a
local PostgreSQL database, and runs the real FIPIRAN bootstrap twice on the same database. It uses a
history limit of two and bounded retries. Fixtures are never substituted. Counts from both runs
must match for idempotency.

The identity report checks `fipiran:12181:1` through `fipiran:12181:4` when those identities exist
in the selected ref and ensures at most one group owns history. A missing identity is reported, not
invented. The exact validated SHA is recorded.

Artifacts are retrieved to `artifacts/iran-live-validation/`:

- `iran-network-diagnostics.json`
- `live-bootstrap-first.json`
- `live-bootstrap-second.json`
- `live-data-validation.json`
- `fipiran-12181-validation.json`
- `manifest.json`
- `failure.json` when a stage fails

The manifest contains a truncated SHA-256 hash of the IP, never the IP itself. Logs and structured
errors redact credentials. Use `--cleanup` to remove the uploaded source and remote controller
after artifact retrieval; the current artifacts remain available until retrieved.

```bash
python scripts/iran_live_validator.py \
  --server 1.2.3.4 \
  --ref agent/fix-fipiran-record-identity \
  --cleanup
```

For the PR #8 follow-up, the one-IP wrapper is:

```bash
./scripts/validate_from_iran.sh 1.2.3.4
```

## Troubleshooting and removal

Structured statuses identify SSH authentication, unsupported OS/architecture, source upload,
dependency installation, PostgreSQL/provisioning, bootstrap, and artifact retrieval failures.
Inspect `failure.json` together with network diagnostics. A 502 HTML response is an external
connectivity failure, not a successful validation.

To remove the host integration after artifacts are retrieved, delete the `irma-validator` user,
its three directories, and the `irma_live_validation` database/`irma` role using the host's normal
administrative process. No GitHub runner or GitHub credential needs removal.
