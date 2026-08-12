#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/iran_live_validator.py" --server "${1:?usage: validate_from_iran.sh SERVER_IP [REF]}" --ref "${2:-agent/fix-fipiran-record-identity}"
