from dataclasses import dataclass, fields
from decimal import Decimal

from app.core.decomposicao import decompor
from app.core.errors import APIError
from app.modules.kpis.service import razao
from app.modules.metricas import contexto
from app.modules.receita import repository
from app.modules.receita.schemas import Decomposicao, Efeitos, Grupo, Grupos, Local, Locais

ZERO = Decimal('0.00')
GRUPOS = ('GD', 'IRREGULARIDADE_CONFIRMADA', 'DEMAIS')


@dataclass
class Totais:
    receita_base: Decimal = ZERO
    receita_atual: Decimal = ZERO
    volume_base_kwh: Decimal = ZERO
    volume_atual_kwh: Decimal = ZERO
    volume: Decimal = ZERO
    reajuste: Decimal = ZERO
    bandeira: Decimal = ZERO
    mix: Decimal = ZERO

    def adicionar(self, outro):
        for campo in fields(self):
            setattr(self, campo.name, getattr(self, campo.name) + getattr(outro, campo.name))

    def variacao(self):
        delta = self.receita_atual - self.receita_base
        delta_volume = self.volume_atual_kwh - self.volume_base_kwh
        return dict(
            receita_base=self.receita_base,
            receita_atual=self.receita_atual,
            variacao=delta,
            variacao_pct=razao(delta, self.receita_base, 100),
            volume_base_kwh=self.volume_base_kwh,
            volume_atual_kwh=self.volume_atual_kwh,
            variacao_volume_kwh=delta_volume,
            variacao_volume_pct=razao(delta_volume, self.volume_base_kwh, 100),
        )

    def efeitos(self):
        return Efeitos(
            volume=self.volume, reajuste=self.reajuste, bandeira=self.bandeira, mix=self.mix
        )


def somar_efeitos(linhas, chave):
    """Soma efeitos por subgrão conforme contracts/README.md (R5) e
    contracts/tabelas/receita_volume_mensal.yaml.
    """
    totais = {}
    for linha in linhas:
        efeitos = decompor(*(linha[f'{campo}{n}'] for n in (0, 1) for campo in 'qrtb'))
        valor = Totais(
            receita_base=linha['r0'],
            receita_atual=linha['r1'],
            volume_base_kwh=linha['q0'],
            volume_atual_kwh=linha['q1'],
            volume=efeitos.volume,
            reajuste=efeitos.reajuste,
            bandeira=efeitos.bandeira,
            mix=efeitos.mix,
        )
        totais.setdefault(chave(linha), Totais()).adicionar(valor)
    return totais


async def dados(db, periodo, comparacao, recorte):
    if recorte.alimentador is not None:
        raise APIError(422, 'Recorte por alimentador indisponível para receita', 'RECORTE_INVALIDO')
    ctx = await contexto(db, periodo, comparacao)
    if ctx.anterior is None:
        raise APIError(422, 'Não há período de comparação disponível', 'COMPARACAO_INDISPONIVEL')
    linhas = await repository.por_subgrao(db, ctx.atual, ctx.anterior, recorte)
    # Cada subgrão é decomposto uma vez; os demais agrupamentos somam esses resultados.
    por_chave = somar_efeitos(
        linhas,
        lambda linha: (linha['municipio'], linha['bairro'], linha['classe'], linha['grupo_uc']),
    )
    return ctx, por_chave


def total_decomposicao(ctx, totais):
    total = Totais()
    for valor in totais.values():
        total.adicionar(valor)
    return Decomposicao(**ctx.metadados(), **total.variacao(), efeitos=total.efeitos())


async def decomposicao(db, periodo, comparacao, recorte):
    ctx, totais = await dados(db, periodo, comparacao, recorte)
    return total_decomposicao(ctx, totais)


async def locais(db, periodo, comparacao, recorte, nivel):
    ctx, totais = await dados(db, periodo, comparacao, recorte)
    return locais_de(ctx, totais, nivel)


async def grupos(db, periodo, comparacao, recorte):
    ctx, totais = await dados(db, periodo, comparacao, recorte)
    return grupos_de(ctx, totais)


# Os agrupamentos a partir de `dados`: quem precisa de mais de um (os insights) consulta
# e decompõe a receita uma vez só.
def locais_de(ctx, totais, nivel):
    agrupados = {}
    for (municipio, bairro, _classe, _grupo), valor in totais.items():
        chave = (municipio, bairro if nivel == 'bairro' else None)
        agrupados.setdefault(chave, Totais()).adicionar(valor)
    itens = [
        Local(municipio=m, bairro=b, **v.variacao(), efeitos=v.efeitos())
        for (m, b), v in agrupados.items()
    ]
    itens.sort(key=lambda item: (item.variacao, item.municipio, item.bairro or ''))
    return Locais(**ctx.metadados(), itens=itens, total=total_decomposicao(ctx, totais))


def grupos_de(ctx, totais):
    agrupados = {grupo: Totais() for grupo in GRUPOS}
    for (_, _, _, grupo), valor in totais.items():
        agrupados[grupo].adicionar(valor)
    itens = [Grupo(grupo_uc=grupo, **agrupados[grupo].variacao()) for grupo in GRUPOS]
    return Grupos(**ctx.metadados(), itens=itens)
