"""Validação de saída: todo número citado na resposta precisa estar nas linhas retornadas.

O redator recebe as linhas e escreve o texto, mas pode errar uma conta ou inventar
um valor. Aqui cada número do texto é comparado com os valores numéricos do
resultado, aceitando as formas comuns de escrever o mesmo valor:

- arredondamento para as casas mostradas (16,66 → "16,7"), e truncamento só quando o
  texto mostra dois dígitos significativos ou mais (16,66 → "16,6", mas "1 milhão" não
  vale para 1.999.999);
- percentual de uma razão, quando o texto usa % ou pp (0,167 → "16,7%");
- escala por extenso ou em MWh/GWh (1.234.567 → "1,2 milhão"; 351.234 kWh → "351 MWh"),
  ou o número sem a escala, quando o SQL já devolveu o valor nela (351,2 → "351,2 MWh");
- sinal implícito ("queda de 351" para −351). Com sinal explícito, o sinal precisa bater.
  Uma alta ("alta de 5,3%") não vale para um valor negativo, e uma queda não vale para
  um positivo, a não ser que a coluna seja o tamanho da queda (queda_pct, reducao_kwh).
  Em "caiu de X para Y", X e Y são níveis e não têm direção.

Todo número é conferido, mesmo colado à unidade ("351kWh", "R$1,2mi", "3,2h"). Não são
conferidos só os códigos (UC000123, ALM-REC-001), as datas e competências (jun/2026,
2025-07), os ordinais (1º) e os números que o chamador permite, como os anos do período,
o número de linhas e o número de meses. Os números da pergunta só valem como limiar
("acima de 30%"): repetidos como resultado, eles não têm lastro.
"""

import re
from collections.abc import Iterable, Iterator, Sequence
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
# O fim do trecho antes do número: no máximo uma palavra e o "R$" depois da palavra-chave.
ANTES_DO_NUMERO = r'(?:\s+\w+)?\s+(?:R\$\s*)?$'
# "alta de 5,3%", "cresceu 12", "aumento de R$ 1.234", "aumento de 3 pp".
ALTA = re.compile(
    r'\b(?:alta|aument\w*|cresc\w*|subi\w*|subida|elev\w*|ganho|avan[cç]\w*)' + ANTES_DO_NUMERO,
    re.IGNORECASE,
)
# "queda de 5,3%", "caiu 12", "redução de R$ 1.234". Fica de fora o que também é nível:
# "perdas de 351 kWh", "o mais baixo, 3,2 h", "energia recuperada de 125 kWh".
BAIXA = re.compile(
    r'\b(?:quedas?|ca[ií](?:u|ram|ndo|r)|redu[cçz]\w*|recu(?:o|ou|aram)|diminu\w*|retra\w*'
    r'|encolh\w*)' + ANTES_DO_NUMERO,
    re.IGNORECASE,
)
# A coluna que já é o tamanho da queda vem positiva.
COLUNA_DE_QUEDA = re.compile(r'qued|redu|dimin|perd|recuo|retra', re.IGNORECASE)
# "de X para Y": dois níveis, sem direção.
PARA = re.compile(r'\s*para\s', re.IGNORECASE)
# Limiares que a pergunta pode trazer e a resposta repetir: "acima de 30%", "pelo menos 3".
LIMIAR = re.compile(
    r'\b(?:acima|abaixo|mais|menos|maior(?:es)?|menor(?:es)?|superior(?:es)?|inferior(?:es)?'
    r'|at[eé]|m[ií]nimo|m[aá]ximo|pelo\s+menos|a\s+partir)(?:\s+(?:de|do|da|que|a))?\s+'
    r'(?:R\$\s*)?$',
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
    # O texto fala em queda: um valor positivo só serve se a coluna for a da queda.
    baixa: bool = False
    # Dígitos significativos mostrados: com menos de dois, só vale o arredondamento.
    significativos: int = 2


class Valor(NamedTuple):
    valor: Decimal
    # A coluna é o tamanho de uma queda (queda_pct): positiva, ela sustenta "queda de".
    de_queda: bool = False


def numeros_sem_lastro(
    texto: str,
    linhas: Iterable[Iterable[object]],
    permitidos: Iterable[object] = (),
    limiares: Iterable[object] = (),
    colunas: Iterable[str] = (),
) -> list[str]:
    """Devolve os números do texto que não aparecem nas linhas, na ordem em que aparecem.

    `permitidos` valem em qualquer lugar do texto; `limiares` (os números da pergunta) só
    logo depois de "acima de", "pelo menos" e afins. `colunas` são os nomes das colunas
    das linhas, para reconhecer a que já traz o tamanho de uma queda."""
    nomes = list(colunas)
    valores = [
        Valor(v, bool(COLUNA_DE_QUEDA.search(nomes[i])) if i < len(nomes) else False)
        for linha in linhas
        for i, item in enumerate(linha)
        for v in _decimais(item)
    ]
    # Um número permitido não é variação: sustenta a queda e a alta.
    valores += [Valor(v, True) for item in permitidos for v in _decimais(item)]
    dos_limiares = [Valor(v, True) for item in limiares for v in _decimais(item)]
    sem_lastro = []
    for trecho, leituras, limiar in _citados(texto):
        if not leituras or any(_tem_lastro(leitura, valores) for leitura in leituras):
            continue
        if limiar and any(_tem_lastro(leitura, dos_limiares) for leitura in leituras):
            continue
        sem_lastro.append(trecho)
    return sem_lastro


class Citacao(NamedTuple):
    # Como o número está escrito no texto.
    trecho: str
    # Posições, em `valores`, dos valores que sustentam o número. Vazia: sem lastro.
    lastros: list[int]


def citacoes(
    texto: str, valores: Sequence[object], permitidos: Iterable[object] = ()
) -> list[Citacao]:
    """Cada número do texto com os valores que o sustentam, para mostrar ao lado do texto.

    Um número igual a um dos `permitidos` (um ano, o número de meses) fica de fora. Os
    permitidos não valem por arredondamento: "R$ 0,00 milhões" não é o ano de 2024. Um
    número que nenhum valor sustenta vem com `lastros` vazia.
    """
    por_valor = [[Valor(v, True) for v in _decimais(valor)] for valor in valores]
    livres = {v for item in permitidos for v in _decimais(item)}
    resultado = []
    for trecho, leituras, _ in _citados(texto):
        if any(leitura.valor in livres for leitura in leituras):
            continue
        lastros = [
            i
            for i, decimais in enumerate(por_valor)
            if any(_tem_lastro(leitura, decimais) for leitura in leituras)
        ]
        resultado.append(Citacao(trecho, lastros))
    return resultado


def _citados(texto: str) -> Iterator[tuple[str, list[Leitura], bool]]:
    """Cada número do texto, com as leituras dele e se vem logo depois de um limiar."""
    limpo = IGNORADOS.sub(' ', texto)
    for citado in NUMERO.finditer(limpo):
        nivel = PARA.match(limpo, citado.end()) is not None
        alta = not nivel and ALTA.search(limpo, 0, citado.start()) is not None
        baixa = not nivel and BAIXA.search(limpo, 0, citado.start()) is not None
        limiar = LIMIAR.search(limpo, 0, citado.start()) is not None
        yield citado.group(0).strip().rstrip('.'), _leituras(citado, alta, baixa), limiar


def numeros_citados(texto: str) -> list[Decimal]:
    """Os números de um texto, em todas as leituras. Os da pergunta viram `limiares`."""
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


def _leituras(citado: re.Match, alta: bool = False, baixa: bool = False) -> list[Leitura]:
    numero, escala = citado['numero'], (citado['escala'] or '').lower()
    sinal = {'-': -1, '−': -1, '+': 1}.get(citado['sinal'] or '', 0)
    percentual = escala == '%' or escala.startswith('p')
    # "1.234" é mil duzentos e trinta e quatro em português, mas pode ser um decimal
    # escrito em inglês. As duas leituras valem.
    textos = [numero.replace('.', '').replace(',', '.')]
    if re.fullmatch(r'\d+\.\d+', numero):
        textos.append(numero)
    multiplicador = next((m for p, m in ESCALAS.items() if escala.startswith(p)), Decimal(1))
    # Com escala, vale também o número como está: o SQL pode já ter devolvido em MWh.
    multiplicadores = (multiplicador, Decimal(1)) if multiplicador != 1 else (multiplicador,)
    leituras = []
    for texto in textos:
        valor = Decimal(texto)
        significativos = len(valor.normalize().as_tuple().digits) if valor else 0
        for fator in multiplicadores:
            unidade = Decimal(1).scaleb(valor.as_tuple().exponent) * fator
            leituras.append(
                Leitura(
                    valor * fator,
                    unidade.normalize(),
                    sinal,
                    percentual,
                    alta,
                    baixa,
                    significativos,
                )
            )
    return leituras


def _tem_lastro(leitura: Leitura, valores: list[Valor]) -> bool:
    # Com % ou pp, o resultado pode trazer o percentual pronto (16,7) ou a razão (0,167).
    fatores = (Decimal(1), Decimal(100)) if leitura.percentual else (Decimal(1),)
    for valor, de_queda in valores:
        if leitura.sinal and valor and (valor > 0) != (leitura.sinal > 0):
            continue
        if leitura.alta and valor < 0:
            continue
        if leitura.baixa and valor > 0 and not de_queda:
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
            if leitura.valor == alvo.quantize(leitura.unidade, ROUND_HALF_UP):
                return True
            # Truncar "1.999.999" para "1 milhão" muda o valor pela metade; "16,6" não.
            return leitura.significativos >= 2 and leitura.valor == alvo.quantize(
                leitura.unidade, ROUND_DOWN
            )
        except InvalidOperation:
            return False
