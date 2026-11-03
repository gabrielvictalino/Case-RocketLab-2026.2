from sqlalchemy import text


async def mensais(db, periodo, recorte, sem_evento_atipico):
    # A exclusão é por alimentador × competência, antes de qualquer agregação.
    return (
        (
            await db.execute(
                text("""
                    SELECT c.alimentador, a.municipio, c.competencia,
                           c.chi_horas AS chi, c.interrupcoes, c.numero_ucs
                    FROM analytics.continuidade_alimentador_mensal c
                    JOIN analytics.dim_alimentador a USING (alimentador)
                    WHERE c.competencia BETWEEN :inicio AND :fim
                      AND (NOT :sem_evento_atipico OR NOT c.flag_evento_atipico)
                      AND (CAST(:municipio AS text) IS NULL OR a.municipio = :municipio)
                      AND (CAST(:alimentador AS text) IS NULL OR c.alimentador = :alimentador)
                    ORDER BY c.competencia, c.alimentador
                """),
                dict(
                    inicio=periodo.inicio,
                    fim=periodo.fim,
                    sem_evento_atipico=sem_evento_atipico,
                    **recorte.model_dump(),
                ),
            )
        )
        .mappings()
        .all()
    )


async def causas(db, periodo, recorte, sem_evento_atipico):
    # A causa mensal é só a principal. As contagens vêm do detalhe, incluindo
    # todas as causas, com a mesma cobertura e exclusão usadas nos indicadores.
    return (
        (
            await db.execute(
                text("""
                    SELECT o.alimentador, o.causa, count(*) AS ocorrencias,
                           count(*) FILTER (WHERE NOT o.flag_sobreposicao) AS interrupcoes
                    FROM analytics.ocorrencias_uc o
                    JOIN analytics.continuidade_alimentador_mensal c
                      ON c.alimentador = o.alimentador
                     AND o.data_abertura >= c.competencia
                     AND o.data_abertura < c.competencia + interval '1 month'
                    JOIN analytics.dim_alimentador a ON a.alimentador = c.alimentador
                    WHERE c.competencia BETWEEN :inicio AND :fim
                      AND (NOT :sem_evento_atipico OR NOT c.flag_evento_atipico)
                      AND (CAST(:municipio AS text) IS NULL OR a.municipio = :municipio)
                      AND (CAST(:alimentador AS text) IS NULL OR c.alimentador = :alimentador)
                    GROUP BY o.alimentador, o.causa
                    ORDER BY o.alimentador, ocorrencias DESC, o.causa
                """),
                dict(
                    inicio=periodo.inicio,
                    fim=periodo.fim,
                    sem_evento_atipico=sem_evento_atipico,
                    **recorte.model_dump(),
                ),
            )
        )
        .mappings()
        .all()
    )
