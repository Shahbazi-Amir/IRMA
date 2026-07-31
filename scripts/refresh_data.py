"""Run one configured data refresh with a machine-readable report."""

import json
import sys

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.services.data_refresh import refresh_from_settings


def main() -> int:
    settings = get_settings()
    try:
        with SessionLocal() as session:
            result = refresh_from_settings(session, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "provider": settings.fund_provider, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
