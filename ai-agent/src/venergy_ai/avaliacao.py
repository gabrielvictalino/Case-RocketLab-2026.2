"""Avaliação automatizada do agente: perguntas com o resultado esperado.

Cada caso traz a pergunta e o que se espera dela:

- `sql`: a consulta de referência. O resultado dela é comparado com o da consulta que o
  agente rodou, e não o texto nem o SQL literal. Cada linha esperada precisa aparecer
  numa linha do agente: os textos iguais (sem diferenciar maiúsculas), os inteiros iguais
  e os demais números com 0,5% (ou 0,05, o arredondamento de uma casa) de diferença,
  aceitando sinal trocado e fator de 100 ou 1.000 (percentual, MWh);
- `nao_sei: true`: o agente deve dizer que não sabe;
- `periodo` (`AAAA-MM..AAAA-MM`): o período que a resposta precisa declarar;
- `ordem: true`: num ranking, as linhas esperadas são as primeiras do agente, na ordem.

Toda resposta é conferida também contra número inventado, com uma regra própria, mais
estrita que a do agente e independente dela: se a avaliação usasse a mesma conferência,
toda resposta já teria passado nela, e um furo do validador nunca apareceria. Aqui, cada
número do texto precisa sair de um valor das linhas que o redator recebeu só por
arredondamento nas casas mostradas, com o número e a coluna na mesma unidade (a escala
escrita multiplica o número, e a escala do nome da coluna, como volume_mwh, multiplica o
valor dela) e o % como valor pronto ou razão. Fora das linhas, valem só os metadados na
posição em que são metadados: o número de linhas, os meses do período seguidos de
"meses", um ano do período ou da comparação depois de "em", "de", "até" e afins e sem
unidade depois, e um número da pergunta no mesmo contexto em que ela o usou ("os 10
bairros", "acima de 30%").
O relatório traz a taxa de acerto, a de "não sei" correto e a latência média.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from venergy_ai.guarda_sql import LIMITE_MAXIMO
from venergy_ai.interface import (
    Assistente,
    Consulta,
    Contexto,
    ProvedorIndisponivel,
    RespostaAgente,
)
from venergy_ai.numeros import IGNORADOS
from venergy_ai.semantica import Periodo

TOLERANCIA = Decimal('0.005')
# Meia unidade da primeira casa: 16,7 contra 16,66.
TOLERANCIA_ABSOLUTA = Decimal('0.051')
FATORES = (Decimal(1), Decimal(100), Decimal('0.01'), Decimal(1000), Decimal('0.001'))

# A conferência própria da avaliação. Só o formato brasileiro (1.234,5), como o redator é
# instruído a escrever, e a escala colada ou não ao número.
NUMERO = re.compile(
    r'(?<![\w,.])(?P<numero>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)'
    r'(?:\s*(?P<escala>%|p\.?p\.?(?![^\W\d_])|(?:milh(?:ão|ões|ao|oes)|mil|mi'
    r'|bilh(?:ão|ões|ao|oes)|bi|MWh|GWh)(?![^\W\d_])))?',
    re.IGNORECASE,
)
# A escala escrita, o multiplicador e como uma coluna já nela se chama.
ESCALAS = (
    ('milh', Decimal(10) ** 6, r'milh(?:ao|oes|ão|ões)|(?:^|_)mi(?:_|$)'),
    ('mil', Decimal(1000), r'(?:^|_)mil(?:_|$)|milhares'),
    ('mi', Decimal(10) ** 6, r'milh(?:ao|oes|ão|ões)|(?:^|_)mi(?:_|$)'),
    ('bilh', Decimal(10) ** 9, r'bilh(?:ao|oes|ão|ões)|(?:^|_)bi(?:_|$)'),
    ('bi', Decimal(10) ** 9, r'bilh(?:ao|oes|ão|ões)|(?:^|_)bi(?:_|$)'),
    ('mwh', Decimal(1000), r'mwh'),
    ('gwh', Decimal(10) ** 6, r'gwh'),
)
# Um ano é metadado depois de uma palavra de tempo, e não antes de uma unidade.
ANTES_DO_ANO = re.compile(
    r'(?:\b(?:em|de|do|desde|at[eé]|entre|e|a|ante|contra|ano|anos|no|para|versus|vs\.?)\s+'
    r'|/)$',
    re.IGNORECASE,
)
DEPOIS_DO_ANO = re.compile(
    r'\s*(?:%|p\.?p\.?|R\$|[kMG]Wh|h\b|horas?\b|mil\b|milh|bilh|UCs?\b|unidades\b'
    r'|clientes\b|faturas\b|bairros\b|munic|alimentadores\b|inspe|ocorr|atendimentos\b'
    r'|reclama)',
    re.IGNORECASE,
)
# Uma contagem de linhas é metadado sem unidade de medida: "7 bairros" sim, "R$ 7" não.
UNIDADE_DEPOIS = re.compile(r'\s*(?:%|p\.?p\.?|[kMG]Wh|h\b|horas?\b|mil\b|milh|bilh)', re.I)
PALAVRA = re.compile(r'\s*([^\W\d_]+)')
UNIDADES = re.compile(r'(?:p\.?p\.?|[kMG]?Wh|h|horas?|reais|real|mil|milh\w*|bilh\w*|mi|bi)$', re.I)
# As palavras de limiar e de seleção que a pergunta e a resposta podem repetir antes do
# número ("acima de 30%", "os últimos 3").
LIMIARES = frozenset(
    'acima abaixo mais menos maior maiores menor menores superior inferior mínimo minimo '
    'máximo maximo pelo partir até ate top últimos ultimos últimas ultimas primeiros '
    'primeiras'.split()
)


@dataclass(frozen=True)
class Caso:
    id: str
    categoria: str
    pergunta: str
    sql: str | None = None
    nao_sei: bool = False
    periodo: str | None = None
    ordem: bool = False
    contexto: dict = field(default_factory=dict)


@dataclass
class Resultado:
    caso: Caso
    acertou: bool
    tipo: str
    falhas: list[str]
    latencia_ms: int
    texto: str = ''
    tokens: int = 0


def carregar(caminho: Path) -> list[Caso]:
    # O PyYAML só entra na avaliação, que roda fora do backend.
    import yaml

    dados = yaml.safe_load(Path(caminho).read_text(encoding='utf-8'))
    casos = [Caso(**caso) for caso in dados['casos']]
    ids = [caso.id for caso in casos]
    if len(set(ids)) != len(ids):
        raise ValueError('Há ids repetidos em perguntas.yaml.')
    for caso in casos:
        if bool(caso.sql) == caso.nao_sei:
            raise ValueError(f'{caso.id}: informe sql ou nao_sei: true, um dos dois.')
    return casos


async def avaliar(
    agente: Assistente, referencia, casos: list[Caso], competencia_mais_recente: date
) -> list[Resultado]:
    """Roda cada caso no agente e confere com o resultado da consulta de referência.

    `referencia` é um executor da role `ai_read` (`ExecutorAiRead`): as consultas de
    referência rodam no mesmo banco e com as mesmas permissões do agente."""
    resultados = []
    for caso in casos:
        esperado = (await referencia.executar(caso.sql)).linhas if caso.sql else None
        contexto = _contexto(caso, competencia_mais_recente)
        inicio = time.monotonic()
        try:
            resposta = await agente.responder(caso.pergunta, contexto)
        except ProvedorIndisponivel as erro:
            latencia = round((time.monotonic() - inicio) * 1000)
            resultados.append(Resultado(caso, False, 'erro', [f'provedor: {erro}'], latencia))
            continue
        falhas = conferir(caso, resposta, esperado, contexto)
        resultados.append(
            Resultado(
                caso,
                not falhas,
                resposta.tipo,
                falhas,
                resposta.latencia_ms,
                resposta.texto,
                resposta.tokens_entrada + resposta.tokens_saida,
            )
        )
    return resultados


def conferir(
    caso: Caso,
    resposta: RespostaAgente,
    esperado: list[list[Any]] | None,
    contexto: Contexto | None = None,
) -> list[str]:
    """Os motivos pelos quais a resposta não atende ao caso; vazio quando atende."""
    if caso.nao_sei:
        return [] if resposta.tipo == 'nao_sei' else ['respondeu em vez de dizer "não sei"']
    if resposta.tipo == 'nao_sei':
        return [f'disse "não sei": {resposta.motivo}']
    falhas = []
    consulta = resposta.consultas[-1] if resposta.consultas else Consulta(sql_gerado='')
    obtido = consulta.linhas
    if not mesmo_resultado(esperado or [], obtido, caso.ordem):
        falhas.append(f'resultado diferente do esperado: {esperado[:3]} × {obtido[:3]}')
    if caso.periodo and not _mesmo_periodo(caso.periodo, resposta):
        declarado = resposta.periodo.descricao if resposta.periodo else 'nenhum'
        falhas.append(f'período declarado {declarado}, esperado {caso.periodo}')
    if sem_lastro := _sem_lastro(caso, resposta, consulta, contexto):
        falhas.append(f'número sem lastro no texto: {", ".join(sem_lastro)}')
    return falhas


def mesmo_resultado(esperado: list[list[Any]], obtido: list[list[Any]], ordem=False) -> bool:
    if not esperado:
        return not any(v is not None for linha in obtido for v in linha)
    if ordem:
        return len(obtido) >= len(esperado) and all(
            _linha_contida(e, o) for e, o in zip(esperado, obtido)
        )
    return all(any(_linha_contida(e, o) for o in obtido) for e in esperado)


def relatorio(resultados: list[Resultado], modelo: str) -> str:
    total = len(resultados)
    acertos = sum(r.acertou for r in resultados)
    com_resposta = [r for r in resultados if not r.caso.nao_sei]
    sem_resposta = [r for r in resultados if r.caso.nao_sei]
    indevidos = sum(r.tipo == 'nao_sei' for r in com_resposta)
    sem_lastro = sum(any(f.startswith('número sem lastro') for f in r.falhas) for r in resultados)
    medidos = [r.latencia_ms for r in resultados if r.tipo != 'erro']
    acerto_com_resposta = _taxa(_acertos(com_resposta), len(com_resposta))
    linhas = [
        f'# Avaliação do agente — {modelo}',
        '',
        '| Indicador | Valor |',
        '|---|---|',
        f'| Taxa de acerto | {_taxa(acertos, total)} ({acertos} de {total}) |',
        f'| Acerto nas perguntas com resposta | {acerto_com_resposta} |',
        f'| "Não sei" correto | {_taxa(_acertos(sem_resposta), len(sem_resposta))} |',
        f'| "Não sei" indevido | {indevidos} de {len(com_resposta)} |',
        f'| Respostas com número sem lastro | {sem_lastro} |',
        f'| Latência média | {_media(medidos)} ms |',
        f'| Tokens por pergunta (média) | {_media([r.tokens for r in resultados])} |',
        '',
        '| Caso | Categoria | Esperado | Obtido | Acertou | Latência (ms) | Falhas |',
        '|---|---|---|---|---|---|---|',
    ]
    for r in resultados:
        esperado = 'não sei' if r.caso.nao_sei else 'resposta'
        falhas = '; '.join(r.falhas).replace('|', '\\|') or '—'
        linhas.append(
            f'| {r.caso.id} | {r.caso.categoria} | {esperado} | {r.tipo} | '
            f'{"sim" if r.acertou else "não"} | {r.latencia_ms} | {falhas} |'
        )
    return '\n'.join(linhas) + '\n'


def taxa_de_acerto(resultados: list[Resultado]) -> float:
    return _acertos(resultados) / len(resultados) if resultados else 0.0


def _contexto(caso: Caso, competencia_mais_recente: date) -> Contexto:
    contexto = dict(caso.contexto)
    for chave in ('periodo', 'comparacao'):
        if chave in contexto:
            contexto[chave] = _periodo(contexto[chave])
    return Contexto(competencia_mais_recente=competencia_mais_recente, **contexto)


def _sem_lastro(caso: Caso, resposta: RespostaAgente, consulta: Consulta, contexto):
    periodo = resposta.periodo and Periodo(resposta.periodo.inicio, resposta.periodo.fim)
    anos = set()
    for p in (periodo, contexto and contexto.periodo, contexto and contexto.comparacao):
        if p is not None:
            anos |= set(range(p.inicio.year - 1, p.fim.year + 1))
    contagens = {len(consulta.linhas)}
    if consulta.total_linhas < LIMITE_MAXIMO:
        contagens.add(consulta.total_linhas)
    return numeros_sem_lastro_estrito(
        resposta.texto,
        consulta.linhas,
        consulta.colunas,
        contagens=contagens,
        meses=periodo.meses if periodo else None,
        anos=anos,
        pergunta=caso.pergunta,
    )


def numeros_sem_lastro_estrito(
    texto: str,
    linhas: list[list[Any]],
    colunas: list[str],
    contagens: set[int] = frozenset(),
    meses: int | None = None,
    anos: set[int] = frozenset(),
    pergunta: str = '',
) -> list[str]:
    """A conferência da avaliação, independente da do agente (ver a docstring do módulo)."""
    valores = [
        (Decimal(str(v)), colunas[i] if i < len(colunas) else '')
        for linha in linhas
        for i, v in enumerate(linha)
        if isinstance(v, int | float | Decimal) and not isinstance(v, bool)
    ]
    da_pergunta = list(_contextos(pergunta))
    sem_lastro = []
    for numero, valor, escala, antes, depois in _contextos(texto):
        if any(_sustenta(valor, escala, numero, v, coluna) for v, coluna in valores):
            continue
        if escala is None and _e_metadado(numero, valor, antes, depois, contagens, meses, anos):
            continue
        if any(
            valor == valor_p and _mesmo_contexto(antes, depois, antes_p, depois_p)
            for _, valor_p, _, antes_p, depois_p in da_pergunta
        ):
            continue
        sem_lastro.append(numero + (escala or ''))
    return sem_lastro


def _contextos(texto: str):
    """Cada número do texto: como está escrito, o valor, a escala e o que vem antes e
    depois dele. Códigos, datas e ordinais saem antes, como no agente."""
    limpo = IGNORADOS.sub(lambda m: ' ' * len(m.group(0)), texto)
    for citado in NUMERO.finditer(limpo):
        numero = citado['numero']
        valor = Decimal(numero.replace('.', '').replace(',', '.'))
        escala = citado['escala'] and limpo[citado.end('numero') : citado.end()]
        yield numero, valor, escala, limpo[: citado.start()], limpo[citado.end() :]


def _sustenta(valor: Decimal, escala: str | None, numero: str, alvo: Decimal, coluna: str):
    # Só arredondamento nas casas mostradas, sem truncar.
    casas = len(numero.split(',')[1]) if ',' in numero else 0
    nome = (escala or '').strip().lower()
    if nome == '%' or nome.startswith('p'):
        return any(_arredonda(valor, alvo * fator, casas) for fator in (1, 100))
    # Os dois na mesma unidade: 351,2 em volume_mwh são 351.200 kWh, e "351,2 kWh" não os
    # descreve.
    escrita = next((m for prefixo, m, _ in ESCALAS if nome.startswith(prefixo)), Decimal(1))
    da_coluna = next(
        (m for _, m, padrao in ESCALAS if re.search(padrao, coluna, re.IGNORECASE)), Decimal(1)
    )
    return _arredonda(valor * escrita, alvo * da_coluna, casas, escrita)


def _arredonda(citado: Decimal, alvo: Decimal, casas: int, multiplicador=Decimal(1)) -> bool:
    unidade = (Decimal(1).scaleb(-casas) * multiplicador).normalize()
    try:
        return abs(alvo).quantize(unidade, ROUND_HALF_UP) == citado
    except InvalidOperation:
        return False


def _e_metadado(numero, valor, antes, depois, contagens, meses, anos) -> bool:
    if not _inteiro(valor) or ',' in numero:
        return False
    inteiro = int(valor)
    if re.fullmatch(r'\d{4}', numero) and inteiro in anos:
        return ANTES_DO_ANO.search(antes) is not None and not DEPOIS_DO_ANO.match(depois)
    if inteiro == meses and re.match(r'\s+m[eê]s(?:es)?\b', depois, re.IGNORECASE):
        return True
    return (
        inteiro in contagens
        and not re.search(r'R\$\s*$', antes)
        and not UNIDADE_DEPOIS.match(depois)
    )


def _mesmo_contexto(antes: str, depois: str, antes_p: str, depois_p: str) -> bool:
    """O número da pergunta vale na resposta só no mesmo contexto: a mesma palavra depois
    ("10 bairros", "3 anos", "3 ou mais") ou as mesmas duas palavras antes, com uma de
    limiar ("acima de 30%"). Uma unidade não conta como palavra, e "foi R$ 9.876.543,21"
    na pergunta não sustenta o mesmo valor na resposta."""
    seguinte, seguinte_p = PALAVRA.match(depois), PALAVRA.match(depois_p)
    if seguinte and seguinte_p:
        palavra = seguinte[1].lower()
        if palavra == seguinte_p[1].lower() and not UNIDADES.match(palavra):
            return True
    anteriores = re.findall(r'[^\W\d_]+', antes.lower())[-2:]
    return (
        len(anteriores) == 2
        and anteriores == re.findall(r'[^\W\d_]+', antes_p.lower())[-2:]
        and any(palavra in LIMIARES for palavra in anteriores)
    )


def _periodo(texto: str) -> Periodo:
    inicio, fim = (date.fromisoformat(f'{parte}-01') for parte in texto.split('..'))
    return Periodo(inicio, fim)


def _mesmo_periodo(esperado: str, resposta: RespostaAgente) -> bool:
    if resposta.periodo is None:
        return False
    periodo = _periodo(esperado)
    return (resposta.periodo.inicio, resposta.periodo.fim) == (periodo.inicio, periodo.fim)


def _linha_contida(esperada: list[Any], obtida: list[Any]) -> bool:
    return all(any(_mesmo_valor(e, o) for o in obtida) for e in esperada if e is not None)


def _mesmo_valor(esperado: Any, obtido: Any) -> bool:
    e, o = _numero(esperado), _numero(obtido)
    if e is None or o is None:
        return str(esperado).strip().casefold() == str(obtido).strip().casefold()
    if e == 0:
        return o == 0
    # Dois inteiros, como as contagens, batem só se forem iguais: 301 não vale por 300,
    # nem 3 por 300.
    if _inteiro(e) and _inteiro(o):
        return abs(e) == abs(o)
    limite = max(abs(e) * TOLERANCIA, TOLERANCIA_ABSOLUTA)
    return any(abs(abs(o) * fator - abs(e)) <= limite for fator in FATORES)


def _inteiro(valor: Decimal) -> bool:
    return valor == valor.to_integral_value()


def _numero(valor: Any) -> Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float | Decimal):
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def _acertos(resultados: list[Resultado]) -> int:
    return sum(r.acertou for r in resultados)


def _taxa(parte: int, total: int) -> str:
    return f'{parte / total:.0%}'.replace('.', ',') if total else '—'


def _media(valores: list[int]) -> str:
    return f'{round(sum(valores) / len(valores)):,}'.replace(',', '.') if valores else '—'
