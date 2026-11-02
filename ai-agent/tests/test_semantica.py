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
    descrever_semantica,
    periodo_comparacao,
    periodo_padrao,
)

CONTRATOS = Path(__file__).resolve().parents[2] / 'contracts/tabelas'
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


def test_unidades_batem_com_o_contrato():
    for visao in VISOES:
        tabela = TABELA_DA_VISAO.get(visao.nome, visao.nome)
        contrato = yaml.safe_load((CONTRATOS / f'{tabela}.yaml').read_text(encoding='utf-8'))
        for coluna in visao.colunas:
            if coluna.nome in contrato['columns']:
                unidade = contrato['columns'][coluna.nome]['unit']
                assert coluna.unidade == (None if unidade == '—' else unidade), (
                    f'{visao.nome}.{coluna.nome}'
                )


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


def test_periodo_de_comparacao_e_descricao():
    periodo = periodo_padrao(date(2026, 6, 1))
    assert periodo.descricao == 'jul/2025 a jun/2026'
    assert periodo_comparacao(periodo) == Periodo(date(2024, 7, 1), date(2025, 6, 1))


def test_descricao_para_o_prompt_cita_views_vocabulario_e_limites():
    texto = descrever_semantica(periodo_padrao(date(2026, 6, 1)))
    for visao in VISOES:
        assert f'### ai_read.{visao.nome}' in texto
        for coluna in visao.colunas:
            assert f'- {coluna.nome}' in texto
    for termo in VOCABULARIO:
        assert f'"{termo.expressoes[0]}"' in texto
    for limite in LIMITES:
        assert limite.descricao in texto
    assert 'jul/2025 a jun/2026 (2025-07-01 a 2026-06-01)' in texto
    assert 'os 12 meses até a competência mais recente' in descrever_semantica()
