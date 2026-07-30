"""Run one configured manual data refresh."""

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.services.data_refresh import refresh_from_configured_csv


def main() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        result = refresh_from_configured_csv(
            session,
            csv_path=settings.fund_csv_path,
            max_retries=settings.provider_max_retries,
        )
    print(result)


if __name__ == "__main__":
    main()
