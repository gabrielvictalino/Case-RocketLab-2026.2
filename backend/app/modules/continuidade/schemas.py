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


class PontoContinuidade(Indicadores):
    competencia: date


class SeriePeriodo(BaseModel):
    totais: Indicadores
    serie: list[PontoContinuidade]


class Serie(RespostaMetricas, SeriePeriodo):
    sem_evento_atipico: bool
    dados_comparacao: SeriePeriodo | None


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
    ranking_comparacao: list[Alimentador] | None
