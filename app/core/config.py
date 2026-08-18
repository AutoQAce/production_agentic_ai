"""Settings management — Layer 0 (Foundation).

One concrete `Settings` class, loaded once and cached. Consumers do **not** import it directly;
they declare the narrow `Protocol` they need (see `LoggingConfig` in `logging.py`) and receive a
`Settings` that structurally satisfies it. One class, many narrow views — that is the DIP/ISP
shape this codebase uses instead of a `ConfigProvider` ABC with a single implementation.

**Environments.** `APP_ENV` is a free-form name (`development`, `sit`, `uat`, `perf`, `production`,
…). It does two independent jobs, deliberately kept separate:

  * it selects which `.env.*` files load (`_env_files`), so a new environment needs a new file,
    not a code change;
  * it maps through `ENVIRONMENT_TIERS` to a `DeploymentTier`, which is the *policy* class the
    startup guard branches on. Adding an environment means adding one row to that dict — the guard
    itself never changes (OCP).

**Precedence**, lowest to highest: `.env` → `.env.local` → `.env.<app_env>` →
`.env.<app_env>.local` → real process environment. Missing files are skipped silently, so a
container that injects everything as real env vars needs no files at all.

**Adding a cloud secret store later** (Key Vault, Secrets Manager, SSM) requires no redesign of
this file: override `settings_customise_sources` on `Settings` and insert the new source into the
returned tuple at the precedence you want. That hook is built into `BaseSettings`; nothing is
pre-scaffolded here for it on purpose.
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError

# app/core/config.py -> app/core -> app -> <project root>. Resolved from __file__, not the CWD,
# so `.env` discovery does not depend on where uvicorn/pytest was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DeploymentTier(StrEnum):
    """The *policy* class of an environment — what the startup guard enforces.

    Distinct from the environment's name: `sit`, `uat` and `preprod` are all separate deployments
    with their own `.env.*` files, but they share one policy tier.
    """

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


# APP_ENV value -> policy tier. Data, not branches: a new environment is one row here.
# Unknown names are rejected at startup rather than silently defaulting to a lax tier.
ENVIRONMENT_TIERS: dict[str, DeploymentTier] = {
    "local": DeploymentTier.DEVELOPMENT,
    "dev": DeploymentTier.DEVELOPMENT,
    "development": DeploymentTier.DEVELOPMENT,
    "test": DeploymentTier.TEST,
    "ci": DeploymentTier.TEST,
    "sit": DeploymentTier.STAGING,
    "uat": DeploymentTier.STAGING,
    "qa": DeploymentTier.STAGING,
    "stage": DeploymentTier.STAGING,
    "staging": DeploymentTier.STAGING,
    "preprod": DeploymentTier.STAGING,
    "prod": DeploymentTier.PRODUCTION,
    "production": DeploymentTier.PRODUCTION,
}

# Tiers that run on shared infrastructure and must never boot on `.env.example` defaults.
_STRICT_TIERS = frozenset({DeploymentTier.STAGING, DeploymentTier.PRODUCTION})

# Literal placeholders shipped in `.env.example`. Anything starting with "your-" is caught too,
# which covers the rest of that file without listing every key.
_PLACEHOLDER_SECRETS = frozenset({"change-me", "changeme", "secret", "password", "mypassword", "postgres"})

_MIN_PRODUCTION_SECRET_LENGTH = 32


def _current_app_env() -> str:
    """Read `APP_ENV` from the *process* environment.

    Deliberately not read from a `.env` file: this value chooses which file to load, so it has to
    be known before any file is parsed. Setting `APP_ENV` inside `.env.production` cannot work.
    """
    return os.getenv("APP_ENV", "development").strip().lower()


def _env_files(app_env: str) -> tuple[Path, ...]:
    """Env files in ascending precedence — later entries win, absent entries are skipped.

    The `.local` tiers are the developer-override escape hatch and are gitignored; the plain
    `.env.<app_env>` is the one a deployment provides.
    """
    return (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / f".env.{app_env}",
        PROJECT_ROOT / f".env.{app_env}.local",
    )


def _is_placeholder(secret: SecretStr) -> bool:
    """True when a secret is empty or still holds an example/scaffold value."""
    value = secret.get_secret_value().strip().lower()
    return not value or value in _PLACEHOLDER_SECRETS or value.startswith("your-")


class Settings(BaseSettings):
    """Typed application settings, populated from `.env` files and the process environment.

    Frozen: settings are read once at startup and never mutated at runtime, so no request handler
    can reconfigure the process out from under another (the article's `setattr`-based
    environment overrides are exactly the hazard this removes).
    """

    model_config = SettingsConfigDict(
        env_file=_env_files(_current_app_env()),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        frozen=True,
    )

    # --- Application ---
    APP_ENV: str = Field(default_factory=_current_app_env)
    PROJECT_NAME: str = "7 Layers Production Agentic AI"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # --- API ---
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # --- Logging (consumed via the `LoggingConfig` Protocol in app/core/logging.py) ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # validated by `_tail_processors_for()`, which owns the renderer registry

    # --- LLM ---
    OPENAI_API_KEY: SecretStr = SecretStr("")
    DEFAULT_LLM_MODEL: str = "gpt-5.4-mini"
    DEFAULT_LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
    MAX_LLM_CALL_RETRIES: int = Field(default=3, ge=0)  # used by the Tenacity retry decorator

    # --- JWT / Auth ---
    JWT_SECRET_KEY: SecretStr = SecretStr("change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1)

    # --- Database (PostgreSQL) ---
    POSTGRES_HOST: str = "db"
    POSTGRES_DB: str = "mydb"
    POSTGRES_USER: str = "myuser"
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_PASSWORD: SecretStr = SecretStr("mypassword")

    # --- Observability (Langfuse) ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: SecretStr = SecretStr("")
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _normalise_app_env(cls, value: str) -> str:
        """Accept `Production`/` prod ` and friends without a separate alias table."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        """Uppercase so `LOG_LEVEL=debug` in a `.env` file works."""
        return value.strip().upper() if isinstance(value, str) else value

    @property
    def tier(self) -> DeploymentTier:
        """Policy class for `APP_ENV`. Validated at construction, so this never raises here."""
        return ENVIRONMENT_TIERS[self.APP_ENV]

    @property
    def allowed_origins_list(self) -> list[str]:
        """CORS origins as a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def postgres_dsn(self) -> SecretStr:
        """SQLAlchemy/psycopg connection string.

        Returned as `SecretStr` because it embeds the password — an accidental `logger.info(dsn)`
        would otherwise ship credentials into the log pipeline. Call sites use
        `.get_secret_value()`, which makes the exposure a visible, deliberate line of code.
        User and password are percent-encoded so values containing `@`, `/` or `:` still work.
        """
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
        return SecretStr(
            f"postgresql://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @model_validator(mode="after")
    def _validate_startup_policy(self) -> Settings:
        """Fail loudly at startup rather than quietly serving a misconfigured process.

        Runs on every tier for things that are always wrong (an unknown environment name, a bogus
        log level), then applies the extra rules that only shared-infrastructure tiers need.
        """
        tier = ENVIRONMENT_TIERS.get(self.APP_ENV)
        if tier is None:
            raise ConfigurationError(
                f"Unknown APP_ENV: {self.APP_ENV!r}",
                known_environments=sorted(ENVIRONMENT_TIERS),
                hint="add it to ENVIRONMENT_TIERS with the policy tier it belongs to",
            )

        # Sourced from stdlib rather than a hardcoded list, so custom levels registered via
        # logging.addLevelName() are accepted automatically.
        if self.LOG_LEVEL not in logging.getLevelNamesMapping():
            raise ConfigurationError(
                f"Unknown LOG_LEVEL: {self.LOG_LEVEL!r}",
                valid_levels=sorted(logging.getLevelNamesMapping()),
            )

        if tier not in _STRICT_TIERS:
            return self

        if self.DEBUG:
            raise ConfigurationError("DEBUG must be false outside development", app_env=self.APP_ENV, tier=str(tier))

        for name, secret in (
            ("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
            ("OPENAI_API_KEY", self.OPENAI_API_KEY),
            ("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD),
        ):
            if _is_placeholder(secret):
                raise ConfigurationError(
                    f"{name} is unset or still a placeholder", app_env=self.APP_ENV, tier=str(tier)
                )

        if tier is DeploymentTier.PRODUCTION:
            if "*" in self.allowed_origins_list:
                raise ConfigurationError("ALLOWED_ORIGINS must not be a wildcard in production")
            if len(self.JWT_SECRET_KEY.get_secret_value()) < _MIN_PRODUCTION_SECRET_LENGTH:
                raise ConfigurationError(
                    "JWT_SECRET_KEY is too short for production",
                    minimum_length=_MIN_PRODUCTION_SECRET_LENGTH,
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings`, reading the environment exactly once.

    The cache is the injection seam: production calls this (directly or via FastAPI's `Depends`),
    tests set env vars and call `get_settings.cache_clear()`. No module-level singleton — importing
    this module has no side effects, so a test can choose its environment before the first read.
    """
    return Settings()
