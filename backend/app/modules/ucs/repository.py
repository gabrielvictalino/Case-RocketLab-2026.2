from collections import defaultdict

from sqlalchemy import text


async def buscar_dim_uc(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT id_uc, titular, documento_mascarado, classe, '
                    'endereco, municipio, bairro, alimentador '
                    'FROM analytics.dim_uc WHERE id_uc = :uc'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .first()
    )


async def buscar_info_carga(db):
    row = (
        (
            await db.execute(
                text(
                    "SELECT (manifesto->>'reference_date')::date AS reference_date, "
                    'periodo_fim '
                    'FROM operations.cargas ORDER BY ordem_publicacao DESC LIMIT 1'
                )
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None, None
    return row['reference_date'], row['periodo_fim']


async def buscar_medidor_atual(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT id_medidor, tipo_medidor, data_instalacao '
                    'FROM analytics.medidores_historico '
                    'WHERE id_uc = :uc AND data_retirada IS NULL '
                    'ORDER BY data_instalacao DESC LIMIT 1'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .first()
    )


async def buscar_gd(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT potencia_kw, data_conexao '
                    'FROM analytics.gd_uc WHERE id_uc = :uc LIMIT 1'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .first()
    )


async def buscar_maior_competencia(db, id_uc: str):
    return await db.scalar(
        text(
            'SELECT max(competencia) FROM analytics.uc_consumo_faturamento_mensal WHERE id_uc = :uc'
        ),
        {'uc': id_uc},
    )


async def listar_consumo_faturamento(db, id_uc: str, inicio, fim):
    return (
        (
            await db.execute(
                text(
                    'SELECT competencia, consumo_kwh_analitico, metodo_consumo, '
                    'tipo_leitura, flag_troca_medidor '
                    'FROM analytics.uc_consumo_faturamento_mensal '
                    'WHERE id_uc = :uc AND competencia BETWEEN :inicio AND :fim '
                    'ORDER BY competencia'
                ),
                {'uc': id_uc, 'inicio': inicio, 'fim': fim},
            )
        )
        .mappings()
        .all()
    )


async def buscar_ultima_fatura(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT competencia, id_fatura, volume_faturado_kwh, valor_total, '
                    'tarifa_base, adicional_bandeira, bandeira, tipo_leitura, '
                    'flag_troca_medidor, metodo_consumo '
                    'FROM analytics.uc_consumo_faturamento_mensal '
                    "WHERE id_uc = :uc AND id_fatura IS NOT NULL AND id_fatura <> '' "
                    'ORDER BY competencia DESC LIMIT 1'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .first()
    )


async def buscar_fatura_competencia(db, id_uc: str, competencia):
    return (
        (
            await db.execute(
                text(
                    'SELECT competencia, id_fatura, volume_faturado_kwh, valor_total, '
                    'tarifa_base, adicional_bandeira, bandeira, tipo_leitura, '
                    'flag_troca_medidor, metodo_consumo '
                    'FROM analytics.uc_consumo_faturamento_mensal '
                    'WHERE id_uc = :uc AND competencia = :comp '
                    "AND id_fatura IS NOT NULL AND id_fatura <> '' "
                    'LIMIT 1'
                ),
                {'uc': id_uc, 'comp': competencia},
            )
        )
        .mappings()
        .first()
    )


async def listar_faturas_abertas(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT id_fatura, competencia, valor_total, data_vencimento, bandeira '
                    'FROM analytics.uc_consumo_faturamento_mensal '
                    "WHERE id_uc = :uc AND status_pagamento = 'ABERTA' "
                    'ORDER BY competencia DESC'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .all()
    )


async def listar_ocorrencias_uc(db, id_uc: str, inicio, fim_plus_1m):
    return (
        (
            await db.execute(
                text(
                    'SELECT id_ocorrencia, data_abertura, data_encerramento, duracao_min, causa '
                    'FROM analytics.ocorrencias_uc '
                    'WHERE id_uc = :uc AND data_abertura >= :inicio '
                    'AND data_abertura < :fim_plus_1m '
                    'ORDER BY data_abertura DESC'
                ),
                {'uc': id_uc, 'inicio': inicio, 'fim_plus_1m': fim_plus_1m},
            )
        )
        .mappings()
        .all()
    )


async def resumo_alimentador(db, alimentador: str, inicio, fim):
    return (
        (
            await db.execute(
                text(
                    'SELECT COALESCE(SUM(interrupcoes), 0) AS soma_interrupcoes, '
                    'COALESCE(SUM(chi_horas), 0) AS soma_chi, '
                    'MAX(numero_ucs) AS numero_ucs '
                    'FROM analytics.continuidade_alimentador_mensal '
                    'WHERE alimentador = :alm AND competencia BETWEEN :inicio AND :fim'
                ),
                {'alm': alimentador, 'inicio': inicio, 'fim': fim},
            )
        )
        .mappings()
        .first()
    )


async def listar_chamados(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT protocolo, aberto_em, assunto, status, nota '
                    'FROM analytics.atendimentos '
                    'WHERE id_uc = :uc ORDER BY aberto_em DESC'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .all()
    )


async def listar_historico_chamados(db, protocolos: list[str]):
    if not protocolos:
        return defaultdict(list)
    rows = (
        (
            await db.execute(
                text(
                    'SELECT protocolo, sequencia, data, descricao '
                    'FROM analytics.atendimentos_historico '
                    'WHERE protocolo = ANY(:protos) '
                    'ORDER BY sequencia'
                ),
                {'protos': protocolos},
            )
        )
        .mappings()
        .all()
    )
    resultado = defaultdict(list)
    for row in rows:
        resultado[row['protocolo']].append(dict(row))
    return resultado


async def listar_inspecoes(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT id_inspecao, data, inspetor, resultado, tipo_irregularidade, '
                    'kwh_recuperado, origem '
                    'FROM portal_read.inspecoes '
                    'WHERE id_uc = :uc ORDER BY data DESC'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .all()
    )


async def buscar_ordem_ativa(db, id_uc: str):
    return (
        (
            await db.execute(
                text(
                    'SELECT * FROM operations.ordens_inspecao '
                    "WHERE id_uc = :uc AND status IN ('ABERTA', 'EM_CAMPO') "
                    'LIMIT 1'
                ),
                {'uc': id_uc},
            )
        )
        .mappings()
        .first()
    )
