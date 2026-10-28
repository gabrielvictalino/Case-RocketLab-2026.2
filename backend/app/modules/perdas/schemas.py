from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

UC = Annotated[str, StringConstraints(pattern=r'^UC\d{6}$')]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Inspetor = Annotated[str, StringConstraints(pattern=r'^INSP-(00[1-9]|0[1-3][0-9]|040)$')]
Energia = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class Status(StrEnum):
    ABERTA = 'ABERTA'
    EM_CAMPO = 'EM_CAMPO'
    CONCLUIDA = 'CONCLUIDA'
    CANCELADA = 'CANCELADA'


class CriarOrdens(BaseModel):
    ucs: list[UC] = Field(min_length=1, max_length=100)


class Despacho(BaseModel):
    inspetor: Inspetor


class Tentativa(BaseModel):
    observacao: Texto


class Cancelamento(BaseModel):
    motivo: Texto


class Resultado(BaseModel):
    resultado: Literal['IRREGULARIDADE CONFIRMADA', 'SEM IRREGULARIDADE']
    tipo_irregularidade: Texto | None = None
    kwh_recuperado: Energia
    data: date

    @model_validator(mode='after')
    def coerencia(self):
        if self.resultado == 'IRREGULARIDADE CONFIRMADA':
            if not self.tipo_irregularidade or self.kwh_recuperado <= 0:
                raise ValueError('Irregularidade exige tipo e kWh recuperado > 0')
        elif self.kwh_recuperado != 0 or self.tipo_irregularidade is not None:
            raise ValueError('Sem irregularidade exige kWh = 0 e tipo nulo')
        return self


class Ordem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    id_uc: str
    status: Status
    score: Decimal
    motivos: list[str]
    energia_recuperar_kwh: Decimal
    energia_recuperar_reais: Decimal
    inspetor: str | None
    resultado: str | None
    tipo_irregularidade: str | None
    kwh_recuperado: Decimal | None
    motivo_cancelamento: str | None
    criado_por: UUID
    atualizado_por: UUID
    criado_em: datetime
    atualizado_em: datetime


class Rejeitada(BaseModel):
    id_uc: str
    motivo: str


class Lote(BaseModel):
    criadas: list[Ordem]
    rejeitadas: list[Rejeitada]


class PaginaOrdens(BaseModel):
    items: list[Ordem]
    total: int
    page: int
    size: int
