from app.modules.continuidade import repository as continuidade
from app.modules.kpis import repository
from app.modules.kpis.schemas import Indicador, KPIs, Serie
from app.modules.metricas import contexto, razao
from app.modules.receita import repository as receita


def indicador(valor, comparacao):
    delta = valor - comparacao if valor is not None and comparacao is not None else None
    return Indicador(
        valor=valor,
        comparacao=comparacao,
        variacao=delta,
        variacao_pct=razao(delta, comparacao, 100),
    )


async def valores(db, periodo, recorte, sem_evento_atipico=False):
    r = await receita.totais(db, periodo, recorte)
    u = await repository.ucs(db, periodo, recorte)
    c = await continuidade.totais(db, periodo, recorte, sem_evento_atipico)
    i = await repository.inspecoes(db, periodo, recorte)
    return {
        'receita': r['receita'],
        'receita_arrecadada': r['receita_arrecadada'],
        'volume_faturado_kwh': r['volume_faturado_kwh'],
        'tarifa_media': razao(r['receita'], r['volume_faturado_kwh'], casas='0.000001'),
        'inadimplencia': razao(
            r['receita'] - r['receita_arrecadada'] if r['receita'] is not None else None,
            r['receita'],
            100,
        ),
        'ativas': u['ativas'] if u['ativas'] else None,
        'com_gd': u['com_gd'] if u['ativas'] else None,
        'dec': razao(c['chi'], c['numero_ucs']),
        'fec': razao(c['interrupcoes'], c['numero_ucs']),
        'taxa_acerto': razao(i['confirmadas'], i['total'], 100),
    }


async def kpis(db, periodo, comparacao, recorte, sem_evento_atipico=False):
    ctx = await contexto(db, periodo, comparacao)
    atual = await valores(db, ctx.atual, recorte, sem_evento_atipico)
    anterior = await valores(db, ctx.anterior, recorte, sem_evento_atipico) if ctx.anterior else {}
    indicadores = {key: indicador(value, anterior.get(key)) for key, value in atual.items()}
    ucs = {key: indicadores.pop(key) for key in ('ativas', 'com_gd')}
    continuidade = {key: indicadores.pop(key) for key in ('dec', 'fec')}
    return KPIs(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        **indicadores,
        ucs=ucs,
        continuidade=continuidade,
    )


async def serie(db, periodo, comparacao, recorte):
    ctx = await contexto(db, periodo, comparacao)
    return Serie(**ctx.metadados(), serie=await receita.serie(db, ctx.atual, recorte))
