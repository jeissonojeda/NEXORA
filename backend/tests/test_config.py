from app.core.config import Settings, get_settings


def test_config_loads_with_defaults() -> None:
    settings = get_settings()
    assert settings.APP_NAME == "Sistema de Facturación e Inventario con IA"
    assert settings.APP_ENV == "development"
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30


def test_config_cors_origins_parsed_as_list() -> None:
    settings = get_settings()
    assert "http://localhost:5173" in settings.cors_origins_list


def test_config_is_production_false_in_development() -> None:
    settings = get_settings()
    assert settings.is_production is False


def test_settings_singleton_is_cached() -> None:
    assert get_settings() is get_settings()


def test_settings_rejects_invalid_types() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(ACCESS_TOKEN_EXPIRE_MINUTES="not-a-number")
