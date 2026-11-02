from decimal import Decimal

from pydantic import BaseModel

from app.core.metricas import RespostaMetricas


class TotaisReceita(BaseModel):
    receita: Decimal | None
    receita_arrecadada: Decimal | None
    volume_faturado_kwh: Decimal | None
    componente_tarifa_reais: Decimal | None
    componente_bandeira_reais: Decimal | None


class EfeitosReceita(BaseModel):
    volume: Decimal
    reajuste: Decimal
    bandeira: Decimal
    mix: Decimal


class Decomposicao(RespostaMetricas):
    atual: TotaisReceita
    anterior: TotaisReceita | None
    variacao: Decimal | None
    efeitos: EfeitosReceita | None
