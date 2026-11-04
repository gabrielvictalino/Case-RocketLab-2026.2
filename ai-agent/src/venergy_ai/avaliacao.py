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

Toda resposta é conferida também contra número inventado: o texto só pode citar números
das linhas que o redator recebeu e os que a validação do agente aceita: a conferência é
a mesma (`conferir_numeros`), com as contagens de linhas, os meses e os anos do período e,
como limiar, os números da pergunta. O relatório traz a taxa de acerto, a de "não sei"
correto e a latência média.
"""

import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from venergy_ai.agente import _periodo_padrao, conferir_numeros
from venergy_ai.interface import (
    Assistente,
    Consulta,
    Contexto,
    ProvedorIndisponivel,
    RespostaAgente,
)
from venergy_ai.semantica import Periodo

TOLERANCIA = Decimal('0.005')
# Meia unidade da primeira casa: 16,7 contra 16,66.
TOLERANCIA_ABSOLUTA = Decimal('0.051')
FATORES = (Decimal(1), Decimal(100), Decimal('0.01'), Decimal(1000), Decimal('0.001'))


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
    # A mesma conferência do agente: a avaliação não reprova por redação uma resposta que
    # o agente, com razão, deixou passar.
    periodo = resposta.periodo and Periodo(resposta.periodo.inicio, resposta.periodo.fim)
    if contexto is None:
        recente = periodo.fim if periodo else date.today().replace(day=1)
        contexto = Contexto(competencia_mais_recente=recente)
    padrao = _periodo_padrao(contexto)
    return conferir_numeros(resposta.texto, caso.pergunta, consulta, periodo, padrao, contexto)


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
