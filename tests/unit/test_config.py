from __future__ import annotations

from job_pilot.core.config import resolve_env_file, settings


def test_resolve_env_file_defaults_to_dotenv(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)

    env_file = resolve_env_file()

    assert env_file.name == ".env"


def test_resolve_env_file_uses_test_env_file(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")

    env_file = resolve_env_file()

    assert env_file.name == ".env.test"


def test_resolve_env_file_uses_explicit_app_env() -> None:
    env_file = resolve_env_file("prod")

    assert env_file.name == ".env.prod"


def test_resolve_env_file_falls_back_to_dotenv_for_unknown_env() -> None:
    env_file = resolve_env_file("unknown")

    assert env_file.name == ".env"


def test_settings_load_test_env_file_during_pytest() -> None:
    assert settings.APP_ENV == "test"
    assert settings.SECRET_KEY == "test-secret-key-for-jobpilot-32-bytes"
