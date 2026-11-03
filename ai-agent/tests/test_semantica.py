import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from venergy_ai.semantica import (
    LIMITES,
    VISOES,
    VISOES_POR_NOME,
    VOCABULARIO,
    Periodo,
    descrever_periodo_padrao,
    descrever_semantica,
    periodo_comparacao,
    periodo_padrao,
)
from venergy_ai.semantica.contexto import filtro_do_periodo, linha_da_coluna

RAIZ = Path(__file__).resolve().parents[2]
CONTRATOS = RAIZ / 'contracts/tabelas'
# Views que não têm o nome da tabela do contrato que copiam.
TABELA_DA_VISAO = {'ucs': 'dim_uc', 'inspecoes': 'inspecoes_historicas'}
COLUNAS_PESSOAIS = {
    'nome_titular',
    'titular',
    'cpf_cnpj',
    'documento_mascarado',
    'logradouro',
    'numero',
    'cep',
    'endereco',
    'descricao',
}
# Colunas sem enum no contrato: os valores vêm da limpeza documentada. Os que não estão
# na doc vêm da própria view (o OUTRO das inspeções do portal).
DOMINIOS_DA_LIMPEZA = {
    ('ocorrencias_uc', 'causa'): ('docs/gold/continuidade.md', ()),
    ('continuidade_alimentador_mensal', 'causa'): ('docs/gold/continuidade.md', ()),
    ('atendimentos', 'assunto'): ('docs/overview_dados/atendimentos.md', ()),
    ('medidores_historico', 'tipo_medidor'): ('docs/silver/silver_medidores.md', ()),
    ('inspecoes', 'tipo_irregularidade'): ('docs/silver/silver_inspecoes.md', ('OUTRO',)),
}
MES = re.compile(r'\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{4}\b')


def test_views_e_colunas_sem_repeticao():
    assert len(VISOES_POR_NOME) == len(VISOES)
    for visao in VISOES:
        nomes = [coluna.nome for coluna in visao.colunas]
        assert len(set(nomes)) == len(nomes), visao.nome
        assert set(visao.chave) <= set(nomes), visao.nome
        assert visao.coluna_tempo is None or visao.coluna_tempo in nomes, visao.nome
        assert visao.descricao and visao.grao and visao.periodo, visao.nome
        assert all(coluna.descricao for coluna in visao.colunas), visao.nome


def test_catalogo_sem_colunas_pessoais():
    assert not {c.nome for v in VISOES for c in v.colunas} & COLUNAS_PESSOAIS


@pytest.mark.parametrize(
    'referencia',
    sorted({r for item in (*VOCABULARIO, *LIMITES) for r in item.referencias}),
)
def test_referencias_existem_no_catalogo(referencia):
    nome, _, coluna = referencia.partition('.')
    visao = VISOES_POR_NOME[nome]
    if coluna:
        visao.coluna(coluna)


def contrato(visao):
    tabela = TABELA_DA_VISAO.get(visao.nome, visao.nome)
    return yaml.safe_load((CONTRATOS / f'{tabela}.yaml').read_text(encoding='utf-8'))


def colunas_do_contrato(visao):
    return contrato(visao)['columns']


@pytest.mark.parametrize('visao', VISOES, ids=lambda visao: visao.nome)
def test_grao_e_chave_batem_com_o_contrato(visao):
    # Uma chave errada no prompt leva a contagem dupla nos joins.
    assert visao.grao == contrato(visao)['grain']
    assert visao.chave == tuple(contrato(visao)['primary_key'])


def test_unidades_batem_com_o_contrato():
    for visao in VISOES:
        contrato = colunas_do_contrato(visao)
        for coluna in visao.colunas:
            if coluna.nome in contrato:
                unidade = contrato[coluna.nome]['unit']
                assert coluna.unidade == (None if unidade == '—' else unidade), (
                    f'{visao.nome}.{coluna.nome}'
                )


@pytest.mark.parametrize(
    'visao, coluna',
    [(visao, coluna) for visao in VISOES for coluna in visao.colunas],
    ids=lambda item: getattr(item, 'nome', ''),
)
def test_valores_e_faixas_batem_com_o_contrato(visao, coluna):
    # Nos dois sentidos: um valor novo no contrato, ou um que saiu dele, quebra o teste.
    do_contrato = colunas_do_contrato(visao).get(coluna.nome, {})
    nome = f'{visao.nome}.{coluna.nome}'
    if 'enum' in do_contrato or (visao.nome, coluna.nome) not in DOMINIOS_DA_LIMPEZA:
        assert coluna.valores == tuple(do_contrato.get('enum', ())), nome
    faixa = (do_contrato['minimum'], do_contrato['maximum']) if 'maximum' in do_contrato else None
    assert coluna.faixa == faixa, nome


@pytest.mark.parametrize(('visao', 'coluna'), DOMINIOS_DA_LIMPEZA, ids='.'.join)
def test_dominios_fora_do_contrato_estao_na_limpeza(visao, coluna):
    # Um valor que a limpeza não produz faria o agente filtrar por algo que não existe.
    doc, da_view = DOMINIOS_DA_LIMPEZA[visao, coluna]
    texto = (RAIZ / doc).read_text(encoding='utf-8')
    valores = VISOES_POR_NOME[visao].coluna(coluna).valores
    assert valores
    assert [v for v in valores if f'`{v}`' not in texto] == list(da_view)


def test_tipos_de_irregularidade_batem_com_a_view():
    sql = (RAIZ / 'importador/views.sql').read_text(encoding='utf-8')
    view = sql.split('CREATE VIEW ai_read.inspecoes', 1)[1].split(';', 1)[0]
    tipos = re.findall(r"'([^']+)'", re.search(r'tipo_irregularidade IN \(([^)]*)\)', view)[1])
    assert VISOES_POR_NOME['inspecoes'].coluna('tipo_irregularidade').valores == (
        *tipos,
        'OUTRO',
    )


def test_nota_de_1_a_5_no_prompt():
    nota = VISOES_POR_NOME['atendimentos'].coluna('nota')
    assert 'Escala de 1 a 5.' in linha_da_coluna(nota)
    texto = descrever_semantica()
    assert '0 a 10' not in texto and 'Nota de 1 a 5' in texto


@pytest.mark.parametrize(
    ('mais_recente', 'inicio', 'fim'),
    [
        (date(2026, 6, 1), date(2025, 7, 1), date(2026, 6, 1)),
        (date(2026, 6, 30), date(2025, 7, 1), date(2026, 6, 1)),
        (date(2026, 1, 1), date(2025, 2, 1), date(2026, 1, 1)),
        (date(2025, 12, 1), date(2025, 1, 1), date(2025, 12, 1)),
    ],
)
def test_periodo_padrao_sao_os_12_meses_ate_a_mais_recente(mais_recente, inicio, fim):
    assert periodo_padrao(mais_recente) == Periodo(inicio, fim)


def test_meses_do_periodo():
    assert Periodo(date(2025, 7, 1), date(2026, 6, 1)).meses == 12
    assert Periodo(date(2026, 6, 1), date(2026, 6, 1)).meses == 1


def test_periodo_padrao_nao_comeca_antes_da_base():
    # Carga de jan a jun/2026: jul/2025 a jun/2026 cairia em PERIODO_FORA_DA_BASE.
    assert periodo_padrao(date(2026, 6, 1), date(2026, 1, 1)) == Periodo(
        date(2026, 1, 1), date(2026, 6, 1)
    )
    assert periodo_padrao(date(2026, 6, 1), date(2022, 7, 1)) == Periodo(
        date(2025, 7, 1), date(2026, 6, 1)
    )


def test_periodo_de_comparacao_e_descricao():
    periodo = periodo_padrao(date(2026, 6, 1))
    assert periodo.descricao == 'jul/2025 a jun/2026'
    assert periodo_comparacao(periodo) == Periodo(date(2024, 7, 1), date(2025, 6, 1))


def test_sem_comparacao_antes_da_base():
    # Como validar_periodos no backend: sem o ano anterior inteiro na base, não compara.
    primeiro_ano = Periodo(date(2022, 7, 1), date(2023, 6, 1))
    assert periodo_comparacao(primeiro_ano, date(2022, 7, 1)) is None
    segundo_ano = Periodo(date(2023, 7, 1), date(2024, 6, 1))
    assert periodo_comparacao(segundo_ano, date(2022, 7, 1)) == primeiro_ano


def secoes_das_views(texto):
    partes = texto.split('### ai_read.')[1:]
    return {parte.split('\n', 1)[0]: parte.split('\n') for parte in partes}


def test_descricao_para_o_prompt_cita_views_vocabulario_e_limites():
    texto = descrever_semantica()
    secoes = secoes_das_views(texto)
    assert set(secoes) == {visao.nome for visao in VISOES}
    for visao in VISOES:
        # A linha inteira, dentro da seção da própria view: "- data" não casa com "- data_x".
        for coluna in visao.colunas:
            assert linha_da_coluna(coluna) in secoes[visao.nome], f'{visao.nome}.{coluna.nome}'
    for termo in VOCABULARIO:
        assert f'"{termo.expressoes[0]}"' in texto
    for limite in LIMITES:
        assert limite.descricao in texto


def test_texto_fixo_nao_cita_mes_nem_ano():
    # A cobertura vem da carga: um mês escrito à mão faria o agente dizer "não sei" sobre
    # dados que uma exportação nova traz.
    sem_carga = descrever_semantica()
    assert MES.findall(sem_carga) == []
    assert re.findall(r'\b20\d\d\b', sem_carga) == []


def test_cobertura_e_data_de_referencia_vem_da_carga():
    base = Periodo(date(2022, 7, 1), date(2026, 7, 1))
    texto = descrever_semantica(base, date(2026, 8, 1))
    assert 'Os dados da carga cobrem as competências de jul/2022 a jul/2026' in texto
    # Os únicos meses do texto são os da carga.
    assert set(MES.findall(texto)) == {'jul'}
    assert "data_vencimento < DATE '2026-08-01'" in texto
    assert 'não responda sobre conta atrasada' in descrever_semantica(base)


@pytest.mark.parametrize(
    'base', [None, Periodo(date(2022, 7, 1), date(2026, 6, 1))], ids=['sem-carga', 'com-carga']
)
def test_inspecoes_do_portal_ficam_fora_do_limite_da_carga(base):
    # Uma inspeção concluída no portal em jul/2026, com a carga até jun/2026, existe.
    carga = descrever_semantica(base).split('## Carga', 1)[1]
    assert 'não há dado da carga' in carga
    assert "Exceção: as inspeções com origem = 'portal'" in carga


@pytest.mark.parametrize('visao', [v for v in VISOES if v.coluna_tempo], ids=lambda v: v.nome)
def test_filtro_de_periodo_inclui_o_ultimo_mes(visao):
    secao = secoes_das_views(descrever_semantica())[visao.nome]
    filtro = filtro_do_periodo(visao)
    assert f'Filtro de período: {filtro}' in secao
    if visao.coluna_tempo != 'competencia':
        # Em data e hora, um BETWEEN até o dia 1 do último mês perderia quase todo ele.
        assert "INTERVAL '1 month'" in filtro and 'BETWEEN' not in filtro


def test_periodo_padrao_traz_os_filtros_com_as_datas():
    texto = descrever_periodo_padrao(Periodo(date(2025, 7, 1), date(2026, 6, 1)), date(2022, 7, 1))
    assert (
        'Sem período na pergunta: jul/2025 a jun/2026. Em competencia: BETWEEN DATE '
        "'2025-07-01' AND DATE '2026-06-01'. Em data ou data e hora: >= DATE '2025-07-01' "
        "AND < DATE '2026-07-01'." in texto
    )
    assert 'Comparação padrão: jul/2024 a jun/2025.' in texto


def test_comparacao_da_tela_substitui_a_do_ano_anterior():
    # Período de jan a jun/2026 comparado com o semestre anterior, escolhido na tela.
    semestre = Periodo(date(2026, 1, 1), date(2026, 6, 1))
    anterior = Periodo(date(2025, 7, 1), date(2025, 12, 1))
    texto = descrever_periodo_padrao(semestre, date(2022, 7, 1), anterior)
    assert 'Comparação padrão: jul/2025 a dez/2025.' in texto
    assert 'jan/2025 a jun/2025' not in texto
    assert texto.count('Comparação padrão') == 1


def test_sem_comparacao_padrao_no_primeiro_ano_da_base():
    base = Periodo(date(2025, 7, 1), date(2026, 6, 1))
    texto = descrever_periodo_padrao(periodo_padrao(base.fim, base.inicio), base.inicio)
    assert 'Sem comparação padrão' in texto
