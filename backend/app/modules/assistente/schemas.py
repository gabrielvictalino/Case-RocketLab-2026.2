from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from venergy_ai.interface import Consulta, RespostaAgente

Recorte = Literal['municipio', 'bairro', 'classe', 'alimentador', 'id_uc']
ValorRecorte = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ContextoPergunta(BaseModel):
    """O que a tela envia junto com a pergunta. Períodos em `AAAA-MM..AAAA-MM`."""

    model_config = ConfigDict(extra='forbid')
    tela: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    periodo: str | None = None
    comparacao: str | None = None
    recortes: dict[Recorte, ValorRecorte] = Field(default_factory=dict)


class Pergunta(BaseModel):
    pergunta: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
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
