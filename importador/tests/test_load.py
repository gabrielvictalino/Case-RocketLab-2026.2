import asyncio
import csv
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

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


@pytest.mark.parametrize('failure', ['duplicate', 'orphan'])
async def test_key_errors_identify_table_column_and_value(db, infrastructure, tmp_path, failure):
    origin = tmp_path / 'batch'
    shutil.copytree(SAMPLES, origin)
    if failure == 'duplicate':
        rewrite(origin, 'dim_uc', lambda rows: rows[1].update(id_uc=rows[0]['id_uc']))
        expected = ['dim_uc', 'id_uc', 'UC100000', 'duplicada']
    else:
        rewrite(origin, 'fila_inspecao', lambda rows: rows[0].update(id_uc='UC999999'))
        expected = ['fila_inspecao', 'id_uc', 'UC999999', 'dim_uc', 'inexistente']
    with pytest.raises(ContractError) as error:
        await load(origin, infrastructure['importer_url'])
    assert all(fragment in str(error.value) for fragment in expected)


async def test_non_synthetic_manifest_keeps_provenance(db, infrastructure, tmp_path):
    # Simula a indicação de proveniência real; a fixture continua sendo sintética.
    origin = tmp_path / 'exportacao'
    shutil.copytree(SAMPLES, origin)
    file = origin / 'manifest.json'
    manifest = json.loads(file.read_text())
    manifest['synthetic'] = False
    file.write_text(json.dumps(manifest))
    try:
        version = await load(origin, infrastructure['importer_url'])
        assert (
            await db.fetchval('SELECT sintetica FROM operations.cargas WHERE id=$1', version)
            is False
        )
    finally:
        await load(SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)


def csv_rows(origin, name):
    with (origin / f'{name}.csv').open(newline='') as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize('corruption', [None, 'tarifa', 'duracao'])
async def test_rounded_derivatives_and_tariff_precision(db, infrastructure, tmp_path, corruption):
    origin = tmp_path / 'batch'
    shutil.copytree(SAMPLES, origin)
    rewrite(
        origin,
        'uc_consumo_faturamento_mensal',
        lambda rows: rows[0].update(tarifa_base='0.7845', adicional_bandeira='0.016950'),
    )
    dims = {r['id_uc']: r for r in csv_rows(origin, 'dim_uc')}
    components = {}

    def key(row):
        return tuple(row[c] for c in ['competencia', 'municipio', 'bairro', 'classe', 'grupo_uc'])

    for row in csv_rows(origin, 'uc_consumo_faturamento_mensal'):
        group = key({**row, **dims[row['id_uc']]})
        totals = components.setdefault(group, [Decimal(0), Decimal(0)])
        tarifa = Decimal(row['tarifa_base']) if row['tarifa_base'] else Decimal(0)
        bandeira = Decimal(row['adicional_bandeira']) if row['adicional_bandeira'] else Decimal(0)
        totals[0] += Decimal(row['volume_faturado_kwh']) * tarifa
        totals[1] += Decimal(row['volume_faturado_kwh']) * bandeira

    def aggregate(rows):
        for row in rows:
            for column, total in zip(
                ['componente_tarifa_reais', 'componente_bandeira_reais'], components[key(row)]
            ):
                row[column] = str(total.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        if corruption == 'tarifa':
            rows[0]['componente_tarifa_reais'] = str(
                Decimal(rows[0]['componente_tarifa_reais']) + 1
            )

    rewrite(origin, 'receita_volume_mensal', aggregate)

    def duration(rows):
        rows[0].update(
            data_encerramento=(
                datetime.fromisoformat(rows[0]['data_abertura']) + timedelta(seconds=80)
            ).isoformat(),
            duracao_min='1.33' if corruption != 'duracao' else '1.34',
            duracao_efetiva_min='1.33',
        )

    rewrite(origin, 'ocorrencias_uc', duration)
    file = origin / 'manifest.json'
    manifest = json.loads(file.read_text())
    for column in manifest['tables']['ocorrencias_uc']['totals']:
        manifest['tables']['ocorrencias_uc']['totals'][column] = str(
            sum(Decimal(r[column]) for r in csv_rows(origin, 'ocorrencias_uc'))
        )
    file.write_text(json.dumps(manifest))
    before = await analytics_snapshot(db)
    try:
        if corruption:
            with pytest.raises(ContractError):
                await load(origin, infrastructure['importer_url'])
            assert await analytics_snapshot(db) == before
        else:
            await load(origin, infrastructure['importer_url'])
            assert await db.fetchval("""SELECT tarifa_base
                FROM analytics.uc_consumo_faturamento_mensal
                ORDER BY id_uc,competencia LIMIT 1""") == Decimal('0.7845')
    finally:
        await load(SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)


async def test_delayed_redis_serializes_next_publication(db, infrastructure, monkeypatch):
    from importador import loader

    paused, release = asyncio.Event(), asyncio.Event()
    original = loader.publish_redis
    first = True

    async def delayed(url, version):
        nonlocal first
        if first:
            first = False
            paused.set()
            await release.wait()
        await original(url, version)

    monkeypatch.setattr(loader, 'publish_redis', delayed)
    args = (SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)
    task_a = asyncio.create_task(load(*args))
    task_b = None
    try:
        await asyncio.wait_for(paused.wait(), timeout=10)
        committed = await db.fetchval('SELECT count(*) FROM operations.cargas')
        task_b = asyncio.create_task(load(*args))

        async def waiting_on_lock():
            while not await db.fetchval("""SELECT EXISTS(
                SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted)"""):
                await asyncio.sleep(0.01)

        await asyncio.wait_for(waiting_on_lock(), timeout=5)
        assert not task_b.done()
        assert await db.fetchval('SELECT count(*) FROM operations.cargas') == committed
    finally:
        release.set()
        versions = await asyncio.gather(*[t for t in [task_a, task_b] if t is not None])
    latest = await db.fetchval(
        'SELECT id FROM operations.cargas ORDER BY ordem_publicacao DESC LIMIT 1'
    )
    assert latest == versions[-1]
    redis = Redis.from_url(infrastructure['settings'].redis_url)
    try:
        assert (await redis.get('versao_carga')).decode() == str(latest)
    finally:
        await redis.aclose()


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
        for schema in ['portal_read', 'ai_read']:
            origins = await db.fetch(
                f'SELECT origem,count(*) n FROM {schema}.inspecoes GROUP BY origem ORDER BY origem'
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
    try:
        version = await load(SAMPLES, infrastructure['importer_url'], 'redis://localhost:1/0')
        assert await db.fetchval('SELECT count(*) FROM operations.cargas') == before + 1
        assert (
            await db.fetchval('SELECT id FROM operations.cargas ORDER BY carregado_em DESC LIMIT 1')
            == version
        )
    finally:
        await load(SAMPLES, infrastructure['importer_url'], infrastructure['settings'].redis_url)


@pytest.mark.parametrize(
    'gate,table,mutate,expected_table,expected_rule',
    [
        (
            'r2_null_invoice',
            'uc_consumo_faturamento_mensal',
            lambda rows: rows[0].update(id_fatura=''),  # deixa outros campos preenchidos
            'uc_consumo_faturamento_mensal',
            'R2',
        ),
        (
            'r2_payment_paga',
            'uc_consumo_faturamento_mensal',
            lambda rows: rows[0].update(status_pagamento='PAGA', valor_arrecadado='0.00'),
            'uc_consumo_faturamento_mensal',
            'R2',
        ),
        (
            'r2_payment_aberta',
            'uc_consumo_faturamento_mensal',
            lambda rows: rows[0].update(status_pagamento='ABERTA', valor_arrecadado='50.00'),
            'uc_consumo_faturamento_mensal',
            'R2',
        ),
        (
            'r2_meter_exchange',
            'uc_consumo_faturamento_mensal',
            lambda rows: rows[0].update(
                flag_troca_medidor='true', metodo_consumo='LEITURA_UTILIZAVEL'
            ),
            'uc_consumo_faturamento_mensal',
            'R2',
        ),
        (
            'r2_leitura_consumo_alterado',
            'uc_consumo_faturamento_mensal',
            # Volume faturado intacto: só o gate de LEITURA_UTILIZAVEL detecta a divergência
            lambda rows: next(
                r
                for r in rows
                if r['metodo_consumo'] == 'LEITURA_UTILIZAVEL'
                and r['consumo_kwh_original'] != '999.00'
            ).update(consumo_kwh_analitico='999.00'),
            'uc_consumo_faturamento_mensal',
            'LEITURA_UTILIZAVEL exige consumo analítico igual ao original (R2)',
        ),
        (
            'r2_volume_analitico',
            'uc_consumo_faturamento_mensal',
            lambda rows: next(
                r for r in rows if r['id_fatura'] and r['metodo_consumo'] != 'LEITURA_UTILIZAVEL'
            ).update(consumo_kwh_analitico='999.00'),
            'uc_consumo_faturamento_mensal',
            'volume com fatura deve ser igual ao consumo analítico (R2)',
        ),
        (
            'r3_group_temporal',
            'uc_consumo_faturamento_mensal',
            # UC100000 em 2025-01 é GD, mudar para DEMAIS
            lambda rows: next(
                r for r in rows if r['id_uc'] == 'UC100000' and r['competencia'] == '2025-01-01'
            ).update(grupo_uc='DEMAIS'),
            'uc_consumo_faturamento_mensal',
            'R3',
        ),
        (
            'r4_flag_gd',
            'dim_uc',
            # UC100000 está em gd_uc, setar flag_gd false
            lambda rows: rows[0].update(flag_gd='false'),
            'dim_uc',
            'R4',
        ),
        (
            'r4_queue_gd',
            'fila_inspecao',
            # Substituir id_uc por uma UC com GD (UC100000 está em gd_uc)
            lambda rows: rows[0].update(id_uc='UC100000'),
            'fila_inspecao',
            'R4',
        ),
        (
            'r4_denominador_continuidade',
            'continuidade_alimentador_mensal',
            lambda rows: rows[0].update(numero_ucs=str(int(rows[0]['numero_ucs']) + 1)),
            'continuidade_alimentador_mensal',
            'R4',
        ),
        (
            'r6_reference_date',
            None,
            None,
            'manifesto',
            'R6',
        ),
    ],
)
async def test_new_gates_reject_and_preserve_state(
    db, infrastructure, tmp_path, gate, table, mutate, expected_table, expected_rule
):
    origin = tmp_path / f'batch_{gate}'
    shutil.copytree(SAMPLES, origin)
    if gate == 'r6_reference_date':
        manifest_file = origin / 'manifest.json'
        manifest = json.loads(manifest_file.read_text())
        manifest['reference_date'] = '2026-05-31'
        manifest_file.write_text(json.dumps(manifest))
    elif table and mutate:
        rewrite(origin, table, mutate)
        # Sincroniza totais de controle no manifesto caso a mutação tenha alterado colunas somadas
        manifest_file = origin / 'manifest.json'
        manifest = json.loads(manifest_file.read_text())
        for col in manifest['tables'][table]['totals']:
            manifest['tables'][table]['totals'][col] = str(
                sum(Decimal(r[col]) for r in csv_rows(origin, table) if r.get(col))
            )
        manifest_file.write_text(json.dumps(manifest))

    before = await analytics_snapshot(db)
    with pytest.raises(ContractError) as exc:
        await load(origin, infrastructure['importer_url'])
    assert expected_table in str(exc.value)
    assert expected_rule in str(exc.value)
    assert await analytics_snapshot(db) == before
    assert await db.fetchval("SELECT to_regnamespace('analytics_staging')") is None


async def test_verify_mode_valid_sample(db, infrastructure, capsys):
    before = await analytics_snapshot(db)
    redis = Redis.from_url(infrastructure['settings'].redis_url)
    redis_before = await redis.get('versao_carga')
    try:
        result = await load(
            SAMPLES,
            infrastructure['importer_url'],
            infrastructure['settings'].redis_url,
            verify_only=True,
        )
        assert result is None
        assert await analytics_snapshot(db) == before
        assert await redis.get('versao_carga') == redis_before
        assert await db.fetchval("SELECT to_regnamespace('analytics_staging')") is None
        captured = capsys.readouterr()
        assert '0.3.0-provisional' in captured.out
        assert 'amostra-sintetica-v1' in captured.out
        assert '2026-07-01' in captured.out
        assert 'OK' in captured.out
    finally:
        await redis.aclose()


async def test_verify_mode_invalid_sample_returns_error(db, infrastructure, tmp_path, capsys):
    origin = tmp_path / 'batch_verify_invalid'
    shutil.copytree(SAMPLES, origin)
    rewrite(origin, 'dim_uc', lambda rows: rows[0].update(flag_gd='false'))
    before = await analytics_snapshot(db)
    redis = Redis.from_url(infrastructure['settings'].redis_url)
    redis_before = await redis.get('versao_carga')
    try:
        with pytest.raises(ContractError) as exc:
            await load(
                origin,
                infrastructure['importer_url'],
                infrastructure['settings'].redis_url,
                verify_only=True,
            )
        assert 'dim_uc' in str(exc.value)
        assert await analytics_snapshot(db) == before
        assert await redis.get('versao_carga') == redis_before
        assert await db.fetchval("SELECT to_regnamespace('analytics_staging')") is None
    finally:
        await redis.aclose()


def test_cli_verificar_success(infrastructure, monkeypatch, capsys):
    from importador import cli

    monkeypatch.setenv('DATABASE_URL_IMPORTADOR', infrastructure['importer_url'])
    monkeypatch.setenv('REDIS_URL', infrastructure['settings'].redis_url)
    monkeypatch.setattr('sys.argv', ['importador', '--origem', str(SAMPLES), '--verificar'])
    cli.main()
    captured = capsys.readouterr()
    assert '0.3.0-provisional' in captured.out
    assert 'OK' in captured.out


def test_cli_verificar_failure(infrastructure, tmp_path, monkeypatch, capsys):
    from importador import cli

    origin = tmp_path / 'batch_cli_invalid'
    shutil.copytree(SAMPLES, origin)
    rewrite(origin, 'dim_uc', lambda rows: rows[0].update(flag_gd='false'))
    monkeypatch.setenv('DATABASE_URL_IMPORTADOR', infrastructure['importer_url'])
    monkeypatch.setenv('REDIS_URL', infrastructure['settings'].redis_url)
    monkeypatch.setattr('sys.argv', ['importador', '--origem', str(origin), '--verificar'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert 'dim_uc' in captured.err
