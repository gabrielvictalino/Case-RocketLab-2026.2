import re
from datetime import date
from pathlib import Path

import pytest

from venergy_ai.avaliacao import (
    Caso,
    avaliar,
    carregar,
    conferir,
    mesmo_resultado,
    relatorio,
    taxa_de_acerto,
)
from venergy_ai.executor import ResultadoSQL
from venergy_ai.interface import Consulta, PeriodoUsado, ProvedorIndisponivel, RespostaAgente

PERGUNTAS = Path(__file__).parents[1] / 'evals' / 'perguntas.yaml'
DOZE_MESES = PeriodoUsado(inicio=date(2025, 7, 1), fim=date(2026, 6, 1), descricao='12 meses')


def resposta(linhas, texto='Ver tabela.', tipo='resposta', periodo=DOZE_MESES, motivo=None):
    consulta = Consulta(sql_gerado='SELECT 1', colunas=['x'], linhas=linhas)
    return RespostaAgente(
        tipo=tipo,
        texto=texto,
        periodo=periodo,
        motivo=motivo,
        consultas=[consulta],
        modelo='simulado',
        tokens_entrada=10,
        tokens_saida=5,
        latencia_ms=100,
    )


@pytest.mark.parametrize(
    'esperado,obtido',
    [
        ([[300]], [[300]]),
        # Percentual pronto ou razão, e a mesma variação com o sinal trocado.
        ([[-16.7]], [[-0.1666]]),
        ([[-16.7]], [[16.66]]),
        # kWh contra MWh.
        ([[-351234.5]], [[-351.2]]),
        # A linha esperada aparece numa linha do agente, com colunas a mais.
        ([['Iputinga', -351234.5]], [['Recife', 'iputinga', -351234.5, -16.7]]),
        ([[1234567.89]], [[1234567.89, 1100000.0, 12.2]]),
    ],
)
def test_mesmo_resultado(esperado, obtido):
    assert mesmo_resultado(esperado, obtido)


@pytest.mark.parametrize(
    'esperado,obtido',
    [
        ([[300]], [[301]]),
        # Uma contagem de 3 não vale por 300.
        ([[300]], [[3]]),
        ([[1234567.89]], [[1300000.0]]),
        ([['Iputinga', -351234.5]], [['Macaxeira', -351234.5]]),
        ([[1], [2]], [[1]]),
    ],
)
def test_resultado_diferente(esperado, obtido):
    assert not mesmo_resultado(esperado, obtido)


def test_ranking_na_ordem():
    assert mesmo_resultado([['A'], ['B']], [['A', 9], ['B', 8], ['C', 7]], ordem=True)
    assert not mesmo_resultado([['A'], ['B']], [['B', 9], ['A', 8]], ordem=True)


def test_conferir_periodo_e_numero_sem_lastro():
    caso = Caso('c', 'teste', 'Receita?', sql='SELECT 1', periodo='2025-07..2026-06')
    assert conferir(caso, resposta([[300]], 'São 300.'), [[300]]) == []
    errado = resposta(
        [[300]],
        'São 300 de 400.',
        periodo=DOZE_MESES.model_copy(
            update={'inicio': date(2025, 1, 1), 'descricao': 'jan/2025 a jun/2026'}
        ),
    )
    falhas = conferir(caso, errado, [[300]])
    assert falhas == [
        'período declarado jan/2025 a jun/2026, esperado 2025-07..2026-06',
        'número sem lastro no texto: 400',
    ]


def test_conferir_nao_sei():
    caso = Caso('c', 'nao-sei', 'Capital da França?', nao_sei=True)
    assert conferir(caso, resposta([], tipo='nao_sei', motivo='Fora.'), None) == []
    assert conferir(caso, resposta([[1]]), None) == ['respondeu em vez de dizer "não sei"']


def test_perguntas_da_avaliacao():
    casos = carregar(PERGUNTAS)
    assert len(casos) >= 20
    categorias = {caso.categoria for caso in casos}
    assert {'liderancas', 'periodo-ambiguo', 'nao-sei', 'injecao'} <= categorias


class AgenteRoteirizado:
    def __init__(self, respostas):
        self.respostas = respostas

    async def responder(self, pergunta, contexto, andamento=None):
        resposta = self.respostas[pergunta]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


class ReferenciaFalsa:
    async def executar(self, sql):
        return ResultadoSQL(['x'], [[300]], 1)


async def test_avaliar_e_relatorio():
    casos = [
        Caso('certo', 'liderancas', 'UCs?', sql='SELECT 300'),
        Caso('errado', 'liderancas', 'UCs de novo?', sql='SELECT 300'),
        Caso('nao-sei', 'nao-sei', 'França?', nao_sei=True),
        Caso('provedor', 'liderancas', 'Cai?', sql='SELECT 300'),
    ]
    agente = AgenteRoteirizado(
        {
            'UCs?': resposta([[300]], 'São 300 UCs.'),
            'UCs de novo?': resposta([], 'Não sei.', tipo='nao_sei', motivo='Sem dados.'),
            'França?': resposta([], 'Não sei.', tipo='nao_sei', motivo='Fora do domínio.'),
            'Cai?': ProvedorIndisponivel('503'),
        }
    )
    resultados = await avaliar(agente, ReferenciaFalsa(), casos, date(2026, 6, 1))
    assert [r.acertou for r in resultados] == [True, False, True, False]
    assert resultados[3].tipo == 'erro'
    assert taxa_de_acerto(resultados) == 0.5
    texto = relatorio(resultados, 'simulado')
    assert '| Taxa de acerto | 50% (2 de 4) |' in texto
    assert '| "Não sei" correto | 100% |' in texto
    assert '| "Não sei" indevido | 1 de 3 |' in texto
    assert '| Latência média | 100 ms |' in texto


@pytest.mark.parametrize(
    'texto',
    [
        'Nos últimos 12 meses, a receita faturada foi de R$ 300.',
        'Em 2025 e 2026, a receita faturada foi de R$ 300.',
        'A consulta trouxe 1 linha: R$ 300.',
    ],
)
def test_metadados_que_o_agente_aceita_nao_contam_como_inventados(texto):
    # Meses e anos do período e contagem de linhas: a validação do agente aceita, e a
    # avaliação não pode reprovar só pela redação.
    caso = Caso(id='x', categoria='y', pergunta='Receita?', sql='SELECT 1')
    assert conferir(caso, resposta([[300]], texto), [[300]]) == []


def test_numero_inventado_continua_reprovado():
    caso = Caso(id='x', categoria='y', pergunta='Receita?', sql='SELECT 1')
    falhas = conferir(caso, resposta([[300]], 'Nos últimos 12 meses, foram R$ 450.'), [[300]])
    assert falhas == ['número sem lastro no texto: 450']


TOP_5 = [['ALM-A'], ['ALM-B'], ['ALM-C'], ['ALM-D'], ['ALM-E']]


@pytest.mark.parametrize(
    'obtido',
    [
        [['ALM-X'], *TOP_5],
        TOP_5[::-1],
        [['ALM-X'], *TOP_5[::-1]],
    ],
    ids=['linha-extra-antes', 'ordem-invertida', 'extra-e-invertida'],
)
def test_ranking_exige_as_primeiras_linhas_na_ordem(obtido):
    assert not mesmo_resultado(TOP_5, obtido, ordem=True)
    # Sem a ordem, os mesmos resultados passariam: por isso o caso precisa dela.
    assert mesmo_resultado(TOP_5, obtido)


def test_todo_ranking_da_avaliacao_confere_a_ordem():
    for caso in carregar(PERGUNTAS):
        sql = caso.sql or ''
        if re.search(r'\bORDER BY\b', sql, re.I) and re.search(r'\bLIMIT\b', sql, re.I):
            assert caso.ordem, caso.id
