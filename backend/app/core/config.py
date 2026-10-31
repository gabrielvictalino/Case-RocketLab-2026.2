from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    database_url_portal: str = 'postgresql+asyncpg://portal:portal_dev@localhost:5432/venergy'
    database_url_ai: str = 'postgresql+asyncpg://ai_read:ai_dev@localhost:5432/venergy'
    database_url_migrations: str = (
        'postgresql+asyncpg://postgres:postgres_dev@localhost:5432/venergy'
    )
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: SecretStr = SecretStr('desenvolvimento-local-troque-esta-chave-32')
    jwt_expiration_hours: int = Field(default=8, ge=1, le=24)

    @model_validator(mode='after')
    def validate_secret(self):
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < 32 or (
            self.app_env != 'development' and secret.startswith('desenvolvimento')
        ):
            raise ValueError(
                'JWT_SECRET deve ter pelo menos 32 caracteres e ser própria do ambiente'
            )
        return self


@lru_cache
def get_settings():
    return Settings()
