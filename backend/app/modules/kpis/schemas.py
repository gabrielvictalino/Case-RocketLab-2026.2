from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.modules.metricas import RespostaMetricas


class Indicador(BaseModel):
    valor: Decimal | None
    comparacao: Decimal | None
    variacao: Decimal | None
    variacao_pct: Decimal | None


class UCs(BaseModel):
    ativas: Indicador
    com_gd: Indicador


class Continuidade(BaseModel):
    dec: Indicador
    fec: Indicador


class KPIs(RespostaMetricas):
    receita: Indicador
    receita_arrecadada: Indicador
    volume_faturado_kwh: Indicador
    tarifa_media: Indicador
    inadimplencia: Indicador
    ucs: UCs
    continuidade: Continuidade
    taxa_acerto: Indicador


class PontoSerie(BaseModel):
    competencia: date
    receita: Decimal | None
    volume_faturado_kwh: Decimal | None


class Serie(RespostaMetricas):
    serie: list[PontoSerie]
