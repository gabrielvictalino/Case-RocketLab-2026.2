from dataclasses import asdict

from app.core.decomposicao import decompor
from app.core.metricas import contexto
from app.modules.receita import repository
from app.modules.receita.schemas import Decomposicao


async def decomposicao(db, periodo, comparacao, recorte):
    ctx = await contexto(db, periodo, comparacao)
    atual = await repository.totais(db, ctx.atual, recorte)
    anterior = await repository.totais(db, ctx.anterior, recorte) if ctx.anterior else None
    efeitos = None
    variacao = None
    if anterior and atual['receita'] is not None and anterior['receita'] is not None:
        variacao = atual['receita'] - anterior['receita']
        efeitos = asdict(
            decompor(
                q0=anterior['volume_faturado_kwh'],
                r0=anterior['receita'],
                t0=anterior['componente_tarifa_reais'],
                b0=anterior['componente_bandeira_reais'],
                q1=atual['volume_faturado_kwh'],
                r1=atual['receita'],
                t1=atual['componente_tarifa_reais'],
                b1=atual['componente_bandeira_reais'],
            )
        )
    return Decomposicao(
        **ctx.metadados(), atual=atual, anterior=anterior, variacao=variacao, efeitos=efeitos
    )
