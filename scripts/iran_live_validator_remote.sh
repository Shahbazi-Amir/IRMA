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

# Mutation-free shell preflight: minimal images may not have Python yet.
missing=()
for tool in sudo apt-get systemctl; do command -v "$tool" >/dev/null 2>&1 || missing+=("$tool"); done
if ! command -v python3 >/dev/null 2>&1; then
  printf '{"status":"python_missing"}\n'
  [[ "$ACTION" == preflight ]] && exit 10
  PYTHON_MISSING=1
else
  PYTHON_MISSING=0
fi
if [[ $(id -u) -eq 0 ]]; then
  SUDO=
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  SUDO="sudo -n"
else
  printf '{"status":"sudo_auth_required"}\n'
  exit 11
fi
if ((${#missing[@]})) && [[ "$ACTION" == preflight ]]; then
  printf '{"status":"missing_prerequisites","commands":"%s"}\n' "${missing[*]}"
  exit 12
fi
if [[ "$PYTHON_MISSING" == 1 ]]; then
  command -v apt-get >/dev/null 2>&1 || { printf '{"status":"python_install_unavailable"}\n'; exit 13; }
  $SUDO apt-get update -qq
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3
fi

if [[ -r /etc/os-release ]]; then . /etc/os-release; fi
case "${ID:-unknown}" in
  ubuntu) PACKAGE_URL=https://archive.ubuntu.com/ubuntu/ ;;
  debian) PACKAGE_URL=https://deb.debian.org/debian/ ;;
  *) PACKAGE_URL="" ;;
esac
export PACKAGE_URL

json_escape() { python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'; }
write_failure() {
  local status=$1 message=$2
  printf '{"status":"%s","message":%s}\n' "$status" "$(printf %s "$message" | json_escape)" > "$ARTIFACTS/failure.json"
}
trap 'code=$?; write_failure remote_failure "remote validator exited with status $code"; exit $code' ERR

$SUDO mkdir -p "$ARTIFACTS"
$SUDO chown "$(id -u):$(id -g)" "$ARTIFACTS"
chmod 700 "$ARTIFACTS"

network_diagnostics() {
  python3 - "$ARTIFACTS/iran-network-diagnostics.json" <<'PY'
import hashlib, json, os, socket, ssl, subprocess, sys, time, urllib.error, urllib.request
from urllib.parse import urlparse
targets = {
 "fipiran_website":"https://www.fipiran.com/",
 "fipiran_catalogue":"https://www.fipiran.com/services/fund/fundcompare/",
 "fipiran_history":"https://www.fipiran.com/services/chart/getfundchart?regno=12181&showAll=false",
 "github":"https://github.com/", "github_api":"https://api.github.com/",
 "github_objects":"https://objects.githubusercontent.com/", "pypi":"https://pypi.org/simple/",
 "python_files":"https://files.pythonhosted.org/", "package_repository":os.environ.get("PACKAGE_URL", ""),
}
results = {}
for name, url in targets.items():
    if not url: continue
    host = urlparse(url).hostname or ""
    item = {"dns": False, "tcp_443": False, "http_status": None, "content_type": None, "latency_ms": None, "valid_json":False}
    started = time.monotonic()
    try:
        socket.getaddrinfo(host, 443); item["dns"] = True
        with socket.create_connection((host, 443), timeout=8): item["tcp_443"] = True
        data = None
        headers={"User-Agent":"IRMA-Iran-Validator/1.0"}
        if name == "fipiran_catalogue":
            data=json.dumps({"regNos":[],"showMarketMakers":False}).encode(); headers["Content-Type"]="application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
        with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            limit=8*1024*1024; body=response.read(limit+1); item["read_size"]=len(body)
            if len(body)>limit: raise ValueError("response_too_large")
            item["response_sha256"]=hashlib.sha256(body).hexdigest(); item["http_status"] = response.status
            item["content_type"] = response.headers.get_content_type()
            item["content_length"]=response.headers.get("Content-Length")
            try:
                parsed=json.loads(body); item["valid_json"]=True
                expected=list if name=="fipiran_history" else (dict,list)
                item["classification"]="reachable" if isinstance(parsed,expected) else "contract_mismatch"
            except json.JSONDecodeError:
                item["classification"]="invalid_json"
    except urllib.error.HTTPError as exc:
        item["http_status"] = exc.code; item["content_type"] = exc.headers.get_content_type()
        item["classification"]="html_502" if exc.code==502 and "html" in item["content_type"] else "http_error"
    except socket.gaierror as exc: item.update(error=str(exc),classification="dns_failure")
    except (socket.timeout,TimeoutError) as exc: item.update(error=str(exc),classification="timeout")
    except ssl.SSLError as exc: item.update(error=str(exc),classification="tls_failure")
    except (ConnectionError,OSError) as exc: item.update(error=str(exc),classification="tcp_failure")
    except (ValueError,json.JSONDecodeError) as exc: item.update(error=str(exc),classification="invalid_json")
    item["latency_ms"] = round((time.monotonic()-started)*1000)
    item.setdefault("classification","reachable" if item["http_status"] and item["http_status"]<400 else "http_error")
    results[name] = item
results["dns_resolution"] = {"ok": any(v["dns"] for v in results.values())}
sync="unknown"
try:
    value=subprocess.run(["timedatectl","show","-p","NTPSynchronized","--value"],capture_output=True,text=True,timeout=3).stdout.strip().lower()
    if value in ("yes","true","1"): sync=True
    elif value in ("no","false","0"): sync=False
except Exception: pass
results["time_sync"]={"checked":sync!="unknown","synchronized":sync}
json.dump(results, open(sys.argv[1], "w"), indent=2)
PY
}

network_diagnostics
if [[ "$ACTION" == preflight ]]; then
  python3 - "$ARTIFACTS/manifest.json" <<'PY'
import json, os, platform, shutil, sys
mem_kib=0
try:
    mem_kib=int(next(x.split()[1] for x in open('/proc/meminfo') if x.startswith('MemTotal:')))
except Exception: pass
disk=shutil.disk_usage('/').free
json.dump({"status":"preflight_complete","server_region":"IR","server_ip_hash":os.getenv("IRMA_SERVER_HASH"),
 "os":platform.platform(),"architecture":platform.machine(),"disk_free_bytes":disk,"ram_bytes":mem_kib*1024,
 "cpu_count":os.cpu_count(),"resource_warnings":[x for x,bad in (("low_ram",mem_kib<1024*1024),("low_disk",disk<5*1024**3)) if bad],
 "target_ref":os.getenv("IRMA_TARGET_REF"),"fixture_used":False}, open(sys.argv[1],"w"), indent=2)
PY
  exit 0
fi
$SUDO apt-get update -qq
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip postgresql postgresql-client git rsync ca-certificates
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
  if [[ $(id -u) -eq 0 ]]; then runuser -u "$APP_USER" -- "$@"; else sudo -n -u "$APP_USER" -- "$@"; fi
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
  if [[ -f /tmp/irma-wheelhouse/.validated && -d /tmp/irma-wheelhouse ]]; then
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
if [[ "${IRMA_CLEANUP:-0}" == 1 ]]; then
  rm -f /tmp/irma-source.tar.gz /tmp/irma-live-validator-remote.sh /tmp/irma-wheelhouse.tar.gz
  rm -rf /tmp/irma-wheelhouse /tmp/irma-validator-work
fi
printf '{"status":"success","artifacts":"retrievable"}\n'
