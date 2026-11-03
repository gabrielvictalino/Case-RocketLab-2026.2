from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.modules.metricas import RespostaMetricas


class Efeitos(BaseModel):
    volume: Decimal
    reajuste: Decimal
    bandeira: Decimal
    mix: Decimal


class Variacao(BaseModel):
    receita_base: Decimal
    receita_atual: Decimal
    variacao: Decimal
    variacao_pct: Decimal | None
    volume_base_kwh: Decimal
    volume_atual_kwh: Decimal
    variacao_volume_kwh: Decimal
    variacao_volume_pct: Decimal | None


class Decomposicao(RespostaMetricas, Variacao):
    efeitos: Efeitos


class Local(Variacao):
    municipio: str
    bairro: str | None
    efeitos: Efeitos


class Locais(RespostaMetricas):
    itens: list[Local]
    total: Decomposicao


class Grupo(Variacao):
    grupo_uc: Literal['GD', 'IRREGULARIDADE_CONFIRMADA', 'DEMAIS']


class Grupos(RespostaMetricas):
    itens: list[Grupo]
