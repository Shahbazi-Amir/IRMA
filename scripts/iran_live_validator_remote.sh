#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ACTION=${IRMA_ACTION:-validate}
APP_ROOT=/opt/irma-validator
STATE_ROOT=/var/lib/irma-validator
ARTIFACTS=/tmp/irma-validator-artifacts
LOG_ROOT=/var/log/irma-validator
APP_USER=irma-validator
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

json_escape() { python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'; }
write_failure() {
  local status=$1 message=$2
  printf '{"status":"%s","message":%s}\n' "$status" "$(printf %s "$message" | json_escape)" > "$ARTIFACTS/failure.json"
}
trap 'code=$?; write_failure remote_failure "remote validator exited with status $code"; exit $code' ERR

mkdir -p "$ARTIFACTS"
chmod 700 "$ARTIFACTS"

network_diagnostics() {
  python3 - "$ARTIFACTS/iran-network-diagnostics.json" <<'PY'
import json, socket, ssl, sys, time, urllib.error, urllib.request
from urllib.parse import urlparse
targets = {
 "fipiran_website":"https://www.fipiran.com/",
 "fipiran_catalogue":"https://www.fipiran.com/services/fund/fundcompare/",
 "fipiran_history":"https://www.fipiran.com/services/chart/getfundchart?regno=12181&showAll=false",
 "github":"https://github.com/", "github_api":"https://api.github.com/",
 "github_objects":"https://objects.githubusercontent.com/", "pypi":"https://pypi.org/simple/",
 "python_files":"https://files.pythonhosted.org/", "package_repository":"https://archive.ubuntu.com/ubuntu/",
}
results = {}
for name, url in targets.items():
    host = urlparse(url).hostname or ""
    item = {"dns": False, "tcp_443": False, "http_status": None, "content_type": None, "latency_ms": None}
    started = time.monotonic()
    try:
        socket.getaddrinfo(host, 443); item["dns"] = True
        with socket.create_connection((host, 443), timeout=8): item["tcp_443"] = True
        request = urllib.request.Request(url, headers={"User-Agent":"IRMA-Iran-Validator/1.0"})
        with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            body = response.read(1024); item["http_status"] = response.status
            item["content_type"] = response.headers.get_content_type()
            item["valid_json"] = bool(json.loads(body)) if "json" in item["content_type"] else False
    except urllib.error.HTTPError as exc:
        item["http_status"] = exc.code; item["content_type"] = exc.headers.get_content_type()
    except Exception as exc: item["error"] = type(exc).__name__
    item["latency_ms"] = round((time.monotonic()-started)*1000)
    results[name] = item
results["dns_resolution"] = {"ok": any(v["dns"] for v in results.values())}
results["time_sync"] = {"utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
json.dump(results, open(sys.argv[1], "w"), indent=2)
PY
}

network_diagnostics
if [[ "$ACTION" == preflight ]]; then
  python3 - "$ARTIFACTS/manifest.json" <<'PY'
import json, os, platform, shutil, sys
json.dump({"status":"preflight_complete","server_region":"IR","server_ip_hash":os.getenv("IRMA_SERVER_HASH"),
 "os":platform.platform(),"architecture":platform.machine(),"disk_free":shutil.disk_usage('/').free,
 "target_ref":os.getenv("IRMA_TARGET_REF"),"fixture_used":False}, open(sys.argv[1],"w"), indent=2)
PY
  exit 0
fi

if [[ $(id -u) -ne 0 ]]; then
  SUDO=sudo
else
  SUDO=
fi
$SUDO apt-get update -qq
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip postgresql postgresql-client git rsync ca-certificates
if ! id "$APP_USER" >/dev/null 2>&1; then $SUDO useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$APP_USER"; fi
$SUDO mkdir -p "$APP_ROOT" "$STATE_ROOT" "$LOG_ROOT" "$ARTIFACTS"
$SUDO chown -R "$APP_USER:$APP_USER" "$APP_ROOT" "$STATE_ROOT" "$LOG_ROOT"
$SUDO chown -R "$APP_USER:$APP_USER" "$ARTIFACTS"
$SUDO chmod 750 "$APP_ROOT" "$STATE_ROOT" "$LOG_ROOT"
if command -v ufw >/dev/null 2>&1; then
  $SUDO ufw default deny incoming >/dev/null
  $SUDO ufw default allow outgoing >/dev/null
  $SUDO ufw allow OpenSSH >/dev/null
  $SUDO ufw --force enable >/dev/null
fi
if [[ "$ACTION" == provision ]]; then exit 0; fi

$SUDO systemctl enable --now postgresql
DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
$SUDO -u postgres psql -v ON_ERROR_STOP=1 -v password="$DB_PASSWORD" <<'SQL' >/dev/null
SELECT format('CREATE ROLE irma LOGIN PASSWORD %L', :'password') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='irma') \gexec
SELECT 'CREATE DATABASE irma_live_validation OWNER irma' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='irma_live_validation') \gexec
ALTER ROLE irma PASSWORD :'password';
SQL

$SUDO find "$APP_ROOT" -mindepth 1 -maxdepth 1 ! -name venv -exec rm -rf -- {} +
run_as_app() {
  if [[ $(id -u) -eq 0 ]]; then runuser -u "$APP_USER" -- "$@"; else sudo -u "$APP_USER" -- "$@"; fi
}
if [[ "${IRMA_DEPLOYMENT_MODE:-upload}" == clone ]]; then
  run_as_app git clone --quiet https://github.com/Shahbazi-Amir/IRMA.git "$APP_ROOT/source"
  $SUDO find "$APP_ROOT/source" -mindepth 1 -maxdepth 1 -exec mv -t "$APP_ROOT" -- {} +
  $SUDO rmdir "$APP_ROOT/source"
  run_as_app git -C "$APP_ROOT" checkout --quiet "$IRMA_TARGET_SHA"
else
  run_as_app tar -xzf /tmp/irma-source.tar.gz -C "$APP_ROOT"
fi
if [[ ! -x "$APP_ROOT/venv/bin/python" ]]; then run_as_app python3 -m venv "$APP_ROOT/venv"; fi
if ! run_as_app "$APP_ROOT/venv/bin/pip" install --require-virtualenv -e "$APP_ROOT"; then
  if [[ -d /tmp/irma-wheelhouse ]]; then
    run_as_app "$APP_ROOT/venv/bin/pip" install --no-index --find-links /tmp/irma-wheelhouse -e "$APP_ROOT"
  else
    write_failure dependency_install_failed "PyPI unavailable and no controller wheel bundle present"; exit 20
  fi
fi

DATABASE_URL="postgresql+psycopg://irma:${DB_PASSWORD}@127.0.0.1:5432/irma_live_validation"
export IRMA_DATABASE_URL="$DATABASE_URL" IRMA_FUND_PROVIDER=fipiran IRMA_FUND_HISTORY_LIMIT=2
export IRMA_FUND_HISTORY_ALL=false IRMA_PROVIDER_MAX_RETRIES=3 IRMA_PROVIDER_MIN_INTERVAL_SECONDS=1
cd "$APP_ROOT"
run_bootstrap() {
  local output=$1
  set +e
  run_as_app env IRMA_DATABASE_URL="$IRMA_DATABASE_URL" IRMA_FUND_PROVIDER=fipiran IRMA_FUND_HISTORY_LIMIT=2 IRMA_FUND_HISTORY_ALL=false IRMA_PROVIDER_MAX_RETRIES=3 IRMA_PROVIDER_MIN_INTERVAL_SECONDS=1 "$APP_ROOT/venv/bin/python" scripts/bootstrap_data.py > "$output"
  local code=$?
  set -e
  return "$code"
}
run_bootstrap "$ARTIFACTS/live-bootstrap-first.json" || { write_failure bootstrap_first_failed "first live bootstrap failed"; exit 30; }
run_bootstrap "$ARTIFACTS/live-bootstrap-second.json" || { write_failure bootstrap_second_failed "second live bootstrap failed"; exit 31; }

run_as_app env IRMA_DATABASE_URL="$IRMA_DATABASE_URL" "$APP_ROOT/venv/bin/python" - "$ARTIFACTS/live-data-validation.json" "$ARTIFACTS/fipiran-12181-validation.json" <<'PY'
import json, os, sys
from sqlalchemy import create_engine, inspect, text
engine=create_engine(os.environ['IRMA_DATABASE_URL'])
with engine.connect() as c:
    tables=set(inspect(engine).get_table_names())
    counts={name:c.execute(text(f'SELECT count(*) FROM {name}')).scalar() for name in ('funds','fund_nav_history','fund_metrics','data_sources') if name in tables}
    identities=[]
    if 'funds' in tables:
        identities=[dict(row._mapping) for row in c.execute(text("SELECT id,external_id,symbol,name_fa FROM funds WHERE external_id LIKE 'fipiran:12181:%' ORDER BY external_id"))]
    owners=[]
    if identities and 'fund_nav_history' in tables:
        owners=[dict(row._mapping) for row in c.execute(text("SELECT f.external_id,count(h.id) history_count FROM funds f LEFT JOIN fund_nav_history h ON h.fund_id=f.id WHERE f.external_id LIKE 'fipiran:12181:%' GROUP BY f.external_id ORDER BY f.external_id"))]
validation={"status":"success","fixture_used":False,**{k[:-1]+'_count' if k.endswith('s') else k+'_count':v for k,v in counts.items()}}
json.dump(validation,open(sys.argv[1],'w'),indent=2,default=str)
expected={f'fipiran:12181:{i}' for i in range(1,5)}; actual={i['external_id'] for i in identities}
identity={"status":"success" if actual==expected and sum(x['history_count']>0 for x in owners)<=1 else "not_applicable_or_failed", "identities":identities,"history_owners":owners,"missing":sorted(expected-actual)}
json.dump(identity,open(sys.argv[2],'w'),indent=2,ensure_ascii=False,default=str)
PY

FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$ARTIFACTS/manifest.json" <<PY
import json
first=json.load(open("$ARTIFACTS/live-bootstrap-first.json")); second=json.load(open("$ARTIFACTS/live-bootstrap-second.json"))
keys=("fund_count","history_count","metric_count","source_count"); diff={k:[first.get(k),second.get(k)] for k in keys if first.get(k)!=second.get(k)}
manifest={"server_region":"IR","server_ip_hash":"$IRMA_SERVER_HASH","os":"$(. /etc/os-release; echo "$ID $VERSION_ID")",
"architecture":"$(uname -m)","target_ref":"$IRMA_TARGET_REF","target_sha":"$IRMA_TARGET_SHA","started_at":"$STARTED_AT",
"finished_at":"$FINISHED_AT","fipiran_reachable":first.get("status")=="success","bootstrap_first":first.get("status"),
"bootstrap_second":second.get("status"),"idempotency":"success" if not diff else "failed","idempotency_differences":diff,"fixture_used":False}
json.dump(manifest,open("$ARTIFACTS/manifest.json","w"),indent=2)
PY
chmod -R go-rwx "$ARTIFACTS"
if [[ "${IRMA_CLEANUP:-0}" == 1 ]]; then rm -f /tmp/irma-source.tar.gz /tmp/irma-live-validator-remote.sh; fi
printf '{"status":"success","artifacts":"retrievable"}\n'
