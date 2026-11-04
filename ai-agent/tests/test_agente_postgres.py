import asyncio
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from venergy_ai.agente import AgenteTextoSQL
from venergy_ai.executor import ConsultaFalhou, ExecutorAiRead
from venergy_ai.interface import Contexto
from test_agente import modelo_simulado

pytestmark = pytest.mark.integration


@pytest.fixture
async def executor(infrastructure):
    # Uma conexão só no pool: a consulta seguinte usa a mesma conexão da anterior.
    engine = create_async_engine(
        infrastructure['settings'].database_url_ai, pool_size=1, max_overflow=0
    )
    yield ExecutorAiRead(engine)
    await engine.dispose()


async def test_set_da_consulta_nao_sobrevive_na_conexao_do_pool(executor):
    await executor.executar('SET statement_timeout = 0')
    await executor.executar('SET default_transaction_read_only = off')
    assert (await executor.executar('SHOW statement_timeout')).linhas == [['5s']]
    assert (await executor.executar('SHOW transaction_read_only')).linhas == [['on']]


async def test_executor_converte_os_valores_e_traz_as_colunas(executor):
    resultado = await executor.executar(
        "SELECT count(*) AS ucs, round(avg(score)::numeric, 2) AS score, DATE '2026-06-01' AS d "
        'FROM ai_read.fila_inspecao'
    )
    assert resultado.colunas == ['ucs', 'score', 'd']
    [[ucs, score, competencia]] = resultado.linhas
    assert isinstance(ucs, int) and isinstance(score, float | int)
    assert competencia == '2026-06-01'


async def test_executor_converte_interval_em_horas(executor):
    resultado = await executor.executar(
        "SELECT INTERVAL '3 hours 30 minutes' AS duracao, 'NaN'::numeric AS indefinido"
    )
    assert resultado.linhas == [[3.5, 'NaN']]


async def test_timeout_do_cliente_vira_erro_da_consulta(infrastructure):
    # O command_timeout do asyncpg dispara antes do statement_timeout de 5 s da role.
    engine = create_async_engine(
        infrastructure['settings'].database_url_ai, connect_args={'command_timeout': 0.5}
    )
    try:
        executor = ExecutorAiRead(engine)
        with pytest.raises(ConsultaFalhou, match='tempo limite'):
            await executor.executar('SELECT count(*) FROM generate_series(1, 10000000000)')
        assert (await executor.executar('SELECT 1')).linhas == [[1]]
    finally:
        await engine.dispose()


async def test_executor_devolve_o_erro_do_banco(executor):
    with pytest.raises(ConsultaFalhou, match='permission denied'):
        await executor.executar('SELECT * FROM operations.usuarios')
    # A conexão continua utilizável depois do erro.
    assert (await executor.executar('SELECT 1')).linhas == [[1]]


async def test_pergunta_respondida_com_a_role_ai_read(executor):
    plano = {
        'tipo': 'consulta',
        'metrica': 'UCs no cadastro',
        'sql': "SELECT count(*) AS ucs FROM ucs WHERE bairro LIKE '%'",
    }
    modelo, _ = modelo_simulado(plano, 'O cadastro tem 300 UCs.')
    contexto = Contexto(competencia_mais_recente=date(2026, 6, 1))
    resposta = await AgenteTextoSQL(modelo, executor).responder('Quantas UCs há?', contexto)
    assert resposta.tipo == 'resposta', resposta.motivo
    [consulta] = resposta.consultas
    assert 'ai_read.ucs' in consulta.sql_executado
    assert consulta.linhas == [[300]]


async def test_consultas_de_referencia_da_avaliacao_rodam_na_ai_read(executor):
    from pathlib import Path

    from venergy_ai.avaliacao import carregar

    casos = carregar(Path(__file__).parents[1] / 'evals' / 'perguntas.yaml')
    for caso in casos:
        if caso.sql:
            resultado = await executor.executar(caso.sql)
            assert resultado.linhas, caso.id


async def test_intervalo_vira_horas_e_o_nome_diz_isso(executor):
    resultado = await executor.executar(
        "SELECT interval '2 days' AS tempo_dias, interval '90 minutes' AS duracao_horas"
    )
    # "2 dias" chegaria ao redator como 48 numa coluna de dias.
    assert resultado.colunas == ['tempo_dias_em_horas', 'duracao_horas']
    assert resultado.linhas == [[48.0, 1.5]]


async def test_teto_de_tempo_cancela_a_consulta_sem_virar_erro_de_sql(executor):
    # O cancelamento no meio da consulta não pode virar ConsultaFalhou: o agente pediria
    # outra consulta ao modelo e o 503 por tempo esgotado não viria.
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.3):
            await executor.executar('SELECT count(*) FROM generate_series(1, 400000000)')
    # A conexão do pool continua servindo.
    assert (await executor.executar('SELECT 1 AS um')).linhas == [[1]]


async def test_cancelamentos_seguidos_nao_esgotam_o_pool(infrastructure):
    # Uma conexão que não volta ao pool depois do cancelamento esgotaria as vagas: com
    # uma vaga só e pool_timeout curto, a consulta final travaria no checkout.
    engine = create_async_engine(
        infrastructure['settings'].database_url_ai, pool_size=1, max_overflow=0, pool_timeout=2
    )
    try:
        executor = ExecutorAiRead(engine)
        for _ in range(3):
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.2):
                    await executor.executar('SELECT count(*) FROM generate_series(1, 400000000)')
        assert (await executor.executar('SELECT 1 AS um')).linhas == [[1]]
    finally:
        await engine.dispose()
