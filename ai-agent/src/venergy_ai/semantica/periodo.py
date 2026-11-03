"""Período padrão das respostas: os últimos 12 meses até a competência mais recente."""

from dataclasses import dataclass
from datetime import date

MESES_PERIODO_PADRAO = 12
MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')


def deslocar(competencia: date, meses: int) -> date:
    indice = competencia.year * 12 + competencia.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    @property
    def descricao(self) -> str:
        return f'{rotulo(self.inicio)} a {rotulo(self.fim)}'


def rotulo(competencia: date) -> str:
    return f'{MESES[competencia.month - 1]}/{competencia.year}'


def periodo_padrao(competencia_mais_recente: date) -> Periodo:
    """Últimos 12 meses, contados de trás para a frente a partir da competência mais recente."""
    fim = competencia_mais_recente.replace(day=1)
    return Periodo(deslocar(fim, 1 - MESES_PERIODO_PADRAO), fim)


def periodo_comparacao(periodo: Periodo, inicio_base: date | None = None) -> Periodo | None:
    """O mesmo intervalo no ano anterior, como no glossário. Como no backend
    (`validar_periodos`), não há comparação quando ele começa antes da base."""
    anterior = Periodo(deslocar(periodo.inicio, -12), deslocar(periodo.fim, -12))
    if inicio_base is not None and anterior.inicio < inicio_base.replace(day=1):
        return None
    return anterior
