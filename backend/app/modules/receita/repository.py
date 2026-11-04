"""Totais e série de receita usados pelos KPIs e disponíveis para a P20 (#55).

Sem alimentador, usa o agregado Gold; com alimentador, usa o detalhe reconciliado
com esse agregado pelo importador. Regras R2/R5: contracts/README.md.
"""

from sqlalchemy import text


def fonte(recorte):
    if recorte.alimentador is None:
        return (
            'analytics.receita_volume_mensal m',
            recorte.condicoes('m'),
            'm.receita',
            'm.receita_arrecadada',
            'm.componente_tarifa_reais',
            'm.componente_bandeira_reais',
        )
    return (
        'analytics.uc_consumo_faturamento_mensal m JOIN analytics.dim_uc u USING (id_uc)',
        recorte.condicoes('u'),
        'm.valor_total',
        'm.valor_arrecadado',
        'm.volume_faturado_kwh * coalesce(m.tarifa_base, 0)',
        'm.volume_faturado_kwh * coalesce(m.adicional_bandeira, 0)',
    )


async def totais(db, periodo, recorte):
    tabela, filtros, receita, arrecadada, tarifa, bandeira = fonte(recorte)
    return (
        (
            await db.execute(
                text(f"""
                    SELECT sum({receita}) AS receita,
                           sum({arrecadada}) AS receita_arrecadada,
                           sum(m.volume_faturado_kwh) AS volume_faturado_kwh,
                           round(sum({tarifa}), 2) AS componente_tarifa_reais,
                           round(sum({bandeira}), 2) AS componente_bandeira_reais
                    FROM {tabela}
                    WHERE m.competencia BETWEEN :inicio AND :fim {filtros}
                """),
                dict(inicio=periodo.inicio, fim=periodo.fim, **recorte.parametros()),
            )
        )
        .mappings()
        .one()
    )


async def serie(db, periodo, recorte):
    tabela, filtros, receita, _, _, _ = fonte(recorte)
    return (
        (
            await db.execute(
                text(f"""
                    WITH mensal AS (
                        SELECT m.competencia, sum({receita}) AS receita,
                               sum(m.volume_faturado_kwh) AS volume_faturado_kwh
                        FROM {tabela}
                        WHERE m.competencia BETWEEN :inicio AND :fim {filtros}
                        GROUP BY m.competencia
                    )
                    SELECT calendario.competencia::date AS competencia,
                           mensal.receita, mensal.volume_faturado_kwh
                    FROM generate_series(CAST(:inicio AS timestamp), CAST(:fim AS timestamp),
                                         interval '1 month') AS calendario(competencia)
                    LEFT JOIN mensal USING (competencia)
                    ORDER BY calendario.competencia
                """),
                dict(inicio=periodo.inicio, fim=periodo.fim, **recorte.parametros()),
            )
        )
        .mappings()
        .all()
    )


async def por_subgrao(db, atual, anterior, recorte):
    campos = {
        'q': 'volume_faturado_kwh',
        'r': 'receita',
        't': 'componente_tarifa_reais',
        'b': 'componente_bandeira_reais',
    }
    somas = ', '.join(
        f'coalesce(sum(m.{campo}) FILTER (WHERE m.competencia BETWEEN :i{n} AND :f{n}), 0) '
        f'AS {sigla}{n}'
        for n in (0, 1)
        for sigla, campo in campos.items()
    )
    query = text(f"""
        SELECT m.municipio, m.bairro, m.classe, m.grupo_uc, {somas}
        FROM analytics.receita_volume_mensal m
        WHERE (m.competencia BETWEEN :i0 AND :f0 OR m.competencia BETWEEN :i1 AND :f1)
              {recorte.condicoes('m')}
        GROUP BY m.municipio, m.bairro, m.classe, m.grupo_uc
        ORDER BY m.municipio, m.bairro, m.classe, m.grupo_uc
    """)
    params = dict(
        i0=anterior.inicio,
        f0=anterior.fim,
        i1=atual.inicio,
        f1=atual.fim,
        **recorte.parametros(),
    )
    return (await db.execute(query, params)).mappings().all()
