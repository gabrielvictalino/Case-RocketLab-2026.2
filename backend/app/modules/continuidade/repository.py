from sqlalchemy import text


def observacoes(recorte):
    """Numeradores e UCs por alimentador × competência, após a exclusão."""
    if recorte.bairro is not None or recorte.classe is not None:
        # O agregado não tem bairro/classe: seleciona as UCs e usa os
        # numeradores do detalhe somente nas competências com cobertura Gold.
        return f"""
            WITH ucs AS (
                SELECT u.id_uc, u.alimentador
                FROM analytics.dim_uc u WHERE true {recorte.condicoes('u')}
            ), cobertura AS (
                SELECT c.alimentador, c.competencia, count(*) AS numero_ucs
                FROM analytics.continuidade_alimentador_mensal c
                JOIN ucs USING (alimentador)
                WHERE c.competencia BETWEEN :inicio AND :fim
                  AND (NOT :sem_evento_atipico OR NOT c.flag_evento_atipico)
                GROUP BY c.alimentador, c.competencia
            ), ocorrencias AS (
                SELECT o.alimentador, date_trunc('month', o.data_abertura)::date AS competencia,
                       round(sum(o.duracao_efetiva_min) / 60, 2) AS chi,
                       count(*) FILTER (WHERE NOT o.flag_sobreposicao) AS interrupcoes
                FROM analytics.ocorrencias_uc o
                JOIN ucs USING (id_uc, alimentador)
                WHERE o.data_abertura >= :inicio
                  AND o.data_abertura < CAST(:fim AS date) + interval '1 month'
                GROUP BY o.alimentador, date_trunc('month', o.data_abertura)::date
            )
            SELECT c.alimentador, c.competencia, coalesce(o.chi, 0.00) AS chi,
                   coalesce(o.interrupcoes, 0) AS interrupcoes, c.numero_ucs
            FROM cobertura c LEFT JOIN ocorrencias o USING (alimentador, competencia)
        """
    return f"""
        SELECT c.alimentador, c.competencia, c.chi_horas AS chi,
               c.interrupcoes, c.numero_ucs
        FROM analytics.continuidade_alimentador_mensal c
        JOIN analytics.dim_alimentador u USING (alimentador)
        WHERE c.competencia BETWEEN :inicio AND :fim
          AND (NOT :sem_evento_atipico OR NOT c.flag_evento_atipico)
          {recorte.condicoes('u')}
    """


POR_ALIMENTADOR = """
    SELECT alimentador, sum(chi) AS chi, sum(interrupcoes) AS interrupcoes,
           max(numero_ucs) AS numero_ucs
    FROM observacoes GROUP BY alimentador
"""


def por_alimentador(recorte):
    return f'WITH observacoes AS ({observacoes(recorte)}) {POR_ALIMENTADOR}'


def parametros(periodo, recorte, sem_evento_atipico):
    return dict(
        inicio=periodo.inicio,
        fim=periodo.fim,
        sem_evento_atipico=sem_evento_atipico,
        **recorte.parametros(),
    )


async def totais(db, periodo, recorte, sem_evento_atipico=False):
    return (
        (
            await db.execute(
                text(f"""
                    WITH por_alimentador AS ({por_alimentador(recorte)})
                    SELECT sum(chi) AS chi, sum(interrupcoes) AS interrupcoes,
                           sum(numero_ucs) AS numero_ucs FROM por_alimentador
                """),
                parametros(periodo, recorte, sem_evento_atipico),
            )
        )
        .mappings()
        .one()
    )


async def serie(db, periodo, recorte, sem_evento_atipico):
    return (
        (
            await db.execute(
                text(f"""
                    WITH observacoes AS MATERIALIZED ({observacoes(recorte)}), mensal AS (
                        SELECT competencia, sum(chi) AS chi, sum(interrupcoes) AS interrupcoes,
                               sum(numero_ucs) AS numero_ucs
                        FROM observacoes GROUP BY competencia
                    ), por_alimentador AS ({POR_ALIMENTADOR}), totais AS (
                        SELECT sum(chi) AS total_chi, sum(interrupcoes) AS total_interrupcoes,
                               sum(numero_ucs) AS total_numero_ucs FROM por_alimentador
                    )
                    SELECT calendario.competencia::date AS competencia,
                           mensal.chi, mensal.interrupcoes, mensal.numero_ucs, totais.*
                    FROM generate_series(CAST(:inicio AS timestamp), CAST(:fim AS timestamp),
                                         interval '1 month') AS calendario(competencia)
                    LEFT JOIN mensal USING (competencia)
                    CROSS JOIN totais
                    ORDER BY calendario.competencia
                """),
                parametros(periodo, recorte, sem_evento_atipico),
            )
        )
        .mappings()
        .all()
    )


async def ranking(db, periodo, recorte, sem_evento_atipico):
    return (
        (
            await db.execute(
                text(f"""
                    WITH por_alimentador AS ({por_alimentador(recorte)})
                    SELECT p.*, a.municipio
                    FROM por_alimentador p
                    JOIN analytics.dim_alimentador a USING (alimentador)
                """),
                parametros(periodo, recorte, sem_evento_atipico),
            )
        )
        .mappings()
        .all()
    )


async def causas(db, periodo, recorte, sem_evento_atipico):
    # Agrupa o detalhe por mês antes do join por igualdade com a cobertura Gold.
    return (
        (
            await db.execute(
                text(f"""
                    WITH por_mes AS (
                        SELECT o.alimentador, o.causa,
                               date_trunc('month', o.data_abertura)::date AS competencia,
                               count(*) AS ocorrencias,
                               count(*) FILTER (WHERE NOT o.flag_sobreposicao) AS interrupcoes
                        FROM analytics.ocorrencias_uc o
                        JOIN analytics.dim_uc u USING (id_uc)
                        WHERE o.data_abertura >= :inicio
                          AND o.data_abertura < CAST(:fim AS date) + interval '1 month'
                          {recorte.condicoes('u')}
                        GROUP BY o.alimentador, o.causa,
                                 date_trunc('month', o.data_abertura)::date
                    )
                    SELECT o.alimentador, o.causa, sum(o.ocorrencias) AS ocorrencias,
                           sum(o.interrupcoes) AS interrupcoes
                    FROM por_mes o
                    JOIN analytics.continuidade_alimentador_mensal c
                      USING (alimentador, competencia)
                    WHERE NOT :sem_evento_atipico OR NOT c.flag_evento_atipico
                    GROUP BY o.alimentador, o.causa
                    ORDER BY o.alimentador, ocorrencias DESC, o.causa
                """),
                parametros(periodo, recorte, sem_evento_atipico),
            )
        )
        .mappings()
        .all()
    )
