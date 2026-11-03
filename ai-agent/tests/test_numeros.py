import pytest

from venergy_ai.numeros import numeros_citados, numeros_sem_lastro

LINHAS = [['Iputinga', -351234.5, -0.167, 1234567.89, 300, 16.66, 3.21]]


@pytest.mark.parametrize(
    'texto',
    [
        'São 300 UCs.',
        'A receita foi de R$ 1.234.567,89.',
        'A receita foi de R$ 1,2 milhão.',
        'A receita foi de R$ 1.235 mil.',
        'A receita foi de R$1,2mi.',
        'A Iputinga caiu 351 MWh, ou −16,7%.',
        'A queda foi de 351.234,5 kWh.',
        'A queda foi de 351234,5kWh.',
        'O índice ficou em 16,7, ou 16,6 truncado.',
        'Em 16.66 no formato em inglês.',
        'Uma variação de 16,7pp.',
        'O DEC foi de 3,2h.',
        'Foram 300 em 12 minutos.',
    ],
)
def test_numeros_com_lastro(texto):
    assert numeros_sem_lastro(texto, LINHAS, [12]) == []


@pytest.mark.parametrize(
    'texto,sem_lastro',
    [
        ('São 301 UCs.', ['301']),
        ('São 4 UCs.', ['4']),
        ('Subiu 30%.', ['30%']),
        ('Subiu +351 MWh.', ['+351 MWh']),
        ('Receita de R$ 1,3 milhão e 300 UCs.', ['1,3 milhão']),
        ('O índice ficou em 16,8.', ['16,8']),
        # Colados à unidade também são conferidos.
        ('Consumo de 352kWh.', ['352']),
        ('Receita de R$1,3mi.', ['1,3mi']),
        ('Variação de 12pp.', ['12pp']),
        ('DEC de 3,3h.', ['3,3']),
        # Uma alta não vale para um valor negativo.
        ('Cresceu 351 MWh.', ['351 MWh']),
    ],
)
def test_numeros_sem_lastro(texto, sem_lastro):
    assert numeros_sem_lastro(texto, LINHAS) == sem_lastro


def test_direcao_da_variacao():
    assert numeros_sem_lastro('Alta de 5,3%.', [[-5.3]]) == ['5,3%']
    assert numeros_sem_lastro('Queda de 5,3%.', [[-5.3]]) == []
    # Uma coluna com o tamanho da queda vem positiva.
    assert numeros_sem_lastro('Queda de 5,3%.', [[5.3]]) == []
    assert numeros_sem_lastro('Alta de 5,3%.', [[5.3]]) == []


@pytest.mark.parametrize(
    'texto',
    [
        'Na UC000123, no ALM-REC-001, pelo INSP-007.',
        'De jul/2025 a jun/2026, em 2025-07 e em 15/03/2025.',
        'Em julho de 2025, em março de 2024 e em set./2025.',
        'O 1º colocado e a 2ª colocada.',
    ],
)
def test_codigos_datas_e_ordinais_nao_sao_conferidos(texto):
    assert numeros_sem_lastro(texto, []) == []


@pytest.mark.parametrize('texto', ['mais de 7777 UCs', 'margem de 7777', 'setores de 7777'])
def test_palavra_que_comeca_como_mes_nao_vira_data(texto):
    assert numeros_sem_lastro(texto, [[10]]) == ['7777']


def test_ano_sozinho_precisa_ser_permitido_ou_estar_nas_linhas():
    assert numeros_sem_lastro('Mais de 2000 UCs em 2025.', [[10]]) == ['2000', '2025']
    assert numeros_sem_lastro('Em 2025.', [[10]], [2025]) == []
    # Uma data nas linhas deixa citar o ano dela.
    assert numeros_sem_lastro('Em 2025.', [['2025-07-01']]) == []


def test_fracao_longa_com_valor_grande_nao_estoura():
    assert numeros_sem_lastro('Razão de 0,16666666666666666.', [[123456789012345]]) == [
        '0,16666666666666666'
    ]


def test_numeros_permitidos():
    assert numeros_sem_lastro('Nos últimos 12 meses, os 5 piores.', [], [12, 5]) == []


def test_textos_e_booleanos_das_linhas_nao_contam():
    assert numeros_sem_lastro('São 1 e 300.', [[True, '300']]) == ['1', '300']


def test_numeros_citados_na_pergunta():
    assert [float(n) for n in numeros_citados('Os 5 piores em 2025, acima de 1.000 kWh?')] == [
        5,
        2025,
        1000,
        1,
    ]
