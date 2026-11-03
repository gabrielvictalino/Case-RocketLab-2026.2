"""Validação de saída: todo número citado na resposta precisa estar nas linhas retornadas.

O redator recebe as linhas e escreve o texto, mas pode errar uma conta ou inventar
um valor. Aqui cada número do texto é comparado com os valores numéricos do
resultado, aceitando as formas comuns de escrever o mesmo valor:

- arredondamento ou truncamento para as casas mostradas (16,66 → "16,7" ou "16,6");
- percentual de uma razão, quando o texto usa % ou pp (0,167 → "16,7%");
- escala por extenso ou em MWh/GWh (1.234.567 → "1,2 milhão"; 351.234 kWh → "351 MWh");
- sinal implícito ("queda de 351" para −351). Com sinal explícito, o sinal precisa bater,
  e uma alta ("alta de 5,3%") não vale para um valor negativo.

Todo número é conferido, mesmo colado à unidade ("351kWh", "R$1,2mi", "3,2h"). Não são
conferidos só os códigos (UC000123, ALM-REC-001), as datas e competências (jun/2026,
2025-07), os ordinais (1º) e os números que o chamador permite, como os da pergunta,
os anos do período, o número de linhas e o número de meses.
"""

import re
from collections.abc import Iterable
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import NamedTuple

MESES = (
    r'(?:janeiro|jan|fevereiro|fev|março|marco|mar|abril|abr|maio|mai|junho|jun|julho|jul'
    r'|agosto|ago|setembro|set|outubro|out|novembro|nov|dezembro|dez)\b\.?'
)
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
            # Ordinais: a posição num ranking não é um valor do resultado.
            r'\b\d{1,2}[ºª°]',
        )
    ),
    re.IGNORECASE,
)
# Sem limite de palavra à direita: "351kWh" e "R$1,2mi" também são conferidos. A escala
# só vale quando não continua numa palavra ("12 minutos" não é "12 mi").
NUMERO = re.compile(
    r'(?<![\w,.])(?P<sinal>[-−+])?'
    r'(?P<numero>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d+|\d+)'
    r'(?:\s*(?P<escala>%|p\.?p\.?(?![^\W\d_])|(?:milh(?:ão|ões|ao|oes)|mil|mi'
    r'|bilh(?:ão|ões|ao|oes)|bi|MWh|GWh)(?![^\W\d_])))?',
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
# Palavras de alta logo antes do número: "alta de 5,3%", "cresceu 12", "aumento de 3 pp".
ALTA = re.compile(
    r'\b(?:alta|aument\w*|cresc\w*|subi\w*|subida|elev\w*|ganho|avan[cç]\w*)(?:\s+\w+)?\s+$',
    re.IGNORECASE,
)
DATA = re.compile(r'(\d{4})-\d{2}(?:-\d{2})?')


class Leitura(NamedTuple):
    valor: Decimal
    # Unidade da última casa mostrada: 0,1 em "16,7"; 100.000 em "1,2 milhão".
    unidade: Decimal
    # −1 ou +1 quando o texto escreve o sinal; 0 quando não escreve.
    sinal: int
    percentual: bool
    # O texto fala em alta logo antes do número: um valor negativo não serve.
    alta: bool = False


def numeros_sem_lastro(
    texto: str, linhas: Iterable[Iterable[object]], permitidos: Iterable[object] = ()
) -> list[str]:
    """Devolve os números do texto que não aparecem nas linhas, na ordem em que aparecem."""
    valores = [v for linha in linhas for item in linha for v in _decimais(item)]
    valores += [v for item in permitidos for v in _decimais(item)]
    limpo = IGNORADOS.sub(' ', texto)
    sem_lastro = []
    for citado in NUMERO.finditer(limpo):
        alta = ALTA.search(limpo, 0, citado.start()) is not None
        leituras = _leituras(citado, alta)
        if leituras and not any(_tem_lastro(leitura, valores) for leitura in leituras):
            sem_lastro.append(citado.group(0).strip().rstrip('.'))
    return sem_lastro


def numeros_citados(texto: str) -> list[Decimal]:
    """Os números de um texto, em todas as leituras. Os da pergunta viram `permitidos`."""
    return [leitura.valor for citado in NUMERO.finditer(texto) for leitura in _leituras(citado)]


def _decimais(valor: object) -> list[Decimal]:
    # Uma data nas linhas ("2025-07-01") deixa o texto citar o ano dela.
    if isinstance(valor, str):
        return [Decimal(ano) for ano in DATA.findall(valor)]
    if isinstance(valor, bool) or not isinstance(valor, int | float | Decimal):
        return []
    try:
        decimal = Decimal(str(valor))
    except InvalidOperation:
        return []
    return [decimal] if decimal.is_finite() else []


def _leituras(citado: re.Match, alta: bool = False) -> list[Leitura]:
    numero, escala = citado['numero'], (citado['escala'] or '').lower()
    sinal = {'-': -1, '−': -1, '+': 1}.get(citado['sinal'] or '', 0)
    percentual = escala == '%' or escala.startswith('p')
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
        leituras.append(
            Leitura(valor * multiplicador, unidade.normalize(), sinal, percentual, alta)
        )
    return leituras


def _tem_lastro(leitura: Leitura, valores: list[Decimal]) -> bool:
    # Com % ou pp, o resultado pode trazer o percentual pronto (16,7) ou a razão (0,167).
    fatores = (Decimal(1), Decimal(100)) if leitura.percentual else (Decimal(1),)
    for valor in valores:
        if leitura.sinal and valor and (valor > 0) != (leitura.sinal > 0):
            continue
        if leitura.alta and valor < 0:
            continue
        for fator in fatores:
            if _arredonda_para(leitura, abs(valor * fator)):
                return True
    return False


def _arredonda_para(leitura: Leitura, alvo: Decimal) -> bool:
    # Um valor grande com uma fração longa no texto passa dos 28 dígitos padrão.
    with localcontext() as contexto:
        contexto.prec = 60
        try:
            return leitura.valor in (
                alvo.quantize(leitura.unidade, ROUND_HALF_UP),
                alvo.quantize(leitura.unidade, ROUND_DOWN),
            )
        except InvalidOperation:
            return False
