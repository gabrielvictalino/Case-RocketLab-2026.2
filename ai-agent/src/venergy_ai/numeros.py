"""Validação de saída: todo número citado na resposta precisa estar nas linhas retornadas.

O redator recebe as linhas e escreve o texto, mas pode errar uma conta ou inventar
um valor. Aqui cada número do texto é comparado com os valores numéricos do
resultado, aceitando as formas comuns de escrever o mesmo valor:

- arredondamento para as casas mostradas (16,66 → "16,7"), e truncamento só quando o
  texto mostra dois dígitos significativos ou mais (16,66 → "16,6", mas "1 milhão" não
  vale para 1.999.999);
- percentual de uma razão, quando o texto usa % ou pp (0,167 → "16,7%");
- escala por extenso ou em MWh/GWh (1.234.567 → "1,2 milhão"; 351.234 kWh → "351 MWh").
  O número sem a escala só vale contra uma coluna que já está nela pelo nome
  (volume_mwh = 351,2 → "351,2 MWh"; receita_milhoes = 1,2 → "1,2 milhão"), nunca
  contra os números permitidos: "R$ 12 milhões" não se sustenta nos 12 meses do período;
- sinal implícito ("queda de 351" para −351). Com sinal explícito, o sinal precisa bater.
  Uma alta ("alta de 5,3%") não vale para um valor negativo, e uma queda não vale para
  um positivo, a não ser que a coluna seja o tamanho da queda (queda_pct, reducao_kwh).
  Em "caiu de X para Y", X e Y são níveis e não têm direção, como o Y de "caiu para Y"
  e o número de "queda em 33 UCs".

Todo número é conferido, mesmo colado à unidade ("351kWh", "R$1,2mi", "3,2h"). Não são
conferidos só os códigos (UC000123, ALM-REC-001), as datas e competências (jun/2026,
2025-07), os ordinais (1º) e os números que o chamador permite, como os anos do período,
o número de linhas e o número de meses. Os números da pergunta só valem no papel que
tinham nela, de limiar ("acima de 30%", "3 ou mais"), seleção ("os 10 bairros") ou
período ("últimos 3 anos"): repetidos como resultado, eles não têm lastro.
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
# A escala escrita no texto e quanto ela multiplica o número. MWh e GWh entram como escala
# porque a unidade comum da energia é o kWh, a das views.
ESCALAS = {
    'milh': Decimal(10) ** 6,
    'mil': Decimal(1000),
    'mi': Decimal(10) ** 6,
    'bilh': Decimal(10) ** 9,
    'bi': Decimal(10) ** 9,
    'mwh': Decimal(1000),
    'gwh': Decimal(10) ** 6,
}
# A coluna que já está numa escala diz isso no nome (volume_mwh, receita_milhoes, ucs_mil),
# e o valor dela é multiplicado por ela. Texto e coluna são comparados na mesma unidade:
# 351,2 em volume_mwh são 351.200 kWh, e só "351,2 MWh" ou "351.200 kWh" os descrevem.
ESCALA_DA_COLUNA = (
    (re.compile(r'milh(?:ao|oes|ão|ões)|(?:^|_)mi(?:_|$)', re.IGNORECASE), Decimal(10) ** 6),
    (re.compile(r'(?:^|_)mil(?:_|$)|milhares', re.IGNORECASE), Decimal(1000)),
    (re.compile(r'bilh(?:ao|oes|ão|ões)|(?:^|_)bi(?:_|$)', re.IGNORECASE), Decimal(10) ** 9),
    (re.compile(r'mwh', re.IGNORECASE), Decimal(1000)),
    (re.compile(r'gwh', re.IGNORECASE), Decimal(10) ** 6),
)
# O fim do trecho antes do número: no máximo uma palavra e o "R$" depois da palavra-chave.
# A palavra não pode ser "para", "em", "a" e afins: em "caiu para 351" e "queda em 33 UCs",
# o número é o nível final ou uma contagem, não o tamanho da variação.
ANTES_DO_NUMERO = r'(?:\s+(?!(?:para|pra|em|a|at[eé]|ao|à|no|na|nos|nas)\b)\w+)?\s+(?:R\$\s*)?$'
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
# Uma coluna em percentual já vem multiplicada por 100 (taxa_pct = 7,42): "742%" não sai dela.
COLUNA_EM_PERCENTUAL = re.compile(r'pct|percent', re.IGNORECASE)
# Um ano só é o ano quando o texto fala de tempo: "em 2025", "de 2024 para 2025". Em
# "São 2025 UCs", é uma contagem, e precisa estar nas linhas.
ANTES_DO_ANO = re.compile(
    r'(?:\b(?:em|de|do|da|desde|at[eé]|entre|e|a|ao|ante|contra|ano|anos|no|na|para|versus'
    r'|vs\.?)\s+|[/(]\s*|^\s*|[.;:!?]\s+)$',
    re.IGNORECASE,
)
DEPOIS_DO_ANO = re.compile(
    r'\s*(?:%|p\.?p\.?|R\$|[kMG]?Wh|kW\b|h\b|horas?\b|mil\b|milh|bilh|UCs?\b|unidades\b'
    r'|clientes\b|consumidores\b|faturas\b|bairros\b|munic|alimentadores\b|inspe|ocorr'
    r'|interrup|atendimentos\b|reclama|protocolos\b)',
    re.IGNORECASE,
)
# A coluna que já é o tamanho da queda vem positiva. "perd" fica de fora: perdas_kwh e
# perda_pct costumam ser o nível de perdas, não uma variação.
COLUNA_DE_QUEDA = re.compile(r'qued|redu|dimin|recuo|retra', re.IGNORECASE)
# "de X para Y": dois níveis, sem direção. Entre o X e o "para" pode vir a unidade
# ("de 400 kWh para 351 kWh"), e depois do "para" vem o outro número.
PARA = re.compile(r'\s*(?:[^\W\d]+\s*)?para\s+(?:R\$\s*)?[-−+]?\d', re.IGNORECASE)
# Limiares que a pergunta pode trazer e a resposta repetir: "acima de 30%", "pelo menos 3".
LIMIAR = re.compile(
    r'\b(?:acima|abaixo|mais|menos|maior(?:es)?|menor(?:es)?|superior(?:es)?|inferior(?:es)?'
    r'|at[eé]|m[ií]nimo|m[aá]ximo|pelo\s+menos|a\s+partir)(?:\s+(?:de|do|da|que|a))?\s+'
    r'(?:R\$\s*)?$',
    re.IGNORECASE,
)
# Os outros papéis de um número da pergunta, além do limiar. Antes dele: seleção e período
# ("os 10 bairros", "top 5", "últimos 3 anos"). Depois dele: limiar ("3 ou mais"),
# ranking ("5 piores") e duração ("12 meses", "3 anos").
SELECAO_ANTES = re.compile(
    r'\b(?:os|as|dos|das|nos|nas|aos|às|top|primeir[oa]s|[uú]ltim[oa]s)\s+$', re.IGNORECASE
)
PAPEL_DEPOIS = re.compile(
    r'\s*(?:%|p\.?p\.?)?\s*(?:ou\s+(?:mais|menos|acima|abaixo)\b'
    r'|(?:maiores|menores|piores|melhores|primeir[oa]s|[uú]ltim[oa]s)\b'
    r'|(?:m[eê]s(?:es)?|anos?|dias|semanas|trimestres|semestres)\b)',
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
    # Um ano escrito em contexto de tempo ("em 2025"): só esta leitura é sustentada por
    # um ano permitido ou pelo ano de uma data das linhas.
    no_tempo: bool = False


class Valor(NamedTuple):
    valor: Decimal
    # A coluna é o tamanho de uma queda (queda_pct): positiva, ela sustenta "queda de".
    de_queda: bool = False
    # A escala em que a coluna já está, pelo nome: 1.000 em volume_mwh. O valor é
    # comparado multiplicado por ela, na mesma unidade da leitura.
    fator: Decimal = Decimal(1)
    # O valor pode ser uma razão, que o texto escreve vezes 100 com % (0,167 → "16,7%").
    # Falso numa coluna em percentual e nos fatos dos insights, que já vêm em %.
    razao: bool = True
    # Um ano (permitido ou de uma data das linhas): só sustenta um ano em contexto de tempo.
    ano: bool = False


class Citado(NamedTuple):
    """Um número do texto, com onde ele está e o que vem em volta."""

    trecho: str
    leituras: list[Leitura]
    # Posição do trecho no texto original: o frontend destaca por ela, sem procurar.
    inicio: int
    fim: int
    # Com papel de limiar ("acima de", "3 ou mais"), seleção ("os 10") ou período
    # ("últimos 3 anos"): onde um número da pergunta pode ser repetido.
    limiar: bool
    # A unidade escrita junto do número: %, pp, R$, kWh ou h. None quando não há.
    unidade: str | None
    # O texto logo depois do número, para reconhecer "12 meses".
    depois: str


class Citacao(NamedTuple):
    trecho: str
    # Posições, em `valores`, dos valores que sustentam o número. Vazia: sem lastro.
    lastros: list[int]
    inicio: int
    fim: int
    unidade: str | None


def numeros_sem_lastro(
    texto: str,
    linhas: Iterable[Iterable[object]],
    permitidos: Iterable[object] = (),
    limiares: Iterable[object] = (),
    colunas: Iterable[str] = (),
) -> list[str]:
    """Devolve os números do texto que não aparecem nas linhas, na ordem em que aparecem.

    `permitidos` valem em qualquer lugar do texto; `limiares` (os números da pergunta que
    têm papel de limiar, seleção ou período, ver `numeros_da_pergunta`) só num desses
    papéis. `colunas` são os nomes das colunas das linhas, para reconhecer a que já traz
    o tamanho de uma queda e a que já está numa escala."""
    nomes = list(colunas)
    valores = [
        _valor_da_coluna(v, nomes[i] if i < len(nomes) else '', isinstance(item, str))
        for linha in linhas
        for i, item in enumerate(linha)
        for v in _decimais(item)
    ]
    # Um número permitido não é variação: sustenta a queda e a alta. Um ano permitido só
    # vale como ano ("em 2025"), não como contagem ("2025 UCs").
    valores += [Valor(v, True, ano=_parece_ano(v)) for item in permitidos for v in _decimais(item)]
    dos_limiares = [Valor(v, True) for item in limiares for v in _decimais(item)]
    sem_lastro = []
    for citado in _citados(texto):
        if not citado.leituras or _algum_lastro(citado, valores):
            continue
        if citado.limiar and _algum_lastro(citado, dos_limiares):
            continue
        sem_lastro.append(citado.trecho)
    return sem_lastro


def _algum_lastro(citado: Citado, valores: list[Valor]) -> bool:
    return any(_tem_lastro(leitura, valores) for leitura in citado.leituras)


def _valor_da_coluna(valor: Decimal, coluna: str, de_data: bool = False) -> Valor:
    fator = max((f for padrao, f in ESCALA_DA_COLUNA if padrao.search(coluna)), default=None)
    return Valor(
        valor,
        bool(COLUNA_DE_QUEDA.search(coluna)),
        fator or Decimal(1),
        razao=not COLUNA_EM_PERCENTUAL.search(coluna),
        # O ano de uma data das linhas ("2025-07-01") só sustenta o ano do texto.
        ano=de_data,
    )


def _parece_ano(valor: Decimal) -> bool:
    return valor == valor.to_integral_value() and 1900 <= valor <= 2100


def citacoes(
    texto: str, valores: Sequence[object], permitidos: Iterable[object] = ()
) -> list[Citacao]:
    """Cada número do texto com os valores que o sustentam, para mostrar ao lado do texto.

    Um número igual a um dos `permitidos` (um ano, o número de meses) fica de fora. Os
    permitidos não valem por arredondamento: "R$ 0,00 milhões" não é o ano de 2024, nem
    com a escala escrita: "R$ 12 milhões" não é o número de meses. Um número que nenhum
    valor sustenta vem com `lastros` vazia.
    """
    por_valor = [[Valor(v, True) for v in _decimais(valor)] for valor in valores]
    livres = {v for item in permitidos for v in _decimais(item)}
    resultado = []
    for citado in _citados(texto):
        if any(leitura.valor in livres for leitura in citado.leituras):
            continue
        lastros = [
            i
            for i, decimais in enumerate(por_valor)
            if any(_tem_lastro(leitura, decimais) for leitura in citado.leituras)
        ]
        resultado.append(Citacao(citado.trecho, lastros, citado.inicio, citado.fim, citado.unidade))
    return resultado


def _citados(texto: str, nomes: Iterable[str] = ()) -> Iterator[Citado]:
    # Trocar por espaços do mesmo tamanho mantém as posições do texto original.
    limpo = IGNORADOS.sub(lambda m: ' ' * len(m.group(0)), texto)
    for nome in sorted({n for n in nomes if n}, key=len, reverse=True):
        limpo = re.sub(re.escape(nome), lambda m: ' ' * len(m.group(0)), limpo, flags=re.I)
    for citado in NUMERO.finditer(limpo):
        antes = limpo[: citado.start()]
        nivel = PARA.match(limpo, citado.end()) is not None
        alta = not nivel and ALTA.search(antes) is not None
        baixa = not nivel and BAIXA.search(antes) is not None
        trecho = citado.group(0).strip().rstrip('.')
        no_tempo = (
            re.fullmatch(r'\d{4}', citado.group(0).strip()) is not None
            and ANTES_DO_ANO.search(antes) is not None
            and DEPOIS_DO_ANO.match(limpo, citado.end()) is None
        )
        yield Citado(
            trecho,
            _leituras(citado, alta, baixa, no_tempo),
            citado.start(),
            citado.start() + len(trecho),
            _tem_papel(limpo, citado),
            _unidade(citado, antes, limpo[citado.end() :]),
            limpo[citado.end() : citado.end() + 12],
        )


def _unidade(citado: re.Match, antes: str, depois: str) -> str | None:
    escala = (citado['escala'] or '').lower()
    if escala == '%':
        return '%'
    if escala.startswith('p'):
        return 'pp'
    if re.search(r'R\$\s*$', antes):
        return 'R$'
    if escala in ('mwh', 'gwh') or re.match(r'\s*kWh', depois, re.I):
        return 'kWh'
    if re.match(r'\s*(?:h\b|horas?\b)', depois, re.I):
        return 'h'
    return None


def _tem_papel(limpo: str, citado: re.Match) -> bool:
    return (
        LIMIAR.search(limpo, 0, citado.start()) is not None
        or SELECAO_ANTES.search(limpo, 0, citado.start()) is not None
        or PAPEL_DEPOIS.match(limpo, citado.end()) is not None
    )


def numeros_citados(texto: str) -> list[Decimal]:
    """Os números de um texto, em todas as leituras."""
    return [leitura.valor for citado in NUMERO.finditer(texto) for leitura in _leituras(citado)]


def numeros_da_pergunta(pergunta: str) -> list[Decimal]:
    """Os números da pergunta que a resposta pode repetir: os de limiar ("acima de 30%",
    "3 ou mais"), de seleção ("os 10 bairros", "5 piores") e de período ("últimos 3
    anos"). Um número afirmado na pergunta ("a receita foi R$ 9.876.543,21?") fica de
    fora: repetido, ele sairia como se viesse da consulta."""
    limpo = IGNORADOS.sub(' ', pergunta)
    return [
        leitura.valor
        for citado in NUMERO.finditer(limpo)
        if _tem_papel(limpo, citado)
        for leitura in _leituras(citado)
    ]


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


def _leituras(
    citado: re.Match, alta: bool = False, baixa: bool = False, no_tempo: bool = False
) -> list[Leitura]:
    numero, escala = citado['numero'], (citado['escala'] or '').lower()
    sinal = {'-': -1, '−': -1, '+': 1}.get(citado['sinal'] or '', 0)
    percentual = escala == '%' or escala.startswith('p')
    # "1.234" é mil duzentos e trinta e quatro em português, mas pode ser um decimal
    # escrito em inglês. As duas leituras valem.
    textos = [numero.replace('.', '').replace(',', '.')]
    if re.fullmatch(r'\d+\.\d+', numero):
        textos.append(numero)
    fator = next((m for p, m in ESCALAS.items() if escala.startswith(p)), Decimal(1))
    # Os algarismos como estão escritos: "20,0" mostra três, e o truncamento vale.
    significativos = len(re.sub(r'\D', '', numero).lstrip('0'))
    leituras = []
    for texto in textos:
        valor = Decimal(texto)
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
                no_tempo,
            )
        )
    return leituras


def _tem_lastro(leitura: Leitura, valores: list[Valor]) -> bool:
    for valor, de_queda, escala, razao, ano in valores:
        if ano and not leitura.no_tempo:
            continue
        valor *= escala
        # Com % ou pp, o resultado pode trazer o percentual pronto (16,7) ou a razão
        # (0,167), a não ser que o valor já esteja em percentual.
        fatores = (Decimal(1), Decimal(100)) if leitura.percentual and razao else (Decimal(1),)
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
