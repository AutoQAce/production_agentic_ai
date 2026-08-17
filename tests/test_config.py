"""Settings tests — environment tiering, the startup policy guard, and secret handling.

Every `Settings(...)` here passes `_env_file=None` so the developer's real `.env` files can't
leak into assertions; explicit kwargs are the highest-precedence source, so the process
environment can't either.
"""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DeploymentTier, Settings, get_settings
from app.core.exceptions import ConfigurationError

PROD_SECRETS = {
    "JWT_SECRET_KEY": "x" * 40,
    "OPENAI_API_KEY": "sk-real-key",
    "POSTGRES_PASSWORD": "s3cret-from-vault",
}


def build(**overrides):
    """Construct Settings in isolation from any .env file."""
    return Settings(_env_file=None, **overrides)


def prod(**overrides):
    """A production-tier Settings that satisfies the guard, plus any overrides."""
    base = {
        "APP_ENV": "production",
        "DEBUG": False,
        "ALLOWED_ORIGINS": "https://app.example.com",
        **PROD_SECRETS,
    }
    return build(**{**base, **overrides})


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [
        ("development", DeploymentTier.DEVELOPMENT),
        ("uat", DeploymentTier.STAGING),
        ("sit", DeploymentTier.STAGING),
        ("PROD", DeploymentTier.PRODUCTION),  # normalised to lowercase before lookup
    ],
)
def test_app_env_maps_to_tier(app_env, expected):
    settings = build(APP_ENV=app_env, DEBUG=False, **PROD_SECRETS, ALLOWED_ORIGINS="https://app.example.com")
    assert settings.tier is expected


def test_unknown_app_env_is_rejected():
    with pytest.raises(ConfigurationError, match="Unknown APP_ENV"):
        build(APP_ENV="banana")


def test_unknown_log_level_is_rejected():
    with pytest.raises(ConfigurationError, match="Unknown LOG_LEVEL"):
        build(LOG_LEVEL="CHATTY")


def test_log_level_is_normalised_to_uppercase():
    assert build(LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"


def test_development_tolerates_placeholder_secrets():
    # The whole point of the dev tier: `.env.example` defaults must still boot.
    assert build(APP_ENV="development").tier is DeploymentTier.DEVELOPMENT


@pytest.mark.parametrize("field", sorted(PROD_SECRETS))
def test_strict_tiers_reject_placeholder_secrets(field):
    with pytest.raises(ConfigurationError, match=f"{field} is unset or still a placeholder"):
        prod(**{field: "your-placeholder-value"})


def test_strict_tiers_reject_debug():
    with pytest.raises(ConfigurationError, match="DEBUG must be false"):
        prod(APP_ENV="uat", DEBUG=True)


def test_production_rejects_wildcard_cors():
    with pytest.raises(ConfigurationError, match="ALLOWED_ORIGINS must not be a wildcard"):
        prod(ALLOWED_ORIGINS="https://app.example.com,*")


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY is too short"):
        prod(JWT_SECRET_KEY="short-but-not-a-placeholder")


def test_staging_allows_short_jwt_secret_and_wildcard():
    # Length/CORS rules are production-only; staging just needs real (non-placeholder) values.
    assert prod(APP_ENV="uat", JWT_SECRET_KEY="short-real", ALLOWED_ORIGINS="*").tier is DeploymentTier.STAGING


def test_secrets_do_not_leak_through_repr():
    dumped = repr(prod())
    assert "sk-real-key" not in dumped
    assert "s3cret-from-vault" not in dumped


def test_postgres_dsn_is_secret_and_percent_encodes_credentials():
    dsn = prod(
        POSTGRES_USER="us@r", POSTGRES_PASSWORD="p@ss/word", POSTGRES_HOST="db", POSTGRES_PORT=5432
    ).postgres_dsn
    assert isinstance(dsn, SecretStr)
    assert dsn.get_secret_value() == "postgresql://us%40r:p%40ss%2Fword@db:5432/mydb"


def test_allowed_origins_list_splits_and_strips():
    assert build(ALLOWED_ORIGINS=" a , ,b ").allowed_origins_list == ["a", "b"]


def test_settings_are_frozen():
    with pytest.raises(ValidationError, match="frozen"):
        build().DEBUG = False


def test_get_settings_is_cached_and_clearable(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    first = get_settings()
    assert first is get_settings()
    get_settings.cache_clear()
    assert get_settings() is not first
    get_settings.cache_clear()
