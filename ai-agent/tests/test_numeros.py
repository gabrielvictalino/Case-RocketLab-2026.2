import pytest

from venergy_ai.numeros import numeros_citados, numeros_sem_lastro

LINHAS = [['Iputinga', -351234.5, -0.167, 1234567.89, 300, 16.66]]


@pytest.mark.parametrize(
    'texto',
    [
        'São 300 UCs.',
        'A receita foi de R$ 1.234.567,89.',
        'A receita foi de R$ 1,2 milhão.',
        'A receita foi de R$ 1.235 mil.',
        'A Iputinga caiu 351 MWh, ou −16,7%.',
        'A queda foi de 351.234,5 kWh.',
        'O índice ficou em 16,7, ou 16,6 truncado.',
        'Em 16.66 no formato em inglês.',
    ],
)
def test_numeros_com_lastro(texto):
    assert numeros_sem_lastro(texto, LINHAS) == []


@pytest.mark.parametrize(
    'texto,sem_lastro',
    [
        ('São 301 UCs.', ['301']),
        ('São 3 UCs.', ['3']),
        ('Subiu 30%.', ['30%']),
        ('Subiu +351 MWh.', ['+351 MWh']),
        ('Receita de R$ 1,3 milhão e 300 UCs.', ['1,3 milhão']),
        ('O índice ficou em 16,8.', ['16,8']),
    ],
)
def test_numeros_sem_lastro(texto, sem_lastro):
    assert numeros_sem_lastro(texto, LINHAS) == sem_lastro


@pytest.mark.parametrize(
    'texto',
    [
        'Na UC000123, no ALM-REC-001, pelo INSP-007.',
        'De jul/2025 a jun/2026, em 2025-07 e em 15/03/2025.',
        'Em julho de 2025 e no ano de 2024.',
        'O 1º colocado.',
    ],
)
def test_codigos_datas_e_anos_nao_sao_conferidos(texto):
    assert numeros_sem_lastro(texto, []) == []


def test_numeros_permitidos():
    assert numeros_sem_lastro('Nos últimos 12 meses, os 5 piores.', [], [12, 5]) == []


def test_textos_e_booleanos_das_linhas_nao_contam():
    assert numeros_sem_lastro('São 1 e 300.', [[True, '300']]) == ['1', '300']


def test_numeros_citados_na_pergunta():
    assert [float(n) for n in numeros_citados('Os 5 piores em 2025, acima de 1.000 kWh?')] == [
        5,
        1000,
        1,
    ]
