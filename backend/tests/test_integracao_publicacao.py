"""Gold → importador → portal/IA/Redis, conforme system design §§8–10.

As integrações usam o bootstrap, as migrações e os serviços reais da fixture da
raiz. Somente o provedor externo do LLM é simulado no teste de insights.
"""

import csv
import json
import shutil
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from venergy_ai.executor import ExecutorAiRead
from venergy_ai.insights import RedatorDeInsights

from contracts.manifesto import gerar_manifesto
from importador.contracts import ContractError
from importador.loader import load

pytestmark = pytest.mark.integration
SAMPLES = Path(__file__).resolve().parents[2] / 'contracts/samples'
RECORTE = dict(
    periodo='2025-07..2025-07',
    comparacao='2025-06..2025-06',
    municipio='Recife',
    classe='Residencial',
)
SQL_RECEITA = """SELECT sum(receita) AS receita FROM ai_read.receita_volume_mensal
    WHERE competencia = DATE '2025-07-01'
      AND municipio = 'Recife' AND classe = 'Residencial'"""


def alterar_csv(origem, tabela, transformar):
    arquivo = origem / f'{tabela}.csv'
    with arquivo.open(newline='', encoding='utf-8') as entrada:
        leitor = csv.DictReader(entrada)
        colunas = leitor.fieldnames
        linhas = list(leitor)
    for linha in linhas:
        transformar(linha)
    with arquivo.open('w', newline='', encoding='utf-8') as saida:
        escritor = csv.DictWriter(saida, colunas, lineterminator='\n')
        escritor.writeheader()
        escritor.writerows(linhas)


def manifestar(origem):
    anterior = json.loads((origem / 'manifest.json').read_text())
    return gerar_manifesto(
        origem,
        batch_id='integracao-' + uuid4().hex,
        periodo=f'{anterior["period"]["start"]}..{anterior["period"]["end"]}',
        data_referencia=anterior['reference_date'],
        sintetico=True,
    )


@pytest.fixture
async def exportacao(infrastructure, db, tmp_path):
    """Dois lados da reconciliação mudam juntos; a amostra é restaurada em erro também."""
    origem = tmp_path / 'gold'
    shutil.copytree(SAMPLES, origem)

    def dobrar(linha, colunas):
        for coluna in colunas:
            linha[coluna] = str(D(linha[coluna]) * 2)

    alterar_csv(
        origem,
        'uc_consumo_faturamento_mensal',
        lambda linha: dobrar(linha, ('valor_total', 'valor_arrecadado')),
    )
    alterar_csv(
        origem,
        'receita_volume_mensal',
        lambda linha: dobrar(linha, ('receita', 'receita_arrecadada')),
    )
    manifestar(origem)
    await load(SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)
    try:
        yield origem
    finally:
        await load(SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)


async def consultar(http, headers, rota, **parametros):
    resposta = await http.get('/api/v1/' + rota, headers=headers, params=parametros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


async def autenticar(http):
    resposta = await http.post(
        '/api/v1/auth/login', json={'login': 'perdas', 'senha': 'Demo-Venergy-2026!'}
    )
    assert resposta.status_code == 200, resposta.text
    return {'Authorization': 'Bearer ' + resposta.json()['access_token']}


async def conferir_receita(http, headers, executor, fator, carga):
    kpis = await consultar(http, headers, 'kpis', **RECORTE)
    receita = await consultar(http, headers, 'receita/decomposicao', **RECORTE)
    serie = await consultar(http, headers, 'kpis/serie', **RECORTE)
    for resposta in (kpis, receita, serie):
        assert resposta['carga']['id'] == str(carga)
    # Exemplo R5 do contrato: 2.905 → 2.652 kWh e R$ 2.324 → R$ 2.386,80.
    assert D(kpis['receita']['valor']) == D('2386.80') * fator
    assert D(kpis['receita']['comparacao']) == D('2324.00') * fator
    assert D(kpis['volume_faturado_kwh']['valor']) == D('2652.00')
    assert D(receita['receita_atual']) == D('2386.80') * fator
    assert D(receita['receita_base']) == D('2324.00') * fator
    assert {chave: D(valor) for chave, valor in receita['efeitos'].items()} == dict(
        volume=D('-202.40') * fator,
        reajuste=D(0),
        bandeira=D('265.20') * fator,
        mix=D(0),
    )
    assert D(serie['serie'][0]['receita']) == D('2386.80') * fator
    resultado = await executor.executar(SQL_RECEITA)
    assert resultado.colunas == ['receita']
    assert D(str(resultado.linhas[0][0])) == D('2386.80') * fator


async def test_publicacao_atualiza_portal_e_executor_ia_sem_reiniciar(
    exportacao, portal, infrastructure
):
    app, http = portal
    headers = await autenticar(http)
    executor = ExecutorAiRead(app.state.ai_engine)
    anterior = await consultar(http, headers, 'meta/carga')
    await conferir_receita(http, headers, executor, 1, anterior['id'])

    nova = await load(
        exportacao, infrastructure['importer_url'], infrastructure['settings'].redis_url
    )

    assert str(nova) != anterior['id']
    await conferir_receita(http, headers, executor, 2, nova)
    atual = await consultar(http, headers, 'meta/carga')
    assert atual['batch_id'] == json.loads((exportacao / 'manifest.json').read_text())['batch_id']
    assert await app.state.redis.get('versao_carga') == str(nova).encode()


@pytest.mark.parametrize('modo', ['verificar', 'hash_invalido', 'reconciliacao_invalida'])
async def test_carga_nao_publicada_preserva_o_que_portal_e_ia_leem(
    exportacao, portal, infrastructure, db, modo
):
    app, http = portal
    headers = await autenticar(http)
    antes = await consultar(http, headers, 'meta/carga')
    versao_redis = await app.state.redis.get('versao_carga')
    cargas = await db.fetch('SELECT * FROM operations.cargas ORDER BY ordem_publicacao')
    if modo == 'hash_invalido':
        with (exportacao / 'dim_uc.csv').open('a') as arquivo:
            arquivo.write('\n')
    elif modo == 'reconciliacao_invalida':
        # Manifesto correto: a divergência só aparece na comparação entre tabelas.
        alterar_csv(exportacao, 'receita_volume_mensal', lambda r: r.update(receita='0.00'))
        manifestar(exportacao)
    argumentos = (exportacao, infrastructure['importer_url'], infrastructure['settings'].redis_url)

    if modo == 'verificar':
        assert await load(*argumentos, verify_only=True) is None
    else:
        mensagem = 'SHA-256' if modo == 'hash_invalido' else 'não reconciliam por grão'
        with pytest.raises(ContractError, match=mensagem):
            await load(*argumentos)

    assert await consultar(http, headers, 'meta/carga') == antes
    assert await app.state.redis.get('versao_carga') == versao_redis
    assert await db.fetch('SELECT * FROM operations.cargas ORDER BY ordem_publicacao') == cargas
    await conferir_receita(http, headers, ExecutorAiRead(app.state.ai_engine), 1, antes['id'])
    for schema in ('analytics_staging', 'analytics_anterior'):
        assert await db.fetchval('SELECT to_regnamespace($1)', schema) is None


async def test_redis_com_versao_antiga_nao_esconde_publicacao_confirmada(
    exportacao, portal, infrastructure
):
    app, http = portal
    headers = await autenticar(http)
    versao_antiga = await app.state.redis.get('versao_carga')

    nova = await load(exportacao, infrastructure['importer_url'], 'redis://127.0.0.1:1/0')

    assert await app.state.redis.get('versao_carga') == versao_antiga
    assert versao_antiga != str(nova).encode()
    await conferir_receita(http, headers, ExecutorAiRead(app.state.ai_engine), 2, nova)
    assert (await consultar(http, headers, 'meta/carga'))['id'] == str(nova)


async def test_nova_gold_preserva_snapshot_da_ordem_e_atualiza_fila_apos_cancelamento(
    exportacao, portal, infrastructure, db
):
    app, http = portal
    headers = await autenticar(http)
    resposta = await http.post(
        '/api/v1/ordens-inspecao', headers=headers, json={'ucs': ['UC100001']}
    )
    assert resposta.status_code == 201, resposta.text
    ordem = resposta.json()['criadas'][0]
    eventos = await db.fetch('SELECT * FROM operations.ordem_eventos ORDER BY id')

    def mudar_candidata(linha):
        if linha['id_uc'] == 'UC100001':
            linha.update(energia_recuperar_kwh='777.00', energia_recuperar_reais='888.00')

    alterar_csv(exportacao, 'fila_inspecao', mudar_candidata)
    manifestar(exportacao)
    await load(exportacao, infrastructure['importer_url'], infrastructure['settings'].redis_url)

    ordens = await consultar(http, headers, 'ordens-inspecao')
    assert ordens['items'] == [ordem]
    assert await db.fetch('SELECT * FROM operations.ordem_eventos ORDER BY id') == eventos
    fila = await consultar(http, headers, 'perdas/fila', size=100)
    assert 'UC100001' not in {item['id_uc'] for item in fila['items']}
    executor = ExecutorAiRead(app.state.ai_engine)
    sql = "SELECT energia_recuperar_kwh FROM ai_read.fila_inspecao WHERE id_uc='UC100001'"
    assert (await executor.executar(sql)).linhas == []

    resposta = await http.post(
        f'/api/v1/ordens-inspecao/{ordem["id"]}/cancelar',
        headers=headers,
        json={'motivo': 'Reavaliar após atualização da Gold'},
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()['energia_recuperar_kwh'] == ordem['energia_recuperar_kwh']
    fila = await consultar(http, headers, 'perdas/fila', size=100)
    candidata = next(item for item in fila['items'] if item['id_uc'] == 'UC100001')
    assert D(candidata['energia_recuperar_kwh']) == D('777.00')
    assert D(candidata['energia_recuperar_reais']) == D('888.00')
    assert (await executor.executar(sql)).linhas == [[777.0]]


async def test_publicacao_muda_cache_do_insight_com_fatos_da_nova_carga(
    exportacao, portal, infrastructure
):
    app, http = portal
    headers = await autenticar(http)
    pedidos = []

    async def responder(mensagens, info):
        pedido = mensagens[-1].parts[-1].content
        fatos = json.loads(pedido.split('<fatos>', 1)[1].rsplit('</fatos>', 1)[0])['fatos']
        pedidos.append({f['chave']: f['valor'] for f in fatos})
        observacoes = []
        for chave in ('receita', 'volume_faturado', 'efeito_bandeira'):
            valor = f'{D(pedidos[-1][chave]):,.2f}'
            valor = valor.replace(',', '_').replace('.', ',').replace('_', '.')
            observacoes.append({'chave': chave, 'texto': f'O valor observado foi de {valor}.'})
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {'observacoes': observacoes})]
        )

    app.state.redator = RedatorDeInsights(
        FunctionModel(responder, model_name='integracao-' + uuid4().hex)
    )
    antes = await consultar(http, headers, 'insights/receita', **RECORTE)
    assert await consultar(http, headers, 'insights/receita', **RECORTE) == antes
    assert len(pedidos) == 1
    assert D(pedidos[0]['receita']) == D('2386.80')

    nova = await load(
        exportacao, infrastructure['importer_url'], infrastructure['settings'].redis_url
    )

    depois = await consultar(http, headers, 'insights/receita', **RECORTE)
    assert depois['carga']['id'] == str(nova)
    assert depois['carga']['id'] != antes['carga']['id']
    assert len(pedidos) == 2
    assert D(pedidos[1]['receita']) == D('4773.60')
    assert depois['observacoes'] != antes['observacoes']
    assert await consultar(http, headers, 'insights/receita', **RECORTE) == depois
    assert len(pedidos) == 2


@pytest.mark.parametrize('tabela', ['dim_uc', 'receita_volume_mensal', 'fila_inspecao'])
async def test_role_portal_nao_escreve_na_gold_apos_publicacao(exportacao, infrastructure, tabela):
    await load(exportacao, infrastructure['importer_url'], infrastructure['settings'].redis_url)
    url = infrastructure['settings'].database_url_portal.replace(
        'postgresql+asyncpg://', 'postgresql://'
    )
    conexao = await asyncpg.connect(url)
    try:
        assert await conexao.fetchval(f'SELECT count(*) FROM analytics.{tabela}') > 0
        # Mesmo sem alcançar linhas, a tentativa de escrita deve ser barrada pela ACL.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conexao.execute(f'DELETE FROM analytics.{tabela} WHERE false')
    finally:
        await conexao.close()
