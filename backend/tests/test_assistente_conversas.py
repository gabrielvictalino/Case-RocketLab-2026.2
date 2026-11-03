import json
from uuid import uuid4

import pytest
from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from redis.asyncio import Redis
from venergy_ai.agente import AgenteTextoSQL
from venergy_ai.executor import ExecutorAiRead

from app.modules.assistente.conversas import chave
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
    estado = json.loads(await redis.get(chave(conversa_id)))
    assert [t['pergunta'] for t in estado['trocas']] == [f'Pergunta {n}' for n in range(1, 6)]
    assert estado['trocas'][-1]['metrica'] == PLANO['metrica']
    assert 7000 < await redis.ttl(chave(conversa_id)) <= 7200


async def test_resposta_fora_do_dominio_nao_muda_o_estado(portal):
    app, http = portal
    usar_modelo(app, PLANO, TEXTO, FORA)
    headers = await entrar(http, 'perdas')
    primeira = (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).json()
    corpo = {'pergunta': 'Qual a capital da França?', 'conversa_id': primeira['conversa_id']}
    assert (await http.post(URL, json=corpo, headers=headers)).json()['tipo'] == 'nao_sei'
    estado = json.loads(await app.state.redis.get(chave(primeira['conversa_id'])))
    assert [t['pergunta'] for t in estado['trocas']] == ['UCs?']


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
