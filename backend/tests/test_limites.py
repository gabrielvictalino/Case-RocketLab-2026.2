import asyncio
from uuid import uuid4

import anyio
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import ModelHTTPError
from redis.asyncio import Redis

from app.core import limites
from app.core.errors import APIError
from app.main import create_app
from app.modules.assistente import service
from app.modules.assistente.schemas import Pergunta
from test_assistente import PLANO, TEXTO, URL, entrar, usar_modelo

pytestmark = pytest.mark.integration


@pytest.fixture
async def redis(infrastructure):
    cliente = Redis.from_url(infrastructure['settings'].redis_url)
    yield cliente
    await cliente.aclose()


async def limpar_limites(redis):
    for padrao in ('rl:*', 'cota:*'):
        async for chave in redis.scan_iter(padrao):
            await redis.delete(chave)


@pytest.fixture
async def portal_limitado(infrastructure, db, redis):
    """App com 2 perguntas por minuto e sem os limites que os outros testes já gastaram."""
    settings = infrastructure['settings'].model_copy(
        update={'assistente_perguntas_por_minuto': 2, 'assistente_cota_tokens_dia': 10**9}
    )
    await limpar_limites(redis)
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as http,
    ):
        yield app, http
    await limpar_limites(redis)


async def test_limite_de_perguntas_por_minuto(portal_limitado):
    app, http = portal_limitado
    usar_modelo(app, PLANO, TEXTO, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    for _ in range(2):
        assert (await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)).status_code == 200
    barrada = await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)
    assert barrada.status_code == 429
    assert barrada.json()['code'] == 'LIMITE_DE_PERGUNTAS'
    assert 1 <= int(barrada.headers['Retry-After']) <= 60
    # O limite é por usuário: outro usuário segue perguntando.
    usar_modelo(app, PLANO, TEXTO)
    outro = await http.post(URL, json={'pergunta': 'UCs?'}, headers=await entrar(http, 'comercial'))
    assert outro.status_code == 200


async def test_janela_deslizante_libera_depois_de_um_minuto(redis):
    usuario = uuid4()
    for agora in (1000.0, 1010.0):
        await limites.consumir(redis, usuario, 'teste', 2, agora=agora)
    with pytest.raises(APIError) as barrada:
        await limites.consumir(redis, usuario, 'teste', 2, agora=1030.0)
    # A mais antiga sai da janela em 1060: faltam 30 s.
    assert barrada.value.headers == {'Retry-After': '30'}
    # A chamada barrada não entra na janela: em 1061 a primeira já saiu e sobra uma vaga.
    await limites.consumir(redis, usuario, 'teste', 2, agora=1061.0)
    with pytest.raises(APIError):
        await limites.consumir(redis, usuario, 'teste', 2, agora=1065.0)
    await limites.consumir(redis, usuario, 'teste', 2, agora=1071.0)


async def test_cota_diaria_de_tokens(portal_limitado, redis):
    app, http = portal_limitado
    usar_modelo(app, PLANO, TEXTO, PLANO, TEXTO)
    headers = await entrar(http, 'perdas')
    primeira = await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)
    gastos = primeira.json()['tokens_entrada'] + primeira.json()['tokens_saida']
    [chave] = [c async for c in redis.scan_iter('cota:*')]
    assert int(await redis.get(chave)) == gastos
    assert 0 < await redis.ttl(chave) <= limites.TTL_COTA_S
    # Com a cota do dia gasta, a pergunta seguinte é barrada até a meia-noite.
    app.state.settings = app.state.settings.model_copy(
        update={'assistente_cota_tokens_dia': gastos}
    )
    barrada = await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)
    assert barrada.status_code == 429
    assert barrada.json()['code'] == 'COTA_DE_TOKENS_ESGOTADA'
    assert 1 <= int(barrada.headers['Retry-After']) <= 24 * 60 * 60


async def test_cota_vira_a_meia_noite_de_recife(redis):
    usuario = uuid4()
    # 02:59 UTC de 3/11 ainda é 2/11 em Recife; 03:00 UTC já é 3/11.
    antes, depois = 1793674740.0, 1793674800.0
    await limites.reservar_cota(redis, usuario, 100, 100, agora=antes)
    with pytest.raises(APIError) as barrada:
        await limites.reservar_cota(redis, usuario, 100, 1, agora=antes)
    assert barrada.value.headers == {'Retry-After': '60'}
    await limites.reservar_cota(redis, usuario, 100, 1, agora=depois)


async def test_perguntas_ao_mesmo_tempo_nao_passam_com_o_mesmo_saldo(redis):
    # 90 de 100 tokens gastos e duas perguntas de 10 ao mesmo tempo: em sequência, a
    # segunda seria barrada. A reserva faz a simultânea ver o saldo da primeira.
    usuario, agora = uuid4(), 1793674800.0
    gasto = await limites.reservar_cota(redis, usuario, 100, 90, agora=agora)
    resultados = await asyncio.gather(
        *(limites.reservar_cota(redis, usuario, 100, 10, agora=agora) for _ in range(2)),
        return_exceptions=True,
    )
    reservas = [r for r in resultados if isinstance(r, limites.Reserva)]
    barradas = [r for r in resultados if isinstance(r, APIError)]
    assert len(reservas) == len(barradas) == 1
    assert barradas[0].code == 'COTA_DE_TOKENS_ESGOTADA'
    # No fim, cada reserva vira o gasto real.
    await limites.acertar_cota(redis, reservas[0], 12)
    await limites.acertar_cota(redis, gasto, 90)
    assert int(await redis.get(gasto.chave)) == 102


async def test_reserva_volta_quando_a_pergunta_nem_chega_ao_llm(portal_limitado, redis):
    app, http = portal_limitado
    usar_modelo(app)
    corpo = {'pergunta': 'E agora?', 'conversa_id': str(uuid4())}
    resposta = await http.post(URL, json=corpo, headers=await entrar(http, 'perdas'))
    assert resposta.status_code == 404
    [chave] = [c async for c in redis.scan_iter('cota:*')]
    assert int(await redis.get(chave)) == 0


async def test_tokens_de_uma_pergunta_que_falhou_tambem_contam(portal_limitado, redis):
    app, http = portal_limitado
    usar_modelo(app, PLANO, ModelHTTPError(503, 'simulado', 'indisponível'))
    resposta = await http.post(URL, json={'pergunta': 'Cai'}, headers=await entrar(http, 'perdas'))
    assert resposta.status_code == 503
    [chave] = [c async for c in redis.scan_iter('cota:*')]
    assert int(await redis.get(chave)) > 0


async def test_sem_redis_os_limites_ficam_abertos(portal_limitado):
    app, http = portal_limitado
    usar_modelo(app, *[PLANO, TEXTO] * 3)
    headers = await entrar(http, 'perdas')
    redis_original = app.state.redis
    app.state.redis = Redis.from_url('redis://127.0.0.1:1/0', socket_connect_timeout=0.2)
    try:
        for _ in range(3):
            resposta = await http.post(URL, json={'pergunta': 'UCs?'}, headers=headers)
            assert resposta.status_code == 200, resposta.text
    finally:
        await app.state.redis.aclose()
        app.state.redis = redis_original


async def test_contador_negativo_nao_trava_o_usuario(redis):
    # A chave pode sumir entre a reserva e o acerto (DEL manual, Redis sem persistência):
    # o acerto com diferença negativa não pode deixar o contador abaixo de zero, e um
    # contador negativo não pode responder 429 depois de já ter debitado a reserva.
    usuario, agora = uuid4(), 1793674800.0
    reserva = await limites.reservar_cota(redis, usuario, 100_000, 20_000, agora=agora)
    await redis.delete(reserva.chave)
    await limites.acertar_cota(redis, reserva, 1_000)
    assert int(await redis.get(reserva.chave)) == 0
    seguinte = await limites.reservar_cota(redis, usuario, 100_000, 20_000, agora=agora)
    assert seguinte.tokens == 20_000 and int(await redis.get(reserva.chave)) == 20_000
    # Um contador que já está negativo conta como zero.
    await redis.set(reserva.chave, -19_000)
    await limites.reservar_cota(redis, usuario, 100_000, 20_000, agora=agora)
    assert int(await redis.get(reserva.chave)) == 20_000


class RedisQuePerdeARespostaDaReserva:
    """O Redis da suíte, mas a resposta da reserva se perde num timeout depois de o
    script rodar: o débito aconteceu, e quem reservou não sabe."""

    def __init__(self, redis):
        self.redis = redis

    def __getattr__(self, nome):
        return getattr(self.redis, nome)

    async def eval(self, script, *args):
        resultado = await self.redis.eval(script, *args)
        if script == limites.RESERVAR:
            raise TimeoutError('resposta perdida')
        return resultado


async def test_timeout_depois_do_debito_nao_cobra_a_reserva(redis):
    usuario, agora = uuid4(), 1793674800.0
    reserva = await limites.reservar_cota(
        RedisQuePerdeARespostaDaReserva(redis), usuario, 100_000, 20_000, agora=agora
    )
    # A reserva volta com zero, mas o Redis debitou os 20 mil.
    assert reserva.tokens == 0 and int(await redis.get(reserva.chave)) == 20_000
    await limites.acertar_cota(redis, reserva, 1_000)
    assert int(await redis.get(reserva.chave)) == 1_000
    # Um segundo acerto da mesma reserva não desconta de novo.
    await limites.acertar_cota(redis, reserva, 1_000)
    assert int(await redis.get(reserva.chave)) == 2_000


async def test_acerto_sem_debito_cobra_so_o_gasto(redis):
    # O Redis não respondeu antes do script: nada foi debitado, e o acerto soma o gasto.
    usuario, agora = uuid4(), 1793674800.0
    chave = limites._chave_cota(usuario, agora)
    await limites.acertar_cota(redis, limites.Reserva(chave, 0, 'nunca-reservou'), 1_000)
    assert int(await redis.get(chave)) == 1_000


class AgenteQueEspera:
    async def responder(self, pergunta, contexto, andamento=None):
        # Já gastou o plano quando o cliente fecha o painel.
        andamento.uso.input_tokens = 1_000
        await asyncio.sleep(10)


class RedisQueEsperaAConexao:
    """O Redis da suíte, mas cada comando espera antes por uma conexão do pool, como num
    connect ou num checkout disputado: é nesse await que o cancelamento pega o acerto."""

    def __init__(self, redis):
        self.redis = redis

    def __getattr__(self, nome):
        return getattr(self.redis, nome)

    async def eval(self, *args):
        await asyncio.sleep(0.01)
        return await self.redis.eval(*args)


async def test_pergunta_abandonada_troca_a_reserva_pelo_gasto(portal_limitado, db, redis):
    # O cancel scope do middleware HTTP (anyio) cancela de novo a cada await. Sem a
    # blindagem, o acerto do finally morria no primeiro await e os 20 mil tokens da
    # reserva ficavam cobrados até a meia-noite.
    app, http = portal_limitado
    app.state.assistente = AgenteQueEspera()
    await entrar(http, 'perdas')
    usuario = {'id': await db.fetchval("SELECT id FROM operations.usuarios WHERE login = 'perdas'")}
    original = app.state.redis
    app.state.redis = RedisQueEsperaAConexao(original)
    try:
        with anyio.move_on_after(0.3):
            await service.perguntar(app.state, Pergunta(pergunta='Abandonei'), usuario)
        await asyncio.sleep(0.3)
    finally:
        app.state.redis = original
    [chave] = [c async for c in redis.scan_iter('cota:*')]
    assert int(await redis.get(chave)) == 1_000
