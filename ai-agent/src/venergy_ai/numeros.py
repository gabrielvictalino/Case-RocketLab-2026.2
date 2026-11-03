"""Validação de saída: todo número citado na resposta precisa estar nas linhas retornadas.

O redator recebe as linhas e escreve o texto, mas pode errar uma conta ou inventar
um valor. Aqui cada número do texto é comparado com os valores numéricos do
resultado, aceitando as formas comuns de escrever o mesmo valor:

- arredondamento ou truncamento para as casas mostradas (16,66 → "16,7" ou "16,6");
- percentual de uma razão, quando o texto usa % (0,167 → "16,7%");
- escala por extenso ou em MWh/GWh (1.234.567 → "1,2 milhão"; 351.234 kWh → "351 MWh");
- sinal implícito ("queda de 351" para −351). Com sinal explícito, o sinal precisa bater.

Não são conferidos: códigos (UC000123, ALM-REC-001), datas e competências (jun/2026,
2025-07), anos sozinhos e os números que o chamador permite, como os da pergunta,
o número de linhas e o número de meses do período.
"""

import re
from collections.abc import Iterable
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import NamedTuple

MESES = r'(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*\.?'
IGNORADOS = re.compile(
    '|'.join(
        (
            # Códigos com letras e dígitos: UC000123, ALM-REC-001, INSP-001, P0.
            r'\b[A-Za-z]+(?:-[A-Za-z0-9]+)*-?\d[\w-]*',
            # Datas e competências.
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b\d{4}-\d{2}(?:-\d{2})?\b',
            rf'\b{MESES}\s*/\s*\d{{2,4}}\b',
            rf'\b{MESES}\s+de\s+\d{{4}}\b',
        )
    ),
    re.IGNORECASE,
)
NUMERO = re.compile(
    r'(?<![\w,.])(?P<sinal>[-−+])?'
    r'(?P<numero>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d+|\d+)'
    r'(?!\w)'
    r'(?:\s*(?P<escala>%|mil\b|milh(?:ão|ões|ao|oes)\b|mi\b|bilh(?:ão|ões|ao|oes)\b|bi\b'
    r'|MWh\b|GWh\b))?',
    re.IGNORECASE,
)
# MWh e GWh entram como escala porque as views trazem energia em kWh.
ESCALAS = {
    'milh': Decimal(10) ** 6,
    'mil': Decimal(1000),
    'mi': Decimal(10) ** 6,
    'bilh': Decimal(10) ** 9,
    'bi': Decimal(10) ** 9,
    'mwh': Decimal(1000),
    'gwh': Decimal(10) ** 6,
}


class Leitura(NamedTuple):
    valor: Decimal
    # Unidade da última casa mostrada: 0,1 em "16,7"; 100.000 em "1,2 milhão".
    unidade: Decimal
    # −1 ou +1 quando o texto escreve o sinal; 0 quando não escreve.
    sinal: int
    percentual: bool


def numeros_sem_lastro(
    texto: str, linhas: Iterable[Iterable[object]], permitidos: Iterable[object] = ()
) -> list[str]:
    """Devolve os números do texto que não aparecem nas linhas, na ordem em que aparecem."""
    valores = [v for linha in linhas for v in map(_decimal, linha) if v is not None]
    valores += [v for v in map(_decimal, permitidos) if v is not None]
    sem_lastro = []
    for citado in NUMERO.finditer(IGNORADOS.sub(' ', texto)):
        leituras = _leituras(citado)
        if leituras and not any(_tem_lastro(leitura, valores) for leitura in leituras):
            sem_lastro.append(citado.group(0).strip())
    return sem_lastro


def numeros_citados(texto: str) -> list[Decimal]:
    """Os números de um texto, em todas as leituras. Os da pergunta viram `permitidos`."""
    return [leitura.valor for citado in NUMERO.finditer(texto) for leitura in _leituras(citado)]


def _decimal(valor: object) -> Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float | Decimal):
        return None
    try:
        decimal = Decimal(str(valor))
    except InvalidOperation:
        return None
    return decimal if decimal.is_finite() else None


def _leituras(citado: re.Match) -> list[Leitura]:
    numero, escala = citado['numero'], (citado['escala'] or '').lower()
    sinal = {'-': -1, '−': -1, '+': 1}.get(citado['sinal'] or '', 0)
    if not escala and not sinal and _e_ano(numero):
        return []
    # "1.234" é mil duzentos e trinta e quatro em português, mas pode ser um decimal
    # escrito em inglês. As duas leituras valem.
    textos = [numero.replace('.', '').replace(',', '.')]
    if re.fullmatch(r'\d+\.\d+', numero):
        textos.append(numero)
    multiplicador = next((m for p, m in ESCALAS.items() if escala.startswith(p)), Decimal(1))
    leituras = []
    for texto in textos:
        valor = Decimal(texto)
        unidade = Decimal(1).scaleb(valor.as_tuple().exponent) * multiplicador
        leituras.append(Leitura(valor * multiplicador, unidade.normalize(), sinal, escala == '%'))
    return leituras


def _e_ano(numero: str) -> bool:
    return re.fullmatch(r'\d{4}', numero) is not None and 1900 <= int(numero) <= 2100


def _tem_lastro(leitura: Leitura, valores: list[Decimal]) -> bool:
    # Com %, o resultado pode trazer o percentual pronto (16,7) ou a razão (0,167).
    fatores = (Decimal(1), Decimal(100)) if leitura.percentual else (Decimal(1),)
    for valor in valores:
        if leitura.sinal and valor and (valor > 0) != (leitura.sinal > 0):
            continue
        for fator in fatores:
            alvo = abs(valor * fator)
            if leitura.valor in (
                alvo.quantize(leitura.unidade, ROUND_HALF_UP),
                alvo.quantize(leitura.unidade, ROUND_DOWN),
            ):
                return True
    return False
