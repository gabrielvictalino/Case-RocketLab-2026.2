from functools import lru_cache
from typing import Annotated, Literal, NamedTuple

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ProvedorIA = Literal['google', 'openrouter']


class ModeloReserva(NamedTuple):
    provedor: ProvedorIA
    modelo: str


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
    ai_provedor: ProvedorIA = 'google'
    ai_modelo: str = 'gemini-3.1-flash-lite'
    # Reservas, opcionais e em ordem: recebem a chamada quando a API do anterior falha.
    # No ambiente: AI_MODELOS_RESERVA=openrouter:google/gemini-3.1-flash-lite,google:<modelo>
    ai_modelos_reserva: Annotated[list[ModeloReserva], NoDecode] = []
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    assistente_timeout_s: float = Field(default=30, gt=0, le=120)
    # Limites por usuário no Redis (fail-open): perguntas por minuto e tokens por dia.
    assistente_perguntas_por_minuto: int = Field(default=20, ge=1)
    assistente_cota_tokens_dia: int = Field(default=500_000, ge=1)
    # Insights: só os que vão ao modelo contam; um insight do cache não gasta o limite.
    insights_por_minuto: int = Field(default=30, ge=1)

    @field_validator('ai_modelos_reserva', mode='before')
    @classmethod
    def ler_reservas(cls, valor):
        # Do ambiente vem o texto `provedor:modelo,...`; o Compose repassa a variável
        # ausente como texto vazio. Só o primeiro `:` separa: nomes do OpenRouter podem
        # ter outro (`...:free`).
        if not isinstance(valor, str):
            return valor
        reservas = []
        for item in filter(None, (parte.strip() for parte in valor.split(','))):
            provedor, separador, modelo = item.partition(':')
            if not separador or not modelo.strip():
                raise ValueError(f'Use provedor:modelo em AI_MODELOS_RESERVA, e não {item!r}')
            reservas.append((provedor.strip(), modelo.strip()))
        return reservas

    @model_validator(mode='after')
    def validate_reservas(self):
        # Repetir um modelo da cadeia parece redundância, mas só repete a mesma falha.
        cadeia = [(self.ai_provedor, self.ai_modelo), *self.ai_modelos_reserva]
        if len(set(cadeia)) != len(cadeia):
            raise ValueError('AI_MODELOS_RESERVA repete um modelo da cadeia')
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
