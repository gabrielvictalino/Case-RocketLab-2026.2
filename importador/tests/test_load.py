import csv
import hashlib
import json
import shutil
from pathlib import Path

import asyncpg
import pytest
from redis.asyncio import Redis

from importador.contracts import ContractError
from importador.loader import load

pytestmark = pytest.mark.integration
SAMPLES = Path(__file__).resolve().parents[2] / 'contracts/samples'


def rewrite(origin, table, mutate):
    file = origin / f'{table}.csv'
    with file.open(newline='') as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        rows = list(reader)
    mutate(rows)
    with file.open('w', newline='') as out:
        writer = csv.DictWriter(out, columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    manifest_file = origin / 'manifest.json'
    manifest = json.loads(manifest_file.read_text())
    entry = manifest['tables'][table]
    entry['sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
    # Não atualiza contagem/totais: alguns cenários verificam exatamente esses gates.
    manifest_file.write_text(json.dumps(manifest))


async def analytics_snapshot(db):
    # Inclui conteúdo, identidade da carga e contagem, sem depender de ordem física.
    return (
        await db.fetch('SELECT * FROM analytics.dim_uc ORDER BY id_uc'),
        await db.fetch('SELECT * FROM analytics.fila_inspecao ORDER BY id_uc'),
        await db.fetchval('SELECT count(*) FROM operations.cargas'),
        await db.fetchval('SELECT sum(valor_total) FROM analytics.uc_consumo_faturamento_mensal'),
    )


@pytest.mark.parametrize(
    'failure',
    [
        'count',
        'hash',
        'type',
        'duplicate',
        'orphan',
        'total',
        'period',
        'version',
        'non_synthetic',
        'filename',
        'inspection',
        'aggregate',
    ],
)
async def test_invalid_import_preserves_previous(db, infrastructure, tmp_path, failure):
    origin = tmp_path / 'batch'
    shutil.copytree(SAMPLES, origin)
    manifest_file = origin / 'manifest.json'
    manifest = json.loads(manifest_file.read_text())
    if failure == 'count':
        manifest['tables']['dim_uc']['rows'] += 1
    elif failure == 'hash':
        manifest['tables']['dim_uc']['sha256'] = '0' * 64
    elif failure == 'total':
        manifest['tables']['uc_consumo_faturamento_mensal']['totals']['valor_total'] = '0'
    elif failure == 'period':
        manifest['period']['end'] = '2026-05'
    elif failure == 'version':
        manifest['contract_version'] = 'aprovado-inexistente'
    elif failure == 'non_synthetic':
        manifest['synthetic'] = False
    elif failure == 'filename':
        manifest['tables']['dim_uc']['file'] = '../../arquivo.csv'
    manifest_file.write_text(json.dumps(manifest))
    if failure == 'type':
        rewrite(origin, 'dim_uc', lambda rows: rows[0].update(flag_gd='talvez'))
    if failure == 'duplicate':
        rewrite(origin, 'dim_uc', lambda rows: rows[1].update(id_uc=rows[0]['id_uc']))
    if failure == 'orphan':
        rewrite(origin, 'fila_inspecao', lambda rows: rows[0].update(id_uc='UC999999'))
    if failure == 'inspection':
        rewrite(
            origin,
            'inspecoes_historicas',
            lambda rows: rows[0].update(resultado='SEM IRREGULARIDADE'),
        )
    if failure == 'aggregate':
        # Mantém os totais, deslocando receita de um bairro para outro.
        rewrite(origin, 'receita_volume_mensal', lambda rows: rows[0].update(bairro='Outro bairro'))
    before = await analytics_snapshot(db)
    with pytest.raises((ContractError, asyncpg.PostgresError)):
        await load(origin, infrastructure['importer_url'], infrastructure['settings'].redis_url)
    assert await analytics_snapshot(db) == before
    assert await db.fetchval("SELECT to_regnamespace('analytics_staging')") is None


async def test_publication_failure_rolls_back_renames_views_and_batch(db, infrastructure):
    # Dependência desconhecida provoca falha depois da promoção e CREATE OR REPLACE VIEW.
    await db.execute('CREATE VIEW operations.guarda_teste AS SELECT id_uc FROM analytics.dim_uc')
    before = await analytics_snapshot(db)
    view_before = await db.fetch('SELECT * FROM ai_read.inspecoes ORDER BY id_inspecao')
    try:
        with pytest.raises(asyncpg.DependentObjectsStillExistError):
            await load(SAMPLES, infrastructure['importer_url'])
        assert await analytics_snapshot(db) == before
        assert await db.fetch('SELECT * FROM ai_read.inspecoes ORDER BY id_inspecao') == view_before
        assert await db.fetchval("SELECT to_regnamespace('analytics_anterior')") is None
    finally:
        await db.execute('DROP VIEW operations.guarda_teste')


async def test_reload_preserves_operations_and_unified_view(client, headers, db, infrastructure):
    base = '/api/v1/ordens-inspecao'
    response = await client.post(base, headers=headers, json={'ucs': ['UC100001', 'UC100002']})
    order_id = response.json()['criadas'][0]['id']
    await client.post(
        f'{base}/{order_id}/despachar', headers=headers, json={'inspetor': 'INSP-001'}
    )
    result = await client.post(
        f'{base}/{order_id}/resultado',
        headers=headers,
        json={'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-06-20'},
    )
    assert result.status_code == 200
    tables = ['usuarios', 'ordens_inspecao', 'ordem_eventos', 'inspecoes']
    before = {t: await db.fetch(f'SELECT * FROM operations.{t} ORDER BY 1') for t in tables}
    old_count = await db.fetchval('SELECT count(*) FROM operations.cargas')
    for _ in range(2):
        version = await load(
            SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url
        )
        assert {
            t: await db.fetch(f'SELECT * FROM operations.{t} ORDER BY 1') for t in tables
        } == before
        origins = await db.fetch(
            'SELECT origem,count(*) n FROM ai_read.inspecoes GROUP BY origem ORDER BY origem'
        )
        assert [(r['origem'], r['n']) for r in origins] == [('historica', 2), ('portal', 1)]
    assert await db.fetchval('SELECT count(*) FROM operations.cargas') == old_count + 2
    assert await db.fetchval('SELECT count(*) FROM analytics.dim_uc') == 300
    redis = Redis.from_url(infrastructure['settings'].redis_url)
    try:
        assert (await redis.get('versao_carga')).decode() == str(version)
    finally:
        await redis.aclose()


async def test_redis_failure_does_not_undo_committed_import(db, infrastructure):
    before = await db.fetchval('SELECT count(*) FROM operations.cargas')
    version = await load(SAMPLES, infrastructure['importer_url'], 'redis://localhost:1/0')
    assert await db.fetchval('SELECT count(*) FROM operations.cargas') == before + 1
    assert (
        await db.fetchval('SELECT id FROM operations.cargas ORDER BY carregado_em DESC LIMIT 1')
        == version
    )
