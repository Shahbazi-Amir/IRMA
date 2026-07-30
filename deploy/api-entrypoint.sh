#!/bin/sh
set -eu
alembic upgrade head
exec uvicorn irma.main:app --host "${IRMA_HOST:-0.0.0.0}" --port "${IRMA_PORT:-8000}"
