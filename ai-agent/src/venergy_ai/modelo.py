"""Modelo de linguagem do agente, escolhido por configuração."""

from typing import Literal

from pydantic_ai import AgentRunResult, FallbackExceptionGroup, ModelAPIError
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from venergy_ai.interface import ProvedorIndisponivel

Provedor = Literal['google', 'openrouter']
MODELO_PADRAO = 'gemini-3.1-flash-lite'
# Uma falha de API do modelo (HTTP, timeout, conexão) ou, com reserva, a de todos eles.
FALHAS_DO_PROVEDOR = (ModelAPIError, FallbackExceptionGroup)


def criar_modelo(provedor: Provedor, modelo: str, chave: str) -> Model:
    """Gemini pela API do Google ou qualquer modelo do OpenRouter (ex.: `google/...`)."""
    if provedor == 'google':
        return GoogleModel(modelo, provider=GoogleProvider(api_key=chave))
    if provedor == 'openrouter':
        return OpenRouterModel(modelo, provider=OpenRouterProvider(api_key=chave))
    raise ValueError(f'Provedor desconhecido: {provedor}')


def com_reserva(principal: Model, *reservas: Model) -> Model:
    """O principal e, se houver, as reservas em ordem: uma falha de API passa a chamada
    para o próximo. Uma saída fora do formato não troca de modelo."""
    return FallbackModel(principal, *reservas) if reservas else principal


def modelo_que_respondeu(execucao: AgentRunResult, configurado: Model) -> str:
    """O nome do modelo que de fato respondeu, e não o `fallback:...` da configuração."""
    return execucao.response.model_name or configurado.model_name


def provedor_indisponivel(erro: Exception) -> ProvedorIndisponivel:
    """Com reserva, a falha traz o erro de cada modelo, com o nome dele: a mensagem de um
    timeout não diz de quem foi. A mensagem vai para a auditoria."""
    if isinstance(erro, FallbackExceptionGroup):
        return ProvedorIndisponivel(
            '; '.join(f'{getattr(falha, "model_name", "?")}: {falha}' for falha in erro.exceptions)
        )
    return ProvedorIndisponivel(str(erro))
