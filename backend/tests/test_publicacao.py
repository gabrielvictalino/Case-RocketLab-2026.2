"""Leituras do portal e publicação de cargas: a carga identificada e os números da mesma
resposta saem sempre da mesma publicação."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text

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


async def test_lock_da_troca_igual_no_importador_e_no_portal():
    assert loader.SWAP_LOCK == SWAP_LOCK
    assert loader.SWAP_LOCK != loader.PUBLICATION_LOCK


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
