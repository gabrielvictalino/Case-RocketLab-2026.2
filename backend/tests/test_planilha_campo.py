import asyncio
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from app.core.errors import APIError
from app.modules.perdas import planilha

BASE = '/api/v1/ordens-inspecao'
CABECALHO = list(planilha.COLUNAS_CAMPO)
integracao = pytest.mark.integration


def xlsx(*linhas, cabecalho=CABECALHO) -> bytes:
    livro = Workbook()
    folha = livro.active
    folha.append(cabecalho)
    for linha in linhas:
        folha.append(linha)
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def linha(id_ordem='', uc='UC100001', data='2026-01-20', inspetor='', resultado='NADA CONSTA',
          tipo='', kwh='0'):  # fmt: skip
    return ['', uc, data, inspetor, resultado, tipo, kwh, id_ordem]


def celulas(**valores) -> dict:
    return dict(zip(CABECALHO, linha(**valores)))


@pytest.mark.parametrize(
    'bruto,esperado',
    [
        ('2026-01-20', date(2026, 1, 20)),
        ('20/01/2026', date(2026, 1, 20)),
        ('20.01.2026', date(2026, 1, 20)),
        ('01-20-2026', date(2026, 1, 20)),
        (datetime(2026, 1, 20, 8, 30), date(2026, 1, 20)),
    ],
)
def test_datas_nos_formatos_da_silver(bruto, esperado):
    assert planilha.normalizar(2, celulas(data=bruto)).resultado.data == esperado


@pytest.mark.parametrize(
    'bruto,motivo',
    [
        ('31/02/2026', 'inexistente'),
        ('20 jan 2026', 'desconhecido'),
        ('', 'vazia'),
        ('2021-01-01', 'início da base'),
    ],
)
def test_datas_invalidas(bruto, motivo):
    assert motivo in planilha.normalizar(2, celulas(data=bruto)).motivo


def test_data_futura_e_barrada():
    amanha = (date.today() + timedelta(days=1)).isoformat()
    assert 'futura' in planilha.normalizar(2, celulas(data=amanha)).motivo


@pytest.mark.parametrize(
    'bruto,resultado,tipo',
    [
        ('confirmada', 'IRREGULARIDADE CONFIRMADA', 'BY-PASS'),
        ('  Irregularidade Confirmada ', 'IRREGULARIDADE CONFIRMADA', 'BY-PASS'),
    ],
)
def test_grafias_de_resultado(bruto, resultado, tipo):
    lida = planilha.normalizar(2, celulas(resultado=bruto, tipo=' by-pass ', kwh='10,5'))
    assert lida.resultado.resultado == resultado
    assert lida.resultado.tipo_irregularidade == tipo
    assert lida.resultado.kwh_recuperado == Decimal('10.50')
    assert lida.aviso is None


@pytest.mark.parametrize('ausencia', ['', '-', 'NULL', 'n/a', None])
def test_ausencias_de_tipo_viram_nulo(ausencia):
    lida = planilha.normalizar(2, celulas(tipo=ausencia))
    assert lida.resultado.tipo_irregularidade is None


@pytest.mark.parametrize(
    'bruto,esperado',
    [
        (125.5, '125.50'),
        (7, '7.00'),
        ('1,005', '1.01'),
        (Decimal('2.5'), '2.50'),
        (1.234, '1.23'),
        ('0.125', '0.13'),
        ('1500', '1500.00'),
    ],
)
def test_kwh(bruto, esperado):
    lida = planilha.normalizar(2, celulas(resultado='CONFIRMADA', tipo='BY-PASS', kwh=bruto))
    assert lida.resultado.kwh_recuperado == Decimal(esperado)


@pytest.mark.parametrize(
    'bruto', ['abc', 'NaN', 'Infinity', '1e3', '1.234,56', '1_000', '-3', True, None, '9' * 400]
)
def test_kwh_invalido(bruto):
    lida = planilha.normalizar(2, celulas(resultado='CONFIRMADA', tipo='BY-PASS', kwh=bruto))
    assert 'kWh' in lida.motivo


@pytest.mark.parametrize('bruto', ['1.500', '15.609', '1.234.567'])
def test_kwh_em_texto_com_ponto_de_milhar_e_ambiguo(bruto):
    lida = planilha.normalizar(2, celulas(resultado='CONFIRMADA', tipo='BY-PASS', kwh=bruto))
    assert 'ambíguo' in lida.motivo


def test_coerencia_vem_das_regras_do_resultado():
    sem_tipo = planilha.normalizar(2, celulas(resultado='CONFIRMADA', kwh='5'))
    assert sem_tipo.motivo == 'Irregularidade exige tipo e kWh recuperado > 0'
    com_kwh = planilha.normalizar(2, celulas(kwh='5'))
    assert com_kwh.motivo == 'Sem irregularidade exige kWh = 0 e tipo nulo'


def test_tipo_novo_e_aviso_e_a_linha_segue_valida():
    lida = planilha.normalizar(2, celulas(resultado='CONFIRMADA', tipo='BYPASS', kwh='5'))
    assert 'BYPASS' in lida.aviso


def test_todos_os_erros_da_linha_aparecem_juntos():
    motivo = planilha.normalizar(2, celulas(uc='X', data='?', resultado='TALVEZ')).motivo
    assert 'Resultado desconhecido' in motivo and 'UC fora' in motivo and 'formato' in motivo


def test_linha_sem_preencher_e_ignorada():
    assert planilha.normalizar(2, celulas(data='', resultado='', kwh='')) is None


def test_linha_parcial_sem_resultado_continua_erro():
    lida = planilha.normalizar(2, celulas(data='', resultado='', tipo='BY-PASS', kwh=''))
    assert 'Resultado vazio' in lida.motivo


def test_ler_numera_como_o_excel_e_pula_linhas_vazias():
    conteudo = xlsx(linha(), [None] * 8, linha(uc='UC100002'))
    assert [numero for numero, _ in planilha.ler(conteudo)] == [2, 4]


def test_ler_tira_nul_que_o_leitor_decodifica():
    [(_, valores)] = planilha.ler(xlsx(linha(tipo='A_x0000_B')))
    assert '\x00' not in valores['tipo_irregularidade']


@pytest.mark.parametrize(
    'conteudo,code',
    [
        (b'isto nao e zip', 'PLANILHA_INVALIDA'),
        (xlsx(linha(), cabecalho=CABECALHO[:-1]), 'PLANILHA_INVALIDA'),
        (xlsx(), 'PLANILHA_INVALIDA'),
        (xlsx(linha(), cabecalho=CABECALHO + ['data']), 'PLANILHA_INVALIDA'),
        (b'0' * (planilha.LIMITE_BYTES + 1), 'PLANILHA_GRANDE'),
    ],
)
def test_arquivos_recusados(conteudo, code):
    with pytest.raises(APIError) as erro:
        planilha.ler(conteudo)
    assert erro.value.code == code


def test_limite_de_linhas():
    linhas = [linha() for _ in range(planilha.LIMITE_LINHAS + 1)]
    with pytest.raises(APIError) as erro:
        planilha.ler(xlsx(*linhas))
    assert erro.value.status_code == 413


def test_limite_do_que_descompacta():
    saida = BytesIO()
    with ZipFile(saida, 'w', compression=8) as pacote:
        pacote.writestr('a.xml', b'0' * (planilha.LIMITE_DESCOMPACTADO + 1))
    with pytest.raises(APIError) as erro:
        planilha.ler(saida.getvalue())
    assert erro.value.code == 'PLANILHA_GRANDE'


def test_texto_com_igual_nao_vira_formula():
    conteudo = planilha.gerar('Teste', ['a'], [['=1+1']])
    folha = load_workbook(BytesIO(conteudo)).active
    assert folha['A2'].data_type == 's' and folha['A2'].value == '=1+1'


@pytest.mark.parametrize(
    'bruto,esperado',
    [('C:\\pasta\\campo.xlsx', 'campo.xlsx'), ('../a/b.xlsx', 'b.xlsx'), ('a\nb.xlsx', 'ab.xlsx')],
)
def test_nome_do_arquivo(bruto, esperado):
    assert planilha.nome_do_arquivo(bruto) == esperado


async def criar_em_campo(client, headers, uc='UC100001', inspetor='INSP-001'):
    criada = await client.post(BASE, headers=headers, json={'ucs': [uc]})
    assert criada.status_code == 201, criada.text
    id_ = criada.json()['criadas'][0]['id']
    await client.post(f'{BASE}/{id_}/despachar', headers=headers, json={'inspetor': inspetor})
    return id_


async def enviar(client, headers, conteudo, nome='campo.xlsx'):
    return await client.post(
        BASE + '/importacoes',
        headers=headers,
        files={'arquivo': (nome, conteudo, planilha.XLSX)},
    )


async def login(client, cargo):
    resposta = await client.post(
        '/api/v1/auth/login', json={'login': cargo, 'senha': 'Demo-Venergy-2026!'}
    )
    return {'Authorization': 'Bearer ' + resposta.json()['access_token']}


@integracao
async def test_exporta_a_fila_com_filtro(client, headers):
    resposta = await client.get('/api/v1/perdas/fila', headers=headers)
    item = resposta.json()['items'][0]
    exportada = await client.get(
        '/api/v1/perdas/fila/export', headers=headers, params={'municipio': item['municipio']}
    )
    assert exportada.status_code == 200
    assert exportada.headers['content-type'] == planilha.XLSX
    assert 'fila-de-inspecao.xlsx' in exportada.headers['content-disposition']
    linhas = list(load_workbook(BytesIO(exportada.content)).active.values)
    assert linhas[0][0] == 'UC' and linhas[1][0] == item['id_uc']
    assert {linha[1] for linha in linhas[1:]} == {item['municipio']}
    assert linhas[1][6] == float(item['energia_recuperar_kwh'])


@integracao
async def test_fila_exportada_e_a_mesma_da_paginada(client, headers):
    paginada = (await client.get('/api/v1/perdas/fila?size=100', headers=headers)).json()
    exportada = await client.get('/api/v1/perdas/fila/export', headers=headers)
    linhas = list(load_workbook(BytesIO(exportada.content)).active.values)[1:]
    assert len(linhas) == paginada['total']
    assert [linha[0] for linha in linhas[:100]] == [i['id_uc'] for i in paginada['items']]
    for linha_exportada, item in zip(linhas, paginada['items']):
        anterior = item['inspecao_anterior']
        data = linha_exportada[8].date().isoformat() if linha_exportada[8] else None
        assert data == (anterior and anterior['data'])
        assert linha_exportada[9] == (anterior and anterior['resultado'])


@integracao
async def test_exporta_so_ordens_em_campo(client, headers):
    em_campo = await criar_em_campo(client, headers)
    await client.post(BASE, headers=headers, json={'ucs': ['UC100002']})
    resposta = await client.get(BASE + '/export', headers=headers)
    linhas = list(load_workbook(BytesIO(resposta.content)).active.values)
    assert linhas[0] == tuple(CABECALHO)
    assert linhas[1:] == [(None, 'UC100001', None, 'INSP-001', None, None, None, em_campo)]


@integracao
async def test_planilha_mista_e_confirmacao_unica(client, headers, db):
    por_id = await criar_em_campo(client, headers, 'UC100001')
    por_uc = await criar_em_campo(client, headers, 'UC100002', 'INSP-002')
    conteudo = xlsx(
        linha(por_id, 'UC100001', '01-20-2026', 'insp-001 ', 'confirmada', 'by-pass', '125,50'),
        linha('', 'UC100002', '20/01/2026'),
        linha(str(uuid4()), 'UC100001'),
        linha('', 'UC100003', data='31/02/2026'),
    )
    previa = await enviar(client, headers, conteudo)
    assert previa.status_code == 201, previa.text
    corpo = previa.json()
    assert corpo['arquivo'] == 'campo.xlsx'
    assert [item['linha'] for item in corpo['validas']] == [2, 3]
    assert corpo['validas'][0]['data'] == '2026-01-20'
    assert corpo['validas'][1]['id_ordem'] == por_uc
    assert corpo['erros'][0] == {'linha': 4, 'motivo': 'Ordem não encontrada'}
    assert 'inexistente' in corpo['erros'][1]['motivo']
    # A prévia não muda nada.
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 0

    url = f'{BASE}/importacoes/{corpo["id"]}/confirmar'
    confirmada = await client.post(url, headers=headers)
    assert confirmada.status_code == 200, confirmada.text
    assert confirmada.json()['atualizadas'] == 2 and confirmada.json()['rejeitadas'] == []
    inspecao = await db.fetchrow(
        'SELECT * FROM operations.inspecoes WHERE id_ordem=$1', UUID(por_id)
    )
    assert inspecao['data'] == date(2026, 1, 20) and inspecao['inspetor'] == 'INSP-001'
    assert inspecao['kwh_recuperado'] == Decimal('125.50')
    dados = json.loads(
        await db.fetchval(
            "SELECT dados FROM operations.ordem_eventos WHERE tipo='RESULTADO' AND id_ordem=$1",
            UUID(por_id),
        )
    )
    assert dados['origem'] == {'importacao': corpo['id'], 'linha': 2}

    repetida = await client.post(url, headers=headers)
    assert repetida.status_code == 409
    assert repetida.json()['code'] == 'IMPORTACAO_JA_CONFIRMADA'
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 2


@integracao
async def test_confirmacoes_simultaneas_aplicam_uma_vez(client, headers, db):
    id_ = await criar_em_campo(client, headers)
    previa = (await enviar(client, headers, xlsx(linha(id_)))).json()
    url = f'{BASE}/importacoes/{previa["id"]}/confirmar'
    respostas = await asyncio.gather(*[client.post(url, headers=headers) for _ in range(4)])
    assert sorted(resposta.status_code for resposta in respostas) == [200, 409, 409, 409]
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 1


@integracao
@pytest.mark.parametrize(
    'preparar,motivo',
    [
        ('concluir', 'Ordem já concluída'),
        ('cancelar', 'Ordem cancelada'),
        ('tentativa', 'Ordem ainda não foi despachada'),
    ],
)
async def test_ordem_fora_de_campo_e_erro_de_linha(client, headers, preparar, motivo):
    id_ = await criar_em_campo(client, headers)
    acoes = {
        'concluir': (
            'resultado',
            {'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-01-01'},
        ),
        'cancelar': ('cancelar', {'motivo': 'Duplicada'}),
        'tentativa': ('tentativas', {'observacao': 'Imóvel fechado'}),
    }
    acao, corpo = acoes[preparar]
    await client.post(f'{BASE}/{id_}/{acao}', headers=headers, json=corpo)
    previa = (await enviar(client, headers, xlsx(linha(id_)))).json()
    assert previa['validas'] == []
    assert previa['erros'] == [{'linha': 2, 'motivo': motivo}]
    sem_linhas = await client.post(f'{BASE}/importacoes/{previa["id"]}/confirmar', headers=headers)
    assert sem_linhas.status_code == 409 and sem_linhas.json()['code'] == 'IMPORTACAO_SEM_LINHAS'


@integracao
async def test_uc_sem_ordem_uc_trocada_e_inspetor_trocado(client, headers):
    id_ = await criar_em_campo(client, headers)
    outra = await criar_em_campo(client, headers, 'UC100003')
    conteudo = xlsx(
        linha('', 'UC100002'),
        linha(id_, 'UC100002'),
        linha(outra, 'UC100003', inspetor='INSP-009'),
    )
    erros = (await enviar(client, headers, conteudo)).json()['erros']
    assert erros == [
        {'linha': 2, 'motivo': 'UC sem ordem ativa'},
        {'linha': 3, 'motivo': 'A UC da linha não é a da ordem (UC100001)'},
        {'linha': 4, 'motivo': 'Inspetor diferente do despachado na ordem (INSP-001)'},
    ]


@integracao
async def test_ordem_repetida_invalida_as_duas_linhas(client, headers):
    id_ = await criar_em_campo(client, headers)
    corpo = (await enviar(client, headers, xlsx(linha(id_), linha('', 'UC100001')))).json()
    assert corpo['validas'] == []
    assert [item['motivo'] for item in corpo['erros']] == ['Ordem repetida nas linhas 2, 3'] * 2


@integracao
@pytest.mark.parametrize(
    'copia,motivo',
    [
        ({'kwh': 'abc'}, 'kWh recuperado inválido'),
        ({'inspetor': 'INSP-009'}, 'Inspetor diferente'),
        ({'uc': 'UC100002'}, 'A UC da linha não é a da ordem'),
        ({'id_ordem': '', 'kwh': 'abc'}, 'kWh recuperado inválido'),
    ],
)
async def test_copia_com_erro_tambem_invalida_a_outra(client, headers, copia, motivo):
    id_ = await criar_em_campo(client, headers)
    conteudo = xlsx(linha(**{'id_ordem': id_, **copia}), linha(id_))
    corpo = (await enviar(client, headers, conteudo)).json()
    assert corpo['validas'] == []
    assert corpo['erros'][0]['linha'] == 2 and motivo in corpo['erros'][0]['motivo']
    repetida = 'Ordem repetida nas linhas 2, 3'
    assert repetida in corpo['erros'][0]['motivo']
    assert corpo['erros'][1] == {'linha': 3, 'motivo': repetida}


@integracao
async def test_linha_sem_preencher_nao_vira_erro_nem_repeticao(client, headers):
    id_ = await criar_em_campo(client, headers)
    em_branco = ['', 'UC100001', '', 'INSP-001', '', '', '', id_]
    corpo = (await enviar(client, headers, xlsx(em_branco, linha(id_)))).json()
    assert corpo['ignoradas'] == 1 and corpo['erros'] == []
    assert [item['linha'] for item in corpo['validas']] == [3]


@integracao
async def test_ordem_que_muda_depois_da_previa_nao_e_aplicada(client, headers, db):
    primeira = await criar_em_campo(client, headers, 'UC100001')
    segunda = await criar_em_campo(client, headers, 'UC100002', 'INSP-002')
    previa = (
        await enviar(client, headers, xlsx(linha(primeira), linha(segunda, 'UC100002')))
    ).json()
    await client.post(f'{BASE}/{primeira}/cancelar', headers=headers, json={'motivo': 'Duplicada'})
    confirmada = await client.post(f'{BASE}/importacoes/{previa["id"]}/confirmar', headers=headers)
    assert confirmada.json()['atualizadas'] == 1
    assert confirmada.json()['rejeitadas'] == [
        {'linha': 2, 'motivo': 'A ordem mudou de estado depois da prévia'}
    ]
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 1


@integracao
async def test_ultima_importacao(client, headers):
    assert (await client.get(BASE + '/importacoes/ultima', headers=headers)).json() is None
    id_ = await criar_em_campo(client, headers)
    previa = (await enviar(client, headers, xlsx(linha(id_)), 'junho.xlsx')).json()
    # Prévia sem confirmar não conta como importação.
    assert (await client.get(BASE + '/importacoes/ultima', headers=headers)).json() is None
    await client.post(f'{BASE}/importacoes/{previa["id"]}/confirmar', headers=headers)
    ultima = (await client.get(BASE + '/importacoes/ultima', headers=headers)).json()
    assert ultima['arquivo'] == 'junho.xlsx' and ultima['atualizadas'] == 1


@integracao
async def test_so_o_cargo_perdas_importa(client, headers):
    diretoria = await login(client, 'diretoria')
    assert (await enviar(client, diretoria, xlsx(linha()))).status_code == 403
    previa = (await enviar(client, headers, xlsx(linha()))).json()
    confirmar = await client.post(f'{BASE}/importacoes/{previa["id"]}/confirmar', headers=diretoria)
    assert confirmar.status_code == 403
    assert (await client.get(BASE + '/export', headers=diretoria)).status_code == 200


@integracao
async def test_exportacoes_exigem_login(client):
    assert (await client.get(BASE + '/export')).status_code == 401
    assert (await client.get('/api/v1/perdas/fila/export')).status_code == 401


@integracao
async def test_arquivo_invalido_e_importacao_inexistente(client, headers, db):
    invalido = await enviar(client, headers, b'nao e planilha')
    assert invalido.status_code == 422 and invalido.json()['code'] == 'PLANILHA_INVALIDA'
    assert await db.fetchval('SELECT count(*) FROM operations.importacoes') == 0
    faltando = await client.post(f'{BASE}/importacoes/{uuid4()}/confirmar', headers=headers)
    assert faltando.status_code == 404
