from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    # Agente: sem a chave do provedor escolhido, o assistente responde 503.
    ai_provedor: Literal['google', 'openrouter'] = 'google'
    ai_modelo: str = 'gemini-3.1-flash-lite'
    # Modelo de reserva, opcional: recebe a chamada quando a API do principal falha.
    ai_provedor_reserva: Literal['google', 'openrouter'] | None = None
    ai_modelo_reserva: str | None = None
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    assistente_timeout_s: float = Field(default=30, gt=0, le=120)
    # Limites por usuário no Redis (fail-open): perguntas por minuto e tokens por dia.
    assistente_perguntas_por_minuto: int = Field(default=20, ge=1)
    assistente_cota_tokens_dia: int = Field(default=500_000, ge=1)
    # Insights: só os que vão ao modelo contam; um insight do cache não gasta o limite.
    insights_por_minuto: int = Field(default=30, ge=1)

    @field_validator('ai_provedor_reserva', 'ai_modelo_reserva', mode='before')
    @classmethod
    def vazio_e_nenhum(cls, valor):
        # O Compose repassa a variável ausente como texto vazio.
        return valor or None

    @model_validator(mode='after')
    def validate_reserva(self):
        if (self.ai_provedor_reserva is None) != (self.ai_modelo_reserva is None):
            raise ValueError('Defina AI_PROVEDOR_RESERVA e AI_MODELO_RESERVA juntos')
        return self

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
