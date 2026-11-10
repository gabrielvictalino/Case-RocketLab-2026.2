"""Modelo de linguagem do agente, escolhido por configuração."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Literal

import anyio
from pydantic_ai import FallbackExceptionGroup, ModelAPIError, ModelResponse, ModelSettings
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from venergy_ai.interface import ProvedorIndisponivel

logger = logging.getLogger(__name__)

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


@dataclass
class Rodada:
    """Uma pergunta ao assistente ou um insight, do ponto de vista da cadeia de modelos.

    `inicio` é o modelo pelo qual a próxima chamada começa: depois que a reserva responde,
    a pergunta segue com ela e não espera de novo pelo principal que caiu. `prazo` é o teto
    da rodada no relógio do anyio. `modelos` são os que responderam, em ordem e sem repetir.
    """

    prazo: float | None = None
    inicio: int = 0
    modelos: list[str] = field(default_factory=list)

    def respondeu(self, indice: int, nome: str) -> None:
        self.inicio = indice
        if nome not in self.modelos:
            self.modelos.append(nome)


# Fica no contexto de quem chama o modelo: as chamadas de uma pergunta compartilham a
# rodada, e duas perguntas ao mesmo tempo não enxergam a rodada uma da outra.
_RODADA: ContextVar[Rodada | None] = ContextVar('rodada', default=None)


@contextmanager
def rodada(teto_s: float | None = None) -> Iterator[Rodada]:
    """Abre uma rodada para as chamadas feitas dentro do bloco."""
    atual = Rodada(prazo=None if teto_s is None else anyio.current_time() + teto_s)
    token = _RODADA.set(atual)
    try:
        yield atual
    finally:
        _RODADA.reset(token)


class ModeloComReserva(FallbackModel):
    """O principal e as reservas, em ordem: uma falha de API passa a chamada para o próximo.
    Uma saída fora do formato não troca de modelo.

    Dentro de uma `rodada`, a chamada começa pelo último modelo que respondeu, e cada
    modelo que falta tentar recebe uma parte igual do tempo que sobra até o teto: um
    principal travado não gasta o tempo das reservas. O último fica com o resto."""

    def __init__(self, principal: Model, *reservas: Model):
        super().__init__(principal, *reservas)
        # Um FallbackModel por modelo: ele prepara a chamada, aplica o prazo dela e
        # devolve a falha de API como FallbackExceptionGroup.
        self._sozinhos = [FallbackModel(modelo) for modelo in self.models]

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        atual = _RODADA.get() or Rodada()
        falhas, tentativas = [], []
        for indice in range(atual.inicio, len(self.models)):
            modelo = self.models[indice]
            configuracao = _com_prazo(model_settings, atual, len(self.models) - indice)
            try:
                resposta = await self._sozinhos[indice].request(
                    messages, configuracao, model_request_parameters
                )
            except FallbackExceptionGroup as grupo:
                falhas.extend(grupo.exceptions)
                tentativas.extend(grupo.attempts)
                # O sinal da troca: com a chave do principal expirada, todo o tráfego iria
                # para a reserva, e só o nome do modelo na auditoria mostraria isso.
                logger.warning(
                    'O modelo %s falhou (%s)%s',
                    modelo.model_name,
                    '; '.join(f'{type(falha).__name__}: {falha}' for falha in grupo.exceptions),
                    '; a chamada passa para a reserva.'
                    if indice + 1 < len(self.models)
                    else '; não há outra reserva.',
                )
                continue
            atual.respondeu(indice, modelo.model_name)
            if tentativas:
                resposta = replace(
                    resposta, failed_attempts=[*tentativas, *(resposta.failed_attempts or [])]
                )
            return resposta
        grupo = FallbackExceptionGroup('Todos os modelos da cadeia falharam', falhas)
        grupo.attempts = tentativas
        raise grupo


def _com_prazo(
    configuracao: ModelSettings | None, atual: Rodada, restantes: int
) -> ModelSettings | None:
    if atual.prazo is None:
        return configuracao
    # Sem tempo nenhum, o teto da rodada cancela a pergunta antes deste prazo.
    fatia = max(atual.prazo - anyio.current_time(), 0.001) / restantes
    configuracao = ModelSettings(**(configuracao or {}))
    configuracao['request_timeout'] = min(fatia, configuracao.get('request_timeout', fatia))
    return configuracao


def com_reserva(principal: Model, *reservas: Model) -> Model:
    """O principal e, se houver, as reservas em ordem (`ModeloComReserva`)."""
    return ModeloComReserva(principal, *reservas) if reservas else principal


def modelo_que_respondeu(atual: Rodada, configurado: Model) -> str:
    """Os modelos que de fato responderam, com o nome da configuração, e não o
    `fallback:...` da cadeia. Sem reserva, é o nome do modelo, como antes."""
    return ', '.join(atual.modelos) or configurado.model_name


def provedor_indisponivel(erro: Exception) -> ProvedorIndisponivel:
    """Com reserva, a falha traz o erro de cada modelo, com o nome dele: a mensagem de um
    timeout não diz de quem foi. A mensagem vai para a auditoria."""
    if isinstance(erro, FallbackExceptionGroup):
        return ProvedorIndisponivel(
            '; '.join(f'{getattr(falha, "model_name", "?")}: {falha}' for falha in erro.exceptions)
        )
    return ProvedorIndisponivel(str(erro))
