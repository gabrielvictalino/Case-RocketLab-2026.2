import asyncio
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
# Lock de transação da troca de `analytics`: exclusivo aqui, compartilhado nas leituras do
# portal (`app.core.database.SWAP_LOCK`). O PUBLICATION_LOCK serializa só importadores e
# dura a carga inteira; este dura só a troca, para não segurar as telas durante o COPY.
SWAP_LOCK = 7820361
# Enquanto o importador espera o SWAP_LOCK, as leituras novas do portal esperam atrás dele.
# Por isso ele espera pouco de cada vez (`lock_timeout`) e abre a fila entre as tentativas,
# em vez de prendê-la até uma leitura longa terminar. O mesmo prazo vale para os locks da
# troca, que segura o portal: a soma das duas esperas fica abaixo da
# `app.core.database.ESPERA_DA_PUBLICACAO_MS`. Esgotadas as tentativas, a carga é recusada
# e a anterior fica preservada.
ESPERA_DA_TROCA_MS = 1500
TENTATIVAS_DA_TROCA = 8
PAUSA_ENTRE_TENTATIVAS_S = 0.5


class TrocaOcupada(Exception):
    """Leituras do portal seguraram a troca de `analytics` além das tentativas."""


async def _pegar_lock_da_troca(db):
    for tentativa in range(TENTATIVAS_DA_TROCA):
        if tentativa:
            await asyncio.sleep(PAUSA_ENTRE_TENTATIVAS_S)
        try:
            # O savepoint isola a espera expirada; o lock pego nele fica com a transação.
            async with db.transaction():
                await db.execute('SELECT pg_advisory_xact_lock($1)', SWAP_LOCK)
            return
        except asyncpg.LockNotAvailableError:
            logger.info('Leituras em curso; nova tentativa da troca (%d)', tentativa + 1)
    raise TrocaOcupada(f'leituras do portal ocuparam a troca em {TENTATIVAS_DA_TROCA} tentativas')


class _Verificado(Exception):
    """Sinaliza conclusão com sucesso do modo verify_only para rollback automático."""


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

    # Gate R2: Nulidade consistente quando id_fatura é nulo
    invalid_null_invoice = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.uc_consumo_faturamento_mensal
        WHERE (id_fatura IS NULL AND NOT (
          bandeira IS NULL AND status_pagamento IS NULL AND data_vencimento IS NULL
          AND tarifa_base IS NULL AND adicional_bandeira IS NULL
          AND volume_faturado_kwh = 0 AND valor_total = 0 AND valor_arrecadado = 0
        )) OR (id_fatura IS NOT NULL AND (
          bandeira IS NULL OR status_pagamento IS NULL OR data_vencimento IS NULL
          OR tarifa_base IS NULL OR adicional_bandeira IS NULL
        )))""")
    if invalid_null_invoice:
        raise ContractError(
            'uc_consumo_faturamento_mensal: inconsistência em competência sem fatura (R2)'
        )

    # Gate R2: Arrecadação compatível com status de pagamento
    invalid_payment_status = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.uc_consumo_faturamento_mensal
        WHERE (status_pagamento = 'PAGA' AND valor_arrecadado <> valor_total)
           OR (status_pagamento = 'ABERTA' AND valor_arrecadado <> 0))""")
    if invalid_payment_status:
        raise ContractError(
            'uc_consumo_faturamento_mensal: valor arrecadado incompatível com status_pagamento (R2)'
        )

    # Gate R2: Troca de medidor exige consumo estimado (o enum do contrato fecha os métodos)
    invalid_meter_exchange = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.uc_consumo_faturamento_mensal
        WHERE flag_troca_medidor = true AND metodo_consumo = 'LEITURA_UTILIZAVEL')""")
    if invalid_meter_exchange:
        raise ContractError(
            'uc_consumo_faturamento_mensal: '
            'flag_troca_medidor exige metodo_consumo diferente de LEITURA_UTILIZAVEL (R2)'
        )

    # Gate R2: LEITURA_UTILIZAVEL significa consumo analítico igual ao original
    invalid_reading = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.uc_consumo_faturamento_mensal
        WHERE metodo_consumo = 'LEITURA_UTILIZAVEL'
          AND consumo_kwh_analitico <> consumo_kwh_original)""")
    if invalid_reading:
        raise ContractError(
            'uc_consumo_faturamento_mensal: '
            'metodo_consumo LEITURA_UTILIZAVEL exige consumo analítico igual ao original (R2)'
        )

    invalid_volume = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.uc_consumo_faturamento_mensal
        WHERE id_fatura IS NOT NULL AND volume_faturado_kwh <> consumo_kwh_analitico)""")
    if invalid_volume:
        raise ContractError(
            'uc_consumo_faturamento_mensal: '
            'volume com fatura deve ser igual ao consumo analítico (R2)'
        )

    # Gate R3: Grupo de UC temporal segundo prioridade GD > IRREGULARIDADE > DEMAIS
    invalid_group = await db.fetchval("""SELECT EXISTS(
        WITH primeira_irregularidade AS (
          SELECT id_uc, date_trunc('month', min(data))::date AS mes_irregularidade
          FROM analytics_staging.inspecoes_historicas
          WHERE resultado = 'IRREGULARIDADE CONFIRMADA'
          GROUP BY id_uc
        ),
        esperado AS (
          SELECT
            m.id_uc,
            m.competencia,
            CASE
              WHEN g.id_uc IS NOT NULL
                AND m.competencia >= date_trunc('month', g.data_conexao)::date
                THEN 'GD'
              WHEN i.id_uc IS NOT NULL AND m.competencia >= i.mes_irregularidade
                THEN 'IRREGULARIDADE_CONFIRMADA'
              ELSE 'DEMAIS'
            END AS grupo_esperado,
            m.grupo_uc
          FROM analytics_staging.uc_consumo_faturamento_mensal m
          LEFT JOIN analytics_staging.gd_uc g ON m.id_uc = g.id_uc
          LEFT JOIN primeira_irregularidade i ON m.id_uc = i.id_uc
        )
        SELECT 1 FROM esperado WHERE grupo_esperado <> grupo_uc LIMIT 1)""")
    if invalid_group:
        raise ContractError(
            'uc_consumo_faturamento_mensal: grupo_uc diverge da regra temporal (R3)'
        )

    # Gate R4: dim_uc.flag_gd equivale à presença em gd_uc
    invalid_flag_gd = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.dim_uc u
        FULL OUTER JOIN analytics_staging.gd_uc g ON u.id_uc = g.id_uc
        WHERE (u.flag_gd = true AND g.id_uc IS NULL)
           OR (u.flag_gd = false AND g.id_uc IS NOT NULL)
           OR u.id_uc IS NULL)""")
    if invalid_flag_gd:
        raise ContractError('dim_uc: flag_gd diverge de gd_uc (R4)')

    # Gate R4: fila_inspecao não pode conter UC com GD
    invalid_queue_gd = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.fila_inspecao f
        JOIN analytics_staging.gd_uc g ON f.id_uc = g.id_uc)""")
    if invalid_queue_gd:
        raise ContractError('fila_inspecao: contém UC presente em gd_uc (R4)')

    # Gate R4: denominador do DEC/FEC fixo, igual ao cadastro do alimentador
    invalid_denominator = await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM analytics_staging.continuidade_alimentador_mensal c
        JOIN analytics_staging.dim_alimentador a USING (alimentador)
        WHERE c.numero_ucs <> a.numero_ucs)""")
    if invalid_denominator:
        raise ContractError(
            'continuidade_alimentador_mensal: numero_ucs diverge de dim_alimentador (R4)'
        )

    # Reconciliar por grão, não só os totais: evita compensação entre grupos.
    divergent = await db.fetchval("""
        WITH detalhe AS (
          SELECT m.competencia,u.municipio,u.bairro,u.classe,m.grupo_uc,
            sum(m.volume_faturado_kwh) volume_faturado_kwh,
            sum(m.valor_total) receita, sum(m.valor_arrecadado) receita_arrecadada,
            round(sum(m.volume_faturado_kwh*coalesce(m.tarifa_base,0)),2)
              componente_tarifa_reais,
            round(sum(m.volume_faturado_kwh*coalesce(m.adicional_bandeira,0)),2)
              componente_bandeira_reais
          FROM analytics_staging.uc_consumo_faturamento_mensal m
          JOIN analytics_staging.dim_uc u USING(id_uc) GROUP BY 1,2,3,4,5
        ), agregado AS (SELECT * FROM analytics_staging.receita_volume_mensal)
        SELECT EXISTS((SELECT * FROM detalhe EXCEPT SELECT * FROM agregado)
          UNION ALL (SELECT * FROM agregado EXCEPT SELECT * FROM detalhe))
    """)
    if divergent:
        raise ContractError('Receita e volume não reconciliam por grão')


async def load(origin, database_url, redis_url=None, *, verify_only=False):
    origin = Path(origin)
    manifest = manifest_for(origin)
    specs = specifications()
    load_id = uuid4()
    db = await asyncpg.connect(database_url, timeout=10)
    try:
        # Lock de sessão cobre também o commit e a atualização externa do Redis.
        # Fechar a conexão libera o lock inclusive em erro/cancelamento.
        await db.execute('SELECT pg_advisory_lock($1)', PUBLICATION_LOCK)
        try:
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
                            await db.execute(
                                f'CREATE INDEX ON analytics_staging."{name}" ("{column}")'
                            )
                if verify_only:
                    raise _Verificado()

                # Espera as leituras em curso terminarem; as novas aguardam o commit e já
                # leem a carga nova, com os números e a identificação da mesma publicação.
                await db.execute(f"SET LOCAL lock_timeout = '{ESPERA_DA_TROCA_MS}ms'")
                await _pegar_lock_da_troca(db)
                await db.execute('ALTER SCHEMA analytics RENAME TO analytics_anterior')
                await db.execute('ALTER SCHEMA analytics_staging RENAME TO analytics')
                await db.execute('GRANT USAGE ON SCHEMA analytics TO portal')
                for name in specs:
                    await db.execute(f'GRANT SELECT ON analytics."{name}" TO portal')
                # Views pertencem ao importador; não há dependência reversa de migração.
                await db.execute(VIEWS.read_text(encoding='utf-8'))
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
        except _Verificado:
            print(f'Versão do contrato: {manifest["contract_version"]}')
            print(f'Batch ID: {manifest["batch_id"]}')
            print(f'Período: {manifest["period"]["start"]}..{manifest["period"]["end"]}')
            print(f'Data de referência: {manifest["reference_date"]}')
            for name, entry in manifest['tables'].items():
                print(f'  {name}: {entry["rows"]} linhas')
            print('OK')
            return None
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
