"""Os fatos de cada tela, tirados das mesmas respostas que a tela exibe.

As etiquetas são as da tela: os rótulos dos cards na Visão Geral e os blocos da
Receita (cascata, grupos de UC e detalhamento por local).
"""

from venergy_ai.interface import Fato

from app.modules.kpis.schemas import KPIs
from app.modules.receita.schemas import Decomposicao, Grupos, Locais, Variacao

EFEITOS = (
    ('volume', 'Efeito volume'),
    ('reajuste', 'Efeito reajuste'),
    ('bandeira', 'Efeito bandeira'),
    ('mix', 'Efeito mix'),
)
GRUPOS = {
    'GD': 'Volume das UCs com GD',
    'IRREGULARIDADE_CONFIRMADA': 'Volume das UCs com irregularidade confirmada',
    'DEMAIS': 'Volume das demais UCs',
}
# Os locais que mais caíram e os que mais subiram, como no detalhamento da tela.
LOCAIS_NAS_PONTAS = 3


def da_visao_geral(kpis: KPIs) -> list[Fato]:
    cards = (
        ('receita', 'Receita faturada', 'R$', kpis.receita),
        ('receita_arrecadada', 'Receita arrecadada', 'R$', kpis.receita_arrecadada),
        ('volume_faturado', 'Volume faturado', 'kWh', kpis.volume_faturado_kwh),
        ('tarifa_media', 'Tarifa média', 'R$/kWh', kpis.tarifa_media),
        ('inadimplencia', 'Inadimplência', '%', kpis.inadimplencia),
        ('ucs_ativas', 'UCs ativas', 'UCs', kpis.ucs.ativas),
        ('ucs_com_gd', 'UCs com GD', 'UCs', kpis.ucs.com_gd),
        ('dec', 'DEC', 'h por UC', kpis.continuidade.dec),
        ('fec', 'FEC', 'interrupções por UC', kpis.continuidade.fec),
        ('taxa_acerto', 'Taxa de acerto', '%', kpis.taxa_acerto),
    )
    # Um card sem valor no período não tem o que observar.
    return [
        Fato(chave=chave, metrica=metrica, unidade=unidade, **indicador.model_dump())
        for chave, metrica, unidade, indicador in cards
        if indicador.valor is not None
    ]


def da_receita(decomposicao: Decomposicao, grupos: Grupos, locais: Locais) -> list[Fato]:
    efeitos = decomposicao.efeitos
    fatos = [
        _receita('receita', 'Receita faturada', decomposicao),
        _volume('volume_faturado', 'Volume faturado', decomposicao),
        *(
            Fato(
                chave=f'efeito_{nome}', metrica=metrica, unidade='R$', valor=getattr(efeitos, nome)
            )
            for nome, metrica in EFEITOS
        ),
        *(
            _volume(f'grupo_{grupo.grupo_uc.lower()}', GRUPOS[grupo.grupo_uc], grupo)
            for grupo in grupos.itens
            if grupo.volume_base_kwh or grupo.volume_atual_kwh
        ),
    ]
    # Os itens vêm da maior queda para a maior alta.
    n = len(locais.itens)
    pontas = sorted({*range(min(LOCAIS_NAS_PONTAS, n)), *range(max(0, n - LOCAIS_NAS_PONTAS), n)})
    for indice in pontas:
        local = locais.itens[indice]
        nome = f'{local.bairro} ({local.municipio})' if local.bairro else local.municipio
        fatos.append(_receita(f'local:{nome}', f'Receita · {nome}', local))
    return fatos


def _receita(chave: str, metrica: str, v: Variacao) -> Fato:
    return Fato(
        chave=chave,
        metrica=metrica,
        unidade='R$',
        valor=v.receita_atual,
        comparacao=v.receita_base,
        variacao=v.variacao,
        variacao_pct=v.variacao_pct,
    )


def _volume(chave: str, metrica: str, v: Variacao) -> Fato:
    return Fato(
        chave=chave,
        metrica=metrica,
        unidade='kWh',
        valor=v.volume_atual_kwh,
        comparacao=v.volume_base_kwh,
        variacao=v.variacao_volume_kwh,
        variacao_pct=v.variacao_volume_pct,
    )
