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
from venergy_ai.semantica.contexto import linha_da_coluna

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


def colunas_do_contrato(visao):
    tabela = TABELA_DA_VISAO.get(visao.nome, visao.nome)
    return yaml.safe_load((CONTRATOS / f'{tabela}.yaml').read_text(encoding='utf-8'))['columns']


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
    contrato = colunas_do_contrato(visao).get(coluna.nome, {})
    assert coluna.valores == tuple(contrato.get('enum', ())), f'{visao.nome}.{coluna.nome}'
    faixa = (contrato['minimum'], contrato['maximum']) if 'maximum' in contrato else None
    assert coluna.faixa == faixa, f'{visao.nome}.{coluna.nome}'


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
    texto = descrever_semantica(periodo_padrao(date(2026, 6, 1)))
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
    assert 'jul/2025 a jun/2026 (2025-07-01 a 2026-06-01)' in texto
    assert 'os 12 meses até a competência mais recente' in descrever_semantica()


def test_cobertura_e_data_de_referencia_vem_da_carga():
    # Uma carga que chega até jul/2026: nada no texto fixo diz que a base acaba em jun/2026.
    base = Periodo(date(2022, 7, 1), date(2026, 7, 1))
    texto = descrever_semantica(periodo_padrao(base.fim), base, date(2026, 8, 1))
    assert 'A base cobre as competências de jul/2022 a jul/2026' in texto
    assert 'jun/2026' not in texto.replace('ago/2025 a jul/2026', '')
    assert "data_vencimento < DATE '2026-08-01'" in texto
    assert 'Comparação padrão: ago/2024 a jul/2025' in texto
    sem_carga = descrever_semantica()
    assert 'não responda sobre conta atrasada' in sem_carga
    assert 'jul/2022' not in sem_carga and 'jun/2026' not in sem_carga


def test_sem_comparacao_padrao_no_primeiro_ano_da_base():
    base = Periodo(date(2025, 7, 1), date(2026, 6, 1))
    texto = descrever_semantica(periodo_padrao(base.fim), base)
    assert 'Sem comparação padrão' in texto
