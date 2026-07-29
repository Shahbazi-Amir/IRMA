from irma.config import Settings


def test_default_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "IRMA API"
    assert settings.port == 8000


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("IRMA_PORT", "9000")
    monkeypatch.setenv("IRMA_APP_ENV", "test")

    settings = Settings(_env_file=None)

    assert settings.port == 9000
    assert settings.app_env == "test"
