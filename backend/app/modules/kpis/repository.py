from sqlalchemy import text


async def ucs(db, periodo, recorte):
    return (
        (
            await db.execute(
                text(f"""
                    SELECT count(DISTINCT m.id_uc) AS ativas,
                           count(DISTINCT m.id_uc) FILTER (
                               WHERE gd.data_conexao < CAST(:fim AS date) + interval '1 month'
                           ) AS com_gd
                    FROM analytics.uc_consumo_faturamento_mensal m
                    JOIN analytics.dim_uc u USING (id_uc)
                    LEFT JOIN analytics.gd_uc gd USING (id_uc)
                    WHERE m.competencia BETWEEN :inicio AND :fim {recorte.condicoes('u')}
                """),
                dict(inicio=periodo.inicio, fim=periodo.fim, **recorte.parametros()),
            )
        )
        .mappings()
        .one()
    )


async def inspecoes(db, periodo, recorte):
    return (
        (
            await db.execute(
                text(f"""
                    SELECT count(*) AS total,
                           count(*) FILTER (
                               WHERE i.resultado = 'IRREGULARIDADE CONFIRMADA'
                           ) AS confirmadas
                    FROM portal_read.inspecoes i
                    LEFT JOIN analytics.dim_uc u USING (id_uc)
                    WHERE i.data >= :inicio
                      AND i.data < CAST(:fim AS date) + interval '1 month'
                      {recorte.condicoes('u')}
                """),
                dict(inicio=periodo.inicio, fim=periodo.fim, **recorte.parametros()),
            )
        )
        .mappings()
        .one()
    )
