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


async def continuidade(db, periodo, recorte):
    if recorte.bairro is not None or recorte.classe is not None:
        # O agregado não tem bairro/classe. Reagrega os numeradores Gold das UCs
        # selecionadas, sem atribuir a elas os eventos de todo o alimentador.
        sql = f"""
            WITH ucs AS (
                SELECT u.id_uc FROM analytics.dim_uc u WHERE true {recorte.condicoes('u')}
            ), cobertura AS (
                SELECT count(*) AS meses
                FROM analytics.continuidade_alimentador_mensal c
                WHERE c.competencia BETWEEN :inicio AND :fim
                  AND EXISTS (
                      SELECT 1 FROM analytics.dim_uc u
                      WHERE u.alimentador = c.alimentador {recorte.condicoes('u')}
                  )
            )
            SELECT CASE WHEN (SELECT meses FROM cobertura) > 0
                        THEN coalesce(sum(o.duracao_efetiva_min), 0) / 60 END AS chi,
                   CASE WHEN (SELECT meses FROM cobertura) > 0
                        THEN count(o.id_ocorrencia) FILTER (WHERE NOT o.flag_sobreposicao)
                        END AS interrupcoes,
                   (SELECT count(*) FROM ucs) AS numero_ucs
            FROM ucs u
            LEFT JOIN analytics.ocorrencias_uc o ON o.id_uc = u.id_uc
                AND o.data_abertura >= :inicio
                AND o.data_abertura < CAST(:fim AS date) + interval '1 month'
        """
    else:
        sql = f"""
            WITH por_alimentador AS (
                SELECT c.alimentador, sum(c.chi_horas) AS chi,
                       sum(c.interrupcoes) AS interrupcoes, max(c.numero_ucs) AS numero_ucs
                FROM analytics.continuidade_alimentador_mensal c
                JOIN analytics.dim_alimentador u USING (alimentador)
                WHERE c.competencia BETWEEN :inicio AND :fim {recorte.condicoes('u')}
                GROUP BY c.alimentador
            )
            SELECT sum(chi) AS chi, sum(interrupcoes) AS interrupcoes,
                   sum(numero_ucs) AS numero_ucs FROM por_alimentador
        """
    return (
        (
            await db.execute(
                text(sql), dict(inicio=periodo.inicio, fim=periodo.fim, **recorte.parametros())
            )
        )
        .mappings()
        .one()
    )
