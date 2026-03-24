import os
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


def _build_postgres_uri() -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5433")
    name = os.environ.get("DB_NAME", "mezahub")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-key")

    # JWT lifetimes (can be overridden via env)
    JWT_ACCESS_TOKEN_EXPIRES_MIN = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MIN", "15"))
    JWT_REFRESH_TOKEN_EXPIRES_DAYS = int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7"))

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5000,http://127.0.0.1:5000",
        ).split(",")
        if origin.strip()
    ]
    PUBLIC_API_BASE_URL = os.environ.get("PUBLIC_API_BASE_URL")
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "true").lower() == "true"

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")

    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", "20"))

    # Rate limiting configuration (Flask-Limiter reads these from app.config)
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", REDIS_URL)
    # Flask-Limiter accepts list/tuple; we split env string on ';'
    RATELIMIT_DEFAULT = tuple(
        part.strip()
        for part in os.environ.get("RATELIMIT_DEFAULT", "200 per day;50 per hour").split(";")
        if part.strip()
    )

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # type: ignore[override]
        database_url = _normalize_database_url(os.environ.get("DATABASE_URL"))
        if database_url:
            return database_url
        # Default to SQLite for local dev (works out-of-the-box).
        return os.environ.get("SQLITE_URL", "sqlite:///mezahub.db")


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # type: ignore[override]
        # Use SQLite by default so the app works without PostgreSQL (no port 5433).
        # Set USE_POSTGRES_DEV=1 in .env to use DATABASE_URL instead.
        if os.environ.get("USE_POSTGRES_DEV", "").strip().lower() in ("1", "true", "yes"):
            url = _normalize_database_url(os.environ.get("DATABASE_URL"))
            if url:
                return url
        return os.environ.get("SQLITE_URL", "sqlite:///mezahub.db")


class TestingConfig(Config):
    DEBUG = False
    TESTING = True

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # type: ignore[override]
        return os.environ.get("TEST_DATABASE_URL", "sqlite:///mezahub_test.db")


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # type: ignore[override]
        database_url = _normalize_database_url(os.environ.get("DATABASE_URL"))
        if database_url:
            return database_url
        return _build_postgres_uri()


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
