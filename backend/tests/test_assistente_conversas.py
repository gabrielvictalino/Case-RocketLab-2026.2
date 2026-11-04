import asyncio
import json
from uuid import uuid4

import pytest
from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from redis.asyncio import Redis
from venergy_ai.agente import CONSULTA_INTERROMPIDA, AgenteTextoSQL
from venergy_ai.executor import ExecutorAiRead
from venergy_ai.interface import Consulta, RespostaAgente

from app.modules.assistente import conversas
from app.modules.assistente.conversas import chave, chave_das_trocas
from test_assistente import PLANO, TEXTO, URL, entrar, usar_modelo

pytestmark = pytest.mark.integration

JABOATAO = {
    'tipo': 'consulta',
    'metrica': 'Receita faturada (R$)',
    'filtros': ['classe = Comercial', 'município = Jaboatão'],
    'periodo_inicio': '2025-07-01',
    'periodo_fim': '2026-06-01',
    'sql': (
        'SELECT round(sum(receita)::numeric, 2) AS receita_reais FROM receita_volume_mensal '
        "WHERE classe = 'Comercial' AND municipio = 'Jaboatão' "
        "AND competencia BETWEEN DATE '2025-07-01' AND DATE '2026-06-01'"
    ),
}
# O follow-up não repete o período: ele vem da troca anterior.
OLINDA = JABOATAO | {
    'filtros': ['classe = Comercial', 'município = Olinda'],
    'periodo_inicio': None,
    'periodo_fim': None,
    'sql': JABOATAO['sql'].replace('Jaboatão', 'Olinda'),
}
FORA = {'tipo': 'fora_do_dominio', 'motivo': 'A pergunta não é sobre os dados.'}


def modelo_gravador(*respostas):
    chamadas = []

    def responder(mensagens, info):
        chamadas.append(info)
        resposta = respostas[len(chamadas) - 1]
        if isinstance(resposta, dict):
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, resposta)])
        return ModelResponse(parts=[TextPart(resposta)])

    return FunctionModel(responder, model_name='simulado'), chamadas


async def test_follow_up_mantem_metrica_e_periodo_e_troca_o_municipio(portal):
    app, http = portal
    modelo, chamadas = modelo_gravador(
        JABOATAO, 'A receita comercial de Jaboatão está na tabela.', OLINDA, 'E a de Olinda.'
    )
    app.state.assistente = AgenteTextoSQL(modelo, ExecutorAiRead(app.state.ai_engine))
    headers = await entrar(http, 'comercial')
    primeira = await http.post(
        URL,
        json={'pergunta': 'Qual a receita comercial de Jaboatão no último ano?'},
        headers=headers,
    )
    assert primeira.status_code == 200, primeira.text
    corpo = {'pergunta': 'E em Olinda?', 'conversa_id': primeira.json()['conversa_id']}
    segunda = await http.post(URL, json=corpo, headers=headers)
    assert segunda.status_code == 200, segunda.text
    # O planejador recebe o estado estruturado da troca anterior, não só o texto.
    instrucoes = chamadas[2].instructions
    conversa = json.loads(instrucoes.split('<conversa>')[-1].split('</conversa>')[0])
    assert conversa == [
        {
            'pergunta': 'Qual a receita comercial de Jaboatão no último ano?',
            'metrica': 'Receita faturada (R$)',
            'filtros': ['classe = Comercial', 'município = Jaboatão'],
            'periodo': {
                'inicio': '2025-07-01',
                'fim': '2026-06-01',
                'descricao': 'jul/2025 a jun/2026',
            },
            'sql': primeira.json()['consultas'][0]['sql_executado'],
        }
    ]
    assert 'Sem período na pergunta: jul/2025 a jun/2026' in instrucoes
    resposta = segunda.json()
    assert resposta['tipo'] == 'resposta'
    assert resposta['metrica'] == 'Receita faturada (R$)'
    assert resposta['periodo']['descricao'] == 'jul/2025 a jun/2026'
    assert resposta['filtros'] == ['classe = Comercial', 'município = Olinda']
    assert "municipio = 'Olinda'" in resposta['consultas'][0]['sql_executado']


async def test_conversa_no_redis_guarda_as_ultimas_5_trocas_por_2_horas(portal):
    app, http = portal
    usar_modelo(app, *[PLANO, TEXTO] * 6)
    headers = await entrar(http, 'perdas')
    conversa_id = None
    for numero in range(6):
        corpo = {'pergunta': f'Pergunta {numero}', 'conversa_id': conversa_id}
        resposta = await http.post(URL, json=corpo, headers=headers)
        assert resposta.status_code == 200, resposta.text
        conversa_id = resposta.json()['conversa_id']
    redis = app.state.redis
    trocas = await trocas_no_redis(app, conversa_id)
    assert [t['pergunta'] for t in trocas] == [f'Pergunta {n}' for n in range(1, 6)]
    assert trocas[-1]['metrica'] == PLANO['metrica']
    for chave_redis in (chave(conversa_id), chave_das_trocas(conversa_id)):
        assert 7000 < await redis.ttl(chave_redis) <= 7200


async def test_resposta_fora_do_dominio_nao_muda_o_estado(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, FORA)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    corpo = {'pergunta': 'Qual a capital da França?', 'conversa_id': primeira['conversa_id']}
    assert (await http.post(URL, json=corpo, headers=headers)).json()['tipo'] == 'nao_sei'
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert [t['pergunta'] for t in trocas] == ['UCs?']


async def test_perguntas_ao_mesmo_tempo_guardam_as_duas_trocas(portal):
    # Duas perguntas na mesma conversa leem o histórico antes de qualquer uma gravar: a
    # troca que termina por último não pode apagar a outra.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    juntas = asyncio.Barrier(2)

    async def responder(mensagens, info):
        if info.output_tools:
            async with asyncio.timeout(10):
                await juntas.wait()
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, PLANO)])
        return ModelResponse(parts=[TextPart(TEXTO)])

    app.state.assistente = AgenteTextoSQL(
        FunctionModel(responder, model_name='simulado'), ExecutorAiRead(app.state.ai_engine)
    )
    respostas = await asyncio.gather(
        *(
            http.post(
                URL,
                json={'pergunta': pergunta, 'conversa_id': primeira['conversa_id']},
                headers=headers,
            )
            for pergunta in ('A?', 'B?')
        )
    )
    assert [r.status_code for r in respostas] == [200, 200]
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert trocas[0]['pergunta'] == 'UCs?'
    assert sorted(t['pergunta'] for t in trocas[1:]) == ['A?', 'B?']


async def test_troca_de_outra_usuaria_nao_entra_na_conversa(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    resposta = RespostaAgente(tipo='resposta', texto=TEXTO, metrica='UCs', modelo='simulado')
    await conversas.registrar(
        app.state.redis, primeira['conversa_id'], uuid4(), 'Outra?', resposta, None
    )
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert [t['pergunta'] for t in trocas] == ['UCs?']


async def test_conversa_no_formato_antigo_segue_como_conversa_nova(portal):
    # Antes do v2, conversa:{id} era um JSON com a dona e as trocas. Depois do deploy, o
    # follow-up dessa conversa responde e já grava a troca no formato novo.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    conversa_id = primeira['conversa_id']
    redis = app.state.redis
    await redis.delete(chave(conversa_id), chave_das_trocas(conversa_id))
    antiga = {'usuario_id': 'dona', 'trocas': [{'pergunta': 'UCs?', 'metrica': 'UCs'}]}
    await redis.set(f'conversa:{conversa_id}', json.dumps(antiga), ex=7200)
    corpo = {'pergunta': 'E agora?', 'conversa_id': conversa_id}
    resposta = await http.post(URL, json=corpo, headers=headers)
    assert resposta.status_code == 200, resposta.text
    assert [t['pergunta'] for t in await trocas_no_redis(app, conversa_id)] == ['E agora?']


async def test_troca_ilegivel_no_redis_nao_derruba_o_follow_up(portal):
    # Uma troca gravada por outra versão de Troca fica fora do histórico, sem 500.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    conversa_id = primeira['conversa_id']
    await app.state.redis.lpush(chave_das_trocas(conversa_id), '{"formato": "outro"}')
    corpo = {'pergunta': 'E agora?', 'conversa_id': conversa_id}
    resposta = await http.post(URL, json=corpo, headers=headers)
    assert resposta.status_code == 200, resposta.text
    perguntas = [t.get('pergunta') for t in await trocas_no_redis(app, conversa_id)]
    assert perguntas == [None, 'UCs?', 'E agora?']


async def test_pergunta_sem_metrica_tambem_renova_o_ttl(portal):
    # O TTL se renova a cada pergunta, não só nas que gravam uma troca.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, FORA)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    conversa_id = primeira['conversa_id']
    redis = app.state.redis
    for chave_redis in (chave(conversa_id), chave_das_trocas(conversa_id)):
        await redis.expire(chave_redis, 60)
    corpo = {'pergunta': 'Qual a capital da França?', 'conversa_id': conversa_id}
    assert (await http.post(URL, json=corpo, headers=headers)).json()['tipo'] == 'nao_sei'
    for chave_redis in (chave(conversa_id), chave_das_trocas(conversa_id)):
        assert 7000 < await redis.ttl(chave_redis) <= 7200


async def trocas_no_redis(app, conversa_id):
    trocas = await app.state.redis.lrange(chave_das_trocas(conversa_id), 0, -1)
    return [json.loads(troca) for troca in trocas]


async def test_sem_redis_a_conversa_segue_sem_historico(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    redis_original = app.state.redis
    app.state.redis = Redis.from_url('redis://127.0.0.1:1/0', socket_connect_timeout=0.2)
    try:
        corpo = {'pergunta': 'E agora?', 'conversa_id': primeira['conversa_id']}
        resposta = await http.post(URL, json=corpo, headers=headers)
    finally:
        await app.state.redis.aclose()
        app.state.redis = redis_original
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()['tipo'] == 'resposta'


async def test_historico_da_conversa_so_para_a_dona(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, FORA)
    perdas = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=perdas)).json()
    corpo = {'pergunta': 'E a França?', 'conversa_id': primeira['conversa_id']}
    await http.post(URL, json=corpo, headers=perdas)
    rota = f'/api/v1/assistente/conversas/{primeira["conversa_id"]}'
    historico = await http.get(rota, headers=perdas)
    assert historico.status_code == 200
    mensagens = historico.json()['mensagens']
    assert [m['pergunta'] for m in mensagens] == ['UCs?', 'E a França?']
    assert mensagens[0]['resposta'] == TEXTO and mensagens[1]['nao_sei']
    assert mensagens[0]['id_resposta'] == primeira['id_resposta']
    alheia = await http.get(rota, headers=await entrar(http, 'comercial'))
    assert alheia.status_code == 404 and alheia.json()['code'] == 'CONVERSA_NAO_ENCONTRADA'
    inexistente = await http.get(f'/api/v1/assistente/conversas/{uuid4()}', headers=perdas)
    assert inexistente.status_code == 404


async def test_resposta_com_consulta_entra_no_historico_mesmo_sem_metrica(portal):
    # A conferência pode descartar a métrica por um número sem lastro; os filtros, o
    # período e o SQL da troca ainda valem para o follow-up.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    usuario = await app.state.redis.get(chave(primeira['conversa_id']))
    consulta = Consulta(sql_gerado='SELECT 1', sql_executado='SELECT 1 LIMIT 1000')
    resposta = RespostaAgente(
        tipo='resposta',
        texto=TEXTO,
        filtros=['município = Recife'],
        consultas=[consulta],
        modelo='simulado',
    )
    await conversas.registrar(
        app.state.redis, primeira['conversa_id'], usuario.decode(), 'E Recife?', resposta, None
    )
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert [t['pergunta'] for t in trocas] == ['UCs?', 'E Recife?']
    assert trocas[1]['filtros'] == ['município = Recife'] and trocas[1]['metrica'] is None


async def test_consulta_que_falhou_no_banco_nao_entra_no_historico(portal):
    # O SQL que falhou em todas as tentativas tem sql_executado, mas também tem erro: o
    # follow-up não pode partir dele.
    app, http = portal
    usar_modelo(app, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    usuario = await app.state.redis.get(chave(primeira['conversa_id']))
    falhas = [
        Consulta(sql_gerado='SELECT x', sql_executado='SELECT x LIMIT 1000', erro=erro)
        for erro in ('Erro do banco: coluna x não existe', CONSULTA_INTERROMPIDA)
    ]
    resposta = RespostaAgente(
        tipo='nao_sei',
        texto='Não sei. Não consegui montar uma consulta válida.',
        filtros=['município = Recife'],
        consultas=falhas,
        modelo='simulado',
    )
    await conversas.registrar(
        app.state.redis, primeira['conversa_id'], usuario.decode(), 'E Recife?', resposta, None
    )
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert [t['pergunta'] for t in trocas] == ['UCs?']


async def test_troca_guarda_o_sql_que_rodou_e_nao_a_tentativa_que_falhou(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    usuario = await app.state.redis.get(chave(primeira['conversa_id']))
    resposta = RespostaAgente(
        tipo='resposta',
        texto=TEXTO,
        consultas=[
            Consulta(sql_gerado='SELECT 1', sql_executado='SELECT 1 LIMIT 1000'),
            Consulta(sql_gerado='SELECT x', sql_executado='SELECT x LIMIT 1000', erro='Erro'),
        ],
        modelo='simulado',
    )
    await conversas.registrar(
        app.state.redis, primeira['conversa_id'], usuario.decode(), 'E Recife?', resposta, None
    )
    trocas = await trocas_no_redis(app, primeira['conversa_id'])
    assert trocas[1]['sql'] == 'SELECT 1 LIMIT 1000'


class RedisQueNaoResponde:
    """Cada comando estoura com o TimeoutError nativo, que não vem embrulhado em
    RedisError."""

    def pipeline(self, *args, **kwargs):
        raise TimeoutError('timeout de conexão do redis')

    async def eval(self, *args):
        raise TimeoutError('timeout de conexão do redis')


async def test_timeout_do_redis_nao_derruba_a_conversa():
    redis = RedisQueNaoResponde()
    assert await conversas.ler(redis, uuid4(), uuid4()) == []
    resposta = RespostaAgente(tipo='resposta', texto=TEXTO, metrica='UCs', modelo='simulado')
    await conversas.registrar(redis, uuid4(), uuid4(), 'UCs?', resposta, None)
