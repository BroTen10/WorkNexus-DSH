from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "WorkNexus-DSH Control Plane"
    version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://worknexus:worknexus_dev_password@127.0.0.1:15432/worknexus"
    jwt_secret: str = "replace-with-32-byte-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 15
    refresh_token_expires_days: int = 14
    email_code_ttl_minutes: int = 10
    email_code_resend_seconds: int = 60
    email_code_max_attempts: int = 5
    api_host: str = "127.0.0.1"
    api_port: int = 8410


@lru_cache
def get_settings() -> Settings:
    return Settings()
