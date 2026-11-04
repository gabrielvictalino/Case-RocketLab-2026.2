"""Leituras do portal e publicação de cargas: a carga identificada e os números da mesma
resposta saem sempre da mesma publicação."""

import asyncio
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core import database
from app.core.database import SWAP_LOCK, sincronizar_com_a_publicacao
from app.modules.meta import repository as meta
from importador import loader

pytestmark = pytest.mark.integration
SAMPLES = Path(__file__).resolve().parents[2] / 'contracts/samples'


async def esperando_o_lock(db):
    while not await db.fetchval(
        """SELECT EXISTS(SELECT 1 FROM pg_locks
        WHERE locktype='advisory' AND objid=$1 AND NOT granted)""",
        SWAP_LOCK,
    ):
        await asyncio.sleep(0.01)


LOGIN = {'login': 'perdas', 'senha': 'Demo-Venergy-2026!'}


async def test_lock_da_troca_igual_no_importador_e_no_portal():
    assert loader.SWAP_LOCK == SWAP_LOCK
    assert loader.SWAP_LOCK != loader.PUBLICATION_LOCK


def test_prazos_da_troca_sao_compativeis():
    # A leitura espera mais que o importador pode prender a fila (na espera pelo lock e nos
    # locks da troca) e expira no servidor antes de o asyncpg cancelar o comando.
    assert 2 * loader.ESPERA_DA_TROCA_MS < database.ESPERA_DA_PUBLICACAO_MS
    assert database.ESPERA_DA_PUBLICACAO_MS < database.COMMAND_TIMEOUT_S * 1000


async def test_leitura_longa_nao_derruba_o_portal_durante_a_importacao(portal, db, infrastructure):
    """Uma transação aberta além do command_timeout enquanto o importador espera a troca:
    as requisições novas, inclusive o login, seguem respondendo, e a carga sai depois."""
    app, http = portal
    tarefa = None
    try:
        async with app.state.portal_sessions() as sessao, sessao.begin():
            await sincronizar_com_a_publicacao(sessao)
            antes = (await meta.carga_atual(sessao))['id']
            tarefa = asyncio.create_task(loader.load(SAMPLES, infrastructure['importer_url']))
            await asyncio.wait_for(esperando_o_lock(db), timeout=30)
            fim = time.monotonic() + database.COMMAND_TIMEOUT_S + 1
            while time.monotonic() < fim:
                resposta = await http.post('/api/v1/auth/login', json=LOGIN)
                assert resposta.status_code == 200, resposta.json()
            assert not tarefa.done()
        nova = await asyncio.wait_for(tarefa, timeout=30)
    finally:
        if tarefa is not None and not tarefa.done():
            await tarefa
    assert nova != antes


async def test_espera_pela_troca_expirada_vira_503(portal, db, monkeypatch):
    app, http = portal
    monkeypatch.setattr(database, 'ESPERA_DA_PUBLICACAO_MS', 200)
    async with db.transaction():
        await db.execute('SELECT pg_advisory_xact_lock($1)', SWAP_LOCK)
        resposta = await http.post('/api/v1/auth/login', json=LOGIN)
    assert resposta.status_code == 503
    assert resposta.json()['code'] == 'CARGA_EM_PUBLICACAO'
    assert resposta.headers['Retry-After']
    # A conexão volta limpa ao pool e o prazo curto não vale para o resto da transação.
    assert (await http.post('/api/v1/auth/login', json=LOGIN)).status_code == 200
    async with app.state.portal_sessions() as sessao, sessao.begin():
        padrao = await sessao.scalar(text('SHOW lock_timeout'))
        await sincronizar_com_a_publicacao(sessao)
        assert await sessao.scalar(text('SHOW lock_timeout')) == padrao


async def test_troca_ocupada_recusa_a_carga_e_preserva_a_anterior(
    portal, db, infrastructure, monkeypatch
):
    app, _ = portal
    monkeypatch.setattr(loader, 'ESPERA_DA_TROCA_MS', 200)
    monkeypatch.setattr(loader, 'TENTATIVAS_DA_TROCA', 2)
    monkeypatch.setattr(loader, 'PAUSA_ENTRE_TENTATIVAS_S', 0.1)
    async with app.state.portal_sessions() as sessao, sessao.begin():
        await sincronizar_com_a_publicacao(sessao)
        antes = (await meta.carga_atual(sessao))['id']
        with pytest.raises(loader.TrocaOcupada):
            await asyncio.wait_for(loader.load(SAMPLES, infrastructure['importer_url']), timeout=30)
    async with app.state.portal_sessions() as sessao, sessao.begin():
        await sincronizar_com_a_publicacao(sessao)
        assert (await meta.carga_atual(sessao))['id'] == antes
    assert not await db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='analytics_staging')"
    )


async def test_carga_nao_e_publicada_no_meio_de_uma_leitura(portal, db, infrastructure):
    app, _ = portal
    tarefa = None
    try:
        async with app.state.portal_sessions() as sessao, sessao.begin():
            await sincronizar_com_a_publicacao(sessao)
            antes = (await meta.carga_atual(sessao))['id']
            tarefa = asyncio.create_task(loader.load(SAMPLES, infrastructure['importer_url']))
            # O importador valida tudo e para na troca, esperando a leitura terminar.
            await asyncio.wait_for(esperando_o_lock(db), timeout=30)
            assert not tarefa.done()
            # A mesma transação segue lendo a carga e as tabelas que identificou.
            assert (await meta.carga_atual(sessao))['id'] == antes
            ucs = await sessao.scalar(text('SELECT count(*) FROM analytics.dim_uc'))
            assert ucs > 0
        nova = await asyncio.wait_for(tarefa, timeout=30)
    finally:
        if tarefa is not None and not tarefa.done():
            await tarefa
    assert nova != antes
    async with app.state.portal_sessions() as sessao, sessao.begin():
        await sincronizar_com_a_publicacao(sessao)
        assert (await meta.carga_atual(sessao))['id'] == nova


async def test_leitura_que_chega_durante_a_troca_ve_a_carga_nova(portal, db, infrastructure):
    app, _ = portal
    async with app.state.portal_sessions() as primeira, primeira.begin():
        await sincronizar_com_a_publicacao(primeira)
        antes = (await meta.carga_atual(primeira))['id']
        tarefa = asyncio.create_task(loader.load(SAMPLES, infrastructure['importer_url']))
        await asyncio.wait_for(esperando_o_lock(db), timeout=30)

        async def ler():
            async with app.state.portal_sessions() as sessao, sessao.begin():
                await sincronizar_com_a_publicacao(sessao)
                return (await meta.carga_atual(sessao))['id']

        # A segunda leitura entra na fila atrás do importador, não ao lado da primeira.
        segunda = asyncio.create_task(ler())
        await asyncio.sleep(0.2)
        assert not segunda.done()
    nova = await asyncio.wait_for(tarefa, timeout=30)
    assert await asyncio.wait_for(segunda, timeout=10) == nova != antes
