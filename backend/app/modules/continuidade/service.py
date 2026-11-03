from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.modules.continuidade import repository
from app.modules.continuidade.schemas import Indicadores, Ranking, Serie
from app.modules.metricas import contexto


def indicadores(rows, sem_evento_atipico=False):
    observacoes = [r for r in rows if not (sem_evento_atipico and r['flag_evento_atipico'])]
    if not observacoes:
        return Indicadores(chi=None, interrupcoes=None, numero_ucs=None, dec=None, fec=None)
    chi = sum((r['chi'] for r in observacoes), Decimal(0))
    interrupcoes = sum(r['interrupcoes'] for r in observacoes)
    # O contrato garante numero_ucs fixo. Conta cada alimentador uma vez no
    # período, mesmo que tenha várias competências selecionadas ou expurgadas.
    ucs = sum({r['alimentador']: r['numero_ucs'] for r in rows}.values())

    def razao(numerador):
        return (Decimal(numerador) / ucs).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return Indicadores(
        chi=chi, interrupcoes=interrupcoes, numero_ucs=ucs, dec=razao(chi), fec=razao(interrupcoes)
    )


async def serie(db, periodo, comparacao, recorte, sem_evento_atipico):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.mensais(db, ctx.atual, recorte)
    por_mes = defaultdict(list)
    for row in rows:
        por_mes[row['competencia']].append(row)
    pontos = []
    mes = ctx.atual.inicio
    while mes <= ctx.atual.fim:
        pontos.append(
            dict(competencia=mes, **indicadores(por_mes[mes], sem_evento_atipico).model_dump())
        )
        if mes == ctx.atual.fim:
            break
        mes = (
            mes.replace(year=mes.year + 1, month=1)
            if mes.month == 12
            else mes.replace(month=mes.month + 1)
        )
    return Serie(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        totais=indicadores(rows, sem_evento_atipico),
        serie=pontos,
    )


async def ranking(db, periodo, comparacao, recorte, sem_evento_atipico, ordem):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.mensais(db, ctx.atual, recorte)
    por_alimentador = defaultdict(list)
    for row in rows:
        por_alimentador[row['alimentador']].append(row)
    causas = defaultdict(list)
    for row in await repository.causas(db, ctx.atual, recorte, sem_evento_atipico):
        causas[row['alimentador']].append(
            {k: row[k] for k in ('causa', 'ocorrencias', 'interrupcoes')}
        )
    itens = []
    for alimentador, mensais in por_alimentador.items():
        valores = indicadores(mensais, sem_evento_atipico)
        if valores.dec is None:
            continue
        itens.append(
            dict(
                alimentador=alimentador,
                municipio=mensais[0]['municipio'],
                **valores.model_dump(),
                causas=causas[alimentador],
            )
        )

    # Ordena pelo índice exato, antes do arredondamento da resposta; código
    # desempata para manter o resultado determinístico.
    def chave(item):
        valores = {
            'chi': item['chi'],
            'dec': item['chi'] / item['numero_ucs'],
            'fec': Decimal(item['interrupcoes']) / item['numero_ucs'],
        }
        return -valores[ordem], item['alimentador']

    itens.sort(key=chave)
    return Ranking(
        **ctx.metadados(), sem_evento_atipico=sem_evento_atipico, ordem=ordem, ranking=itens
    )
