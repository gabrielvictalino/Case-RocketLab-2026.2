from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from venergy_ai.interface import Consulta, RespostaAgente

# Telas do portal, com o nome que vai para o agente.
TELAS = {
    'visao-geral': 'Visão Geral',
    'receita': 'Receita',
    'unidade-consumidora': 'Unidade Consumidora',
    'perdas': 'Perdas',
    'operacao': 'Operação',
}
Tela = Literal['visao-geral', 'receita', 'unidade-consumidora', 'perdas', 'operacao']
Recorte = Literal['municipio', 'bairro', 'classe', 'alimentador', 'id_uc']
# Nomes de lugar, classes e códigos: sem aspas, quebras de linha, < nem >, que o modelo
# poderia ler como instrução.
ValorRecorte = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[\w .,'()/-]+$"
    ),
]


class ContextoPergunta(BaseModel):
    """O que a tela envia junto com a pergunta. Períodos em `AAAA-MM..AAAA-MM`."""

    model_config = ConfigDict(extra='forbid')
    tela: Tela | None = None
    periodo: str | None = None
    comparacao: str | None = None
    recortes: dict[Recorte, ValorRecorte] = Field(default_factory=dict)


class Pergunta(BaseModel):
    # O Postgres recusa NUL em text: sem esta trava, a pergunta iria ao LLM e só falharia
    # no INSERT da auditoria, com um 500 e sem linha auditada.
    pergunta: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=1000, pattern=r'^[^\x00]*$'
        ),
    ]
    conversa_id: UUID | None = None
    contexto: ContextoPergunta = Field(default_factory=ContextoPergunta)


class RespostaPergunta(RespostaAgente):
    id_resposta: UUID
    conversa_id: UUID


class Auditoria(BaseModel):
    id_resposta: UUID
    conversa_id: UUID
    usuario: str
    pergunta: str
    contexto: dict[str, Any]
    consultas: list[Consulta]
    sql_gerado: str | None
    sql_executado: str | None
    numero_linhas: int | None
    resposta: str | None
    nao_sei: bool
    motivo: str | None
    modelo: str | None
    tokens_entrada: int | None
    tokens_saida: int | None
    latencia_ms: int
    erro: str | None
    criado_em: datetime
