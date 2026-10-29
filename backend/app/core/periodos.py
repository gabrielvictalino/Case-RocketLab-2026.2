import re
from dataclasses import dataclass
from datetime import date

from app.core.errors import APIError


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    @classmethod
    def parse(cls, value: str):
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])\.\.\d{4}-(0[1-9]|1[0-2])', value):
            raise APIError(422, 'Use AAAA-MM..AAAA-MM', 'PERIODO_INVALIDO')
        try:
            inicio, fim = (date.fromisoformat(p + '-01') for p in value.split('..'))
        except ValueError:
            raise APIError(422, 'Competência inválida', 'PERIODO_INVALIDO') from None
        if inicio > fim:
            raise APIError(422, 'Início posterior ao fim', 'PERIODO_INVALIDO')
        return cls(inicio, fim)

    def dentro_da_base(self, minimo: date, maximo: date):
        if self.inicio < minimo or self.fim > maximo:
            raise APIError(422, 'Período fora da base disponível', 'PERIODO_FORA_DA_BASE')
        return self

    def comparacao_padrao(self):
        if self.inicio.year == 1:
            raise APIError(422, 'Não há ano anterior disponível', 'PERIODO_INVALIDO')
        return Periodo(
            self.inicio.replace(year=self.inicio.year - 1), self.fim.replace(year=self.fim.year - 1)
        )


def validar_periodos(periodo: str, comparacao: str | None, minimo: date, maximo: date):
    atual = Periodo.parse(periodo).dentro_da_base(minimo, maximo)
    if comparacao is not None:
        return atual, Periodo.parse(comparacao).dentro_da_base(minimo, maximo)
    if atual.inicio.year == 1:
        return atual, None
    anterior = atual.comparacao_padrao()
    # A ausência de um ano anterior completo não invalida o período solicitado.
    if anterior.inicio < minimo or anterior.fim > maximo:
        return atual, None
    return atual, anterior
