import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
from redis.asyncio import Redis

from importador.contracts import ContractError, file_hash, manifest_for, records, specifications

logger = logging.getLogger(__name__)
VIEWS = Path(__file__).resolve().parents[2] / 'views.sql'
PUBLICATION_LOCK = 7820360


def table_ddl(name, spec):
    fields = [
        f'"{column}" {col["type"]}' + ('' if col['nullable'] else ' NOT NULL')
        for column, col in spec['columns'].items()
    ]
    return f'CREATE TABLE analytics_staging."{name}" ({", ".join(fields)})'


async def primary_key(db, name, spec):
    # Validar antes do índice fornece a chave problemática, sem vazar a linha inteira.
    key = ','.join(f'"{k}"' for k in spec['primary_key'])
    duplicate = await db.fetchrow(
        f'SELECT {key} FROM analytics_staging."{name}" GROUP BY {key} HAVING count(*) > 1 LIMIT 1'
    )
    if duplicate:
        raise ContractError(f'{name}: chave duplicada {dict(duplicate)}')
    await db.execute(f'ALTER TABLE analytics_staging."{name}" ADD PRIMARY KEY ({key})')


async def validate(db, specs, manifest):
    for name, spec in specs.items():
        table = f'analytics_staging."{name}"'
        count = await db.fetchval(f'SELECT count(*) FROM {table}')
        entry = manifest['tables'][name]
        if count != entry['rows']:
            raise ContractError(f'{name}: contagem diverge do manifesto')
        if set(entry['totals']) != set(spec.get('control_totals', [])):
            raise ContractError(f'{name}: totais de controle ausentes ou desconhecidos')
        for column, expected in entry['totals'].items():
            total = await db.fetchval(f'SELECT coalesce(sum("{column}"),0) FROM {table}')
            if total != Decimal(expected):
                raise ContractError(f'{name}.{column}: total de controle divergente')
        for column, col in spec['columns'].items():
            if 'references' in col:
                target, key = col['references']
                orphan = await db.fetchrow(
                    f'SELECT s."{column}" FROM {table} s '
                    f'LEFT JOIN analytics_staging."{target}" t '
                    f'ON s."{column}"=t."{key}" '
                    f'WHERE s."{column}" IS NOT NULL AND t."{key}" IS NULL LIMIT 1'
                )
                if orphan:
                    raise ContractError(
                        f'{name}.{column}: referência inexistente {orphan[column]!r} '
                        f'em {target}.{key}'
                    )
                await db.execute(
                    f'ALTER TABLE {table} ADD FOREIGN KEY ("{column}") '
                    f'REFERENCES analytics_staging."{target}" ("{key}")'
                )
        if 'competencia' in spec['columns']:
            bounds = await db.fetchrow(
                f'SELECT min(competencia) lo, max(competencia) hi FROM {table}'
            )
            lo = date.fromisoformat(manifest['period']['start'] + '-01')
            hi = date.fromisoformat(manifest['period']['end'] + '-01')
            if bounds['lo'] is not None and (bounds['lo'] < lo or bounds['hi'] > hi):
                raise ContractError(f'{name}: competência fora do manifesto')
    bounds = await db.fetchrow(
        'SELECT min(competencia) lo,max(competencia) hi '
        'FROM analytics_staging.uc_consumo_faturamento_mensal'
    )
    if bounds['lo'] != date.fromisoformat(manifest['period']['start'] + '-01') or bounds[
        'hi'
    ] != date.fromisoformat(manifest['period']['end'] + '-01'):
        raise ContractError('Cobertura mensal diverge do manifesto')
    # Reconciliar por grão, não só os totais: evita compensação entre grupos.
    divergent = await db.fetchval("""
        WITH detalhe AS (
          SELECT m.competencia,u.municipio,u.bairro,u.classe,m.grupo_uc,
            sum(m.volume_faturado_kwh) volume_faturado_kwh,
            sum(m.valor_total) receita, sum(m.valor_arrecadado) receita_arrecadada,
            round(sum(m.volume_faturado_kwh*m.tarifa_base),2) componente_tarifa_reais,
            round(sum(m.volume_faturado_kwh*m.adicional_bandeira),2) componente_bandeira_reais
          FROM analytics_staging.uc_consumo_faturamento_mensal m
          JOIN analytics_staging.dim_uc u USING(id_uc) GROUP BY 1,2,3,4,5
        ), agregado AS (SELECT * FROM analytics_staging.receita_volume_mensal)
        SELECT EXISTS((SELECT * FROM detalhe EXCEPT SELECT * FROM agregado)
          UNION ALL (SELECT * FROM agregado EXCEPT SELECT * FROM detalhe))
    """)
    if divergent:
        raise ContractError('Receita e volume não reconciliam por grão')
    invalid_inspection = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.inspecoes_historicas WHERE NOT (
          (resultado='IRREGULARIDADE CONFIRMADA' AND tipo_irregularidade IS NOT NULL
            AND kwh_recuperado > 0) OR
          (resultado='SEM IRREGULARIDADE' AND tipo_irregularidade IS NULL
            AND kwh_recuperado=0)))""")
    if invalid_inspection:
        raise ContractError('Inspeção histórica incoerente')
    invalid_dates = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.medidores_historico
        WHERE data_retirada < data_instalacao) OR EXISTS(
        SELECT 1 FROM analytics_staging.ocorrencias_uc
        WHERE data_encerramento < data_abertura OR duracao_efetiva_min > duracao_min
          OR round(extract(epoch FROM data_encerramento-data_abertura)/60,2)
             <> duracao_min)""")
    if invalid_dates:
        raise ContractError('Datas ou durações incoerentes')


async def load(origin, database_url, redis_url=None):
    origin = Path(origin)
    manifest = manifest_for(origin)
    specs = specifications()
    load_id = uuid4()
    db = await asyncpg.connect(database_url, timeout=10)
    try:
        # Lock de sessão cobre também o commit e a atualização externa do Redis.
        # Fechar a conexão libera o lock inclusive em erro/cancelamento.
        await db.execute('SELECT pg_advisory_lock($1)', PUBLICATION_LOCK)
        async with db.transaction():
            await db.execute("SET LOCAL lock_timeout = '15s'")
            await db.execute('CREATE SCHEMA analytics_staging AUTHORIZATION importador')
            # Default privileges pertencem ao OID do schema e precisam acompanhar a troca.
            await db.execute("""ALTER DEFAULT PRIVILEGES IN SCHEMA analytics_staging
                GRANT SELECT ON TABLES TO portal""")
            for name, spec in specs.items():
                file = origin / f'{name}.csv'
                if file_hash(file) != manifest['tables'][name]['sha256']:
                    raise ContractError(f'{name}: SHA-256 divergente')
                await db.execute(table_ddl(name, spec))
                await db.copy_records_to_table(
                    name,
                    schema_name='analytics_staging',
                    columns=list(spec['columns']),
                    records=records(file, spec),
                )
                await primary_key(db, name, spec)
            await validate(db, specs, manifest)
            # Índices por UC e competência complementam as PKs do contrato.
            for name, spec in specs.items():
                for column in ('id_uc', 'competencia'):
                    if column in spec['columns'] and spec['primary_key'][0] != column:
                        await db.execute(f'CREATE INDEX ON analytics_staging."{name}" ("{column}")')
            await db.execute('ALTER SCHEMA analytics RENAME TO analytics_anterior')
            await db.execute('ALTER SCHEMA analytics_staging RENAME TO analytics')
            await db.execute('GRANT USAGE ON SCHEMA analytics TO portal')
            for name in specs:
                await db.execute(f'GRANT SELECT ON analytics."{name}" TO portal')
            # Views pertencem ao importador; não há dependência reversa de migração.
            await db.execute(VIEWS.read_text())
            # Remove FKs internas antes das tabelas, sem CASCADE.
            constraints = await db.fetch("""SELECT c.conname, t.relname FROM pg_constraint c
                JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
                WHERE n.nspname='analytics_anterior' AND c.contype='f' """)
            for row in constraints:
                # Identificadores vêm do catálogo do banco, com escaping SQL.
                table = row['relname'].replace('"', '""')
                constraint = row['conname'].replace('"', '""')
                await db.execute(
                    f'ALTER TABLE analytics_anterior."{table}" DROP CONSTRAINT "{constraint}"'
                )
            old_tables = await db.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='analytics_anterior'"
            )
            for row in old_tables:
                table = row['tablename'].replace('"', '""')
                await db.execute(f'DROP TABLE analytics_anterior."{table}"')
            await db.execute('DROP SCHEMA analytics_anterior')
            await db.execute(
                """INSERT INTO operations.cargas
                (id,batch_id,versao_contrato,sintetica,periodo_inicio,periodo_fim,manifesto,
                 carregado_em)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,clock_timestamp())""",
                load_id,
                manifest['batch_id'],
                manifest['contract_version'],
                manifest['synthetic'],
                date.fromisoformat(manifest['period']['start'] + '-01'),
                date.fromisoformat(manifest['period']['end'] + '-01'),
                json.dumps(manifest),
            )
        # PostgreSQL é a fonte de verdade. Falha no Redis não desfaz carga confirmada.
        if redis_url:
            await publish_redis(redis_url, load_id)
    finally:
        await db.close()
    return load_id


async def publish_redis(redis_url, load_id):
    client = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.set('versao_carga', str(load_id))
    except Exception:
        logger.warning('Carga %s publicada; não foi possível atualizar a versão no Redis', load_id)
    finally:
        await client.aclose()
