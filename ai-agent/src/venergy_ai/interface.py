"""Fronteira entre o agente e o backend: o que entra numa pergunta e o que sai na resposta.

O backend só conhece estes tipos. Ele monta o `Contexto` a partir da tela e da carga
publicada, e grava a `RespostaAgente` na auditoria pela conexão do portal, que o
agente nunca recebe.
"""

from datetime import date
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from venergy_ai.semantica.periodo import Periodo

LINHAS_EXIBIDAS = 50


class Contexto(BaseModel):
    """O que a tela sabe quando a pergunta é feita."""

    competencia_mais_recente: date
    tela: str | None = None
    # Período e comparação da tela: o padrão quando a pergunta não define período.
    periodo: Periodo | None = None
    comparacao: Periodo | None = None
    recortes: dict[str, str] = Field(default_factory=dict)


class PeriodoUsado(BaseModel):
    inicio: date
    fim: date
    descricao: str


class Consulta(BaseModel):
    """Uma tentativa: o SQL que o modelo escreveu e o que de fato rodou."""

    sql_gerado: str
    # Nulo quando a guarda rejeitou o SQL e nada foi executado.
    sql_executado: str | None = None
    colunas: list[str] = Field(default_factory=list)
    linhas: list[list[Any]] = Field(
        default_factory=list, description=f'Até {LINHAS_EXIBIDAS} linhas, para exibição.'
    )
    total_linhas: int = 0
    duracao_ms: int | None = None
    erro: str | None = None


class RespostaAgente(BaseModel):
    tipo: Literal['resposta', 'nao_sei']
    texto: str
    metrica: str | None = None
    periodo: PeriodoUsado | None = None
    # Preenchidos no "não sei": por que não respondeu e o que os dados permitem.
    motivo: str | None = None
    alternativa: str | None = None
    consultas: list[Consulta] = Field(default_factory=list)
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0


class ProvedorIndisponivel(RuntimeError):
    """O provedor do modelo falhou (rede, autenticação, cota ou erro do servidor)."""


class Assistente(Protocol):
    async def responder(self, pergunta: str, contexto: Contexto) -> RespostaAgente: ...
