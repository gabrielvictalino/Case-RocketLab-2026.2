"""Modelo de linguagem do agente, escolhido por configuração."""

from typing import Literal

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

Provedor = Literal['google', 'openrouter']
MODELO_PADRAO = 'gemini-3.1-flash-lite'


def criar_modelo(provedor: Provedor, modelo: str, chave: str) -> Model:
    """Gemini pela API do Google ou qualquer modelo do OpenRouter (ex.: `google/...`)."""
    if provedor == 'google':
        return GoogleModel(modelo, provider=GoogleProvider(api_key=chave))
    if provedor == 'openrouter':
        return OpenRouterModel(modelo, provider=OpenRouterProvider(api_key=chave))
    raise ValueError(f'Provedor desconhecido: {provedor}')
