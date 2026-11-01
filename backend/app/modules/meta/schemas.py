from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class Filtros(BaseModel):
    municipios: list[str]
    bairros: dict[str, list[str]]
    classes: list[str]
    alimentadores: list[str]


class Carga(BaseModel):
    id: UUID
    batch_id: str
    versao_contrato: str
    sintetica: bool
    carregado_em: datetime
    competencia_inicial: date
    competencia_mais_recente: date
