from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.modules.metricas import RespostaMetricas

Ordem = Literal['chi', 'dec', 'fec']


class Indicadores(BaseModel):
    chi: Decimal | None
    interrupcoes: int | None
    numero_ucs: int | None
    dec: Decimal | None
    fec: Decimal | None


class PontoSerie(Indicadores):
    competencia: date


class Serie(RespostaMetricas):
    sem_evento_atipico: bool
    totais: Indicadores
    serie: list[PontoSerie]


class Causa(BaseModel):
    causa: str
    ocorrencias: int
    interrupcoes: int


class Alimentador(Indicadores):
    alimentador: str
    municipio: str
    causas: list[Causa]


class Ranking(RespostaMetricas):
    sem_evento_atipico: bool
    ordem: Ordem
    ranking: list[Alimentador]
