from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Search Service API"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str
    DB_NAME: str = "searchservice"

    ELASTIC_HOST: str = "elasticsearch"
    ELASTIC_PORT: int = "9200"
    ELASTIC_PASSWORD: str

    OUTBOX_POLL_INTERVAL: float = 1.0
    OUTBOX_BATCH_SIZE: int = 100

    @property
    def DATABASE_URL(self) -> str:
        """Собирает DSN подключения к PostgreSQL для asyncpg."""
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )

    @property
    def ELASTIC_URL(self) -> str:
        """Собирает URL подключения к Elasticsearch."""
        return f"https://{self.ELASTIC_HOST}:{self.ELASTIC_PORT}"


settings = Settings()
