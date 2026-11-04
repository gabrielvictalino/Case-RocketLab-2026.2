import pytest

from venergy_ai.numeros import numeros_citados, numeros_da_pergunta, numeros_sem_lastro

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
    assert numeros_sem_lastro('Alta de 5,3%.', [[5.3]]) == []
    # Uma queda não vale para uma variação positiva...
    assert numeros_sem_lastro('Queda de 5,3%.', [[5.3]], colunas=['variacao_pct']) == ['5,3%']
    assert numeros_sem_lastro('A receita caiu 5,3%.', [[5.3]]) == ['5,3%']
    # ...a não ser que a coluna seja o tamanho da queda, que vem positivo.
    assert numeros_sem_lastro('Queda de 5,3%.', [[5.3]], colunas=['queda_pct']) == []


@pytest.mark.parametrize(
    'texto,linhas',
    [
        # "de X para Y" fala de dois níveis.
        ('A receita caiu de R$ 10 milhões para R$ 8 milhões.', [[10_000_000, 8_000_000]]),
        ('A inadimplência caiu de 5,1% para 4,3%.', [[5.1, 4.3]]),
        # Perdas, o mais baixo e a energia recuperada são níveis, não quedas.
        ('As perdas de 351 kWh se concentram em Recife.', [[351]]),
        ('O DEC mais baixo foi 3,2 h.', [[3.2]]),
        ('A energia recuperada de 125 kWh.', [[125]]),
    ],
)
def test_niveis_nao_tem_direcao(texto, linhas):
    assert numeros_sem_lastro(texto, linhas) == []


def test_alta_com_real_no_meio():
    assert numeros_sem_lastro('Aumento de R$ 1.234.', [[-1234]]) == ['1.234']
    assert numeros_sem_lastro('Aumento de R$1.234.', [[-1234]]) == ['1.234']
    assert numeros_sem_lastro('Aumento de R$ 1.234.', [[1234]]) == []
    assert numeros_sem_lastro('Queda de R$ 1.234.', [[1234]]) == ['1.234']


@pytest.mark.parametrize(
    'texto,valor,coluna',
    [
        ('O volume foi de 351,2 MWh.', 351.2, 'volume_mwh'),
        ('A receita foi de R$ 1,2 milhão.', 1.2, 'receita_milhoes'),
        ('Foram 12 mil UCs.', 12, 'ucs_mil'),
    ],
)
def test_valor_ja_na_escala_do_texto(texto, valor, coluna):
    # O SQL devolveu o valor já na escala, e o nome da coluna diz isso.
    assert numeros_sem_lastro(texto, [[valor]], colunas=[coluna]) == []


@pytest.mark.parametrize(
    'texto,linhas,permitidos,coluna,sem_lastro',
    [
        # Sem a escala no nome da coluna, o número sem a escala não se sustenta.
        ('A receita foi de R$ 1,2 milhão.', [[1.2]], [], 'tarifa', ['1,2 milhão']),
        ('Foram 12 mil UCs.', [[12]], [], 'ucs', ['12 mil']),
        # 351 kWh não são 351 MWh.
        ('O consumo foi de 351 MWh.', [[351]], [], 'consumo_kwh', ['351 MWh']),
        # Nem contra os números permitidos: os 12 meses e as 5 linhas não viram receita.
        ('A receita foi de R$ 12 milhões.', [[3456789.12]], [12], 'receita', ['12 milhões']),
        ('A receita foi de R$ 5 mil.', [[3456789.12]], [5], 'receita', ['5 mil']),
        # Numa coluna já em MWh, 351.200 são 351.200 MWh: "351,2 MWh" é mil vezes menor.
        ('O volume foi de 351,2 MWh.', [[351200]], [], 'volume_mwh', ['351,2 MWh']),
        ('A receita foi de R$ 1,2 milhão.', [[1200000]], [], 'receita_milhoes', ['1,2 milhão']),
    ],
)
def test_escala_inventada_nao_se_sustenta(texto, linhas, permitidos, coluna, sem_lastro):
    assert numeros_sem_lastro(texto, linhas, permitidos, colunas=[coluna]) == sem_lastro


@pytest.mark.parametrize(
    'texto,valor,sem_lastro',
    [
        ('A receita foi de R$ 1 milhão.', 1_999_999, ['1 milhão']),
        ('Foram 2 mil kWh.', 2999, ['2 mil']),
        ('Ficou em 0.', 0.99, ['0']),
        # Com dois dígitos significativos, o truncamento continua valendo.
        ('O índice ficou em 16,6.', 16.66, []),
        ('A receita foi de R$ 1,9 milhão.', 1_999_999, []),
    ],
)
def test_truncamento_so_com_dois_digitos(texto, valor, sem_lastro):
    assert numeros_sem_lastro(texto, [[valor]]) == sem_lastro


@pytest.mark.parametrize(
    'texto,valor',
    [('A taxa ficou em 20,0%.', 20.06), ('Foram 10,0 h.', 10.06), ('O índice foi 1,50.', 1.509)],
)
def test_zeros_a_direita_contam_como_algarismos(texto, valor):
    # "20,0" mostra três algarismos, como "16,6": o truncamento vale.
    assert numeros_sem_lastro(texto, [[valor]], colunas=['taxa_pct']) == []


@pytest.mark.parametrize(
    'texto,linhas,coluna',
    [
        # O número depois de "caiu para" é o nível final, não o tamanho da queda.
        ('O consumo caiu para 351 kWh.', [[351]], 'consumo_kwh'),
        ('O consumo caiu de 400 kWh para 351 kWh.', [[400], [351]], 'consumo_kwh'),
        ('O DEC reduziu para 3,2 h.', [[3.2]], 'dec_horas'),
        ('O DEC recuou a 3,2 h.', [[3.2]], 'dec_horas'),
        ('A receita subiu para R$ 1.234.', [[1234]], 'receita'),
        # "queda em 33 UCs" conta onde houve queda.
        ('Houve queda em 33 UCs.', [[33]], 'ucs'),
    ],
)
def test_nivel_depois_da_variacao_nao_tem_direcao(texto, linhas, coluna):
    assert numeros_sem_lastro(texto, linhas, colunas=[coluna]) == []


def test_tamanho_da_variacao_continua_com_direcao():
    assert numeros_sem_lastro('O consumo caiu 351 kWh.', [[351]], colunas=['consumo_kwh']) == [
        '351'
    ]
    # "para a classe" não é "de X para Y": a queda continua precisando de valor negativo.
    assert numeros_sem_lastro(
        'Queda de 5% para a classe comercial.', [[5]], colunas=['variacao_pct']
    ) == ['5%']


def test_coluna_de_perdas_nao_e_coluna_de_queda():
    # perdas_kwh é o nível de perdas: positivo, ele não sustenta uma queda.
    texto = 'As perdas tiveram queda de 351 kWh.'
    assert numeros_sem_lastro(texto, [[351]], colunas=['perdas_kwh']) == ['351']
    assert numeros_sem_lastro(texto, [[351]], colunas=['reducao_perdas_kwh']) == []


def test_limiar_da_pergunta_so_vale_como_limiar():
    assert numeros_sem_lastro('Foram 33 UCs com queda acima de 30%.', [[33]], limiares=[30]) == []
    assert numeros_sem_lastro('Pelo menos 3 UCs.', [[1]], limiares=[3]) == []
    assert numeros_sem_lastro('A queda média foi de 30%.', [[33]], limiares=[30]) == ['30%']


@pytest.mark.parametrize(
    'pergunta,numeros',
    [
        ('Quais os 10 bairros com maior queda?', [10]),
        ('Qual a receita dos últimos 3 anos?', [3]),
        ('Quantas UCs têm 3 ou mais interrupções?', [3]),
        ('Quantas UCs tiveram queda acima de 30%?', [30]),
        ('Quais os 5 piores alimentadores?', [5]),
        ('Top 5 bairros por receita', [5]),
        # Um número afirmado na pergunta não tem papel: a resposta não pode repeti-lo.
        ('A receita de Recife foi R$ 9.876.543,21, certo?', []),
        ('Há 2000 UCs com GD?', []),
        ('A inadimplência foi 30%?', []),
    ],
)
def test_numeros_da_pergunta_so_os_que_tem_papel(pergunta, numeros):
    assert [float(n) for n in numeros_da_pergunta(pergunta)] == numeros


@pytest.mark.parametrize(
    'pergunta,texto,linhas',
    [
        ('Quais os 10 bairros com maior queda?', 'Dos 10 bairros pedidos, só 7 têm dado.', [[7]]),
        ('Qual a receita dos últimos 3 anos?', 'Nos últimos 3 anos, foram R$ 1.234.', [[1234]]),
        (
            'Quantas UCs têm 3 ou mais interrupções?',
            'Há 42 UCs com 3 ou mais interrupções.',
            [[42]],
        ),
    ],
)
def test_resposta_repete_o_numero_da_pergunta_no_mesmo_papel(pergunta, texto, linhas):
    assert numeros_sem_lastro(texto, linhas, limiares=numeros_da_pergunta(pergunta)) == []


def test_numero_afirmado_na_pergunta_nao_vira_limiar_na_resposta():
    limiares = numeros_da_pergunta('A receita de Recife foi R$ 9.876.543,21, certo?')
    texto = 'A receita foi de mais de R$ 9.876.543,21.'
    assert numeros_sem_lastro(texto, [[1234567.89]], limiares=limiares) == ['9.876.543,21']


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


def test_ano_permitido_so_vale_em_contexto_de_tempo():
    # "São 2025 UCs" é uma contagem: o ano permitido não a sustenta.
    assert numeros_sem_lastro('São 2025 UCs.', [[300]], [2025]) == ['2025']
    assert numeros_sem_lastro('Há 2025 clientes em 2025.', [[300]], [2025]) == ['2025']
    assert numeros_sem_lastro('De 2024 para 2025, e desde 2025.', [[300]], [2024, 2025]) == []
    assert numeros_sem_lastro('2025 foi o ano.', [[300]], [2025]) == []


def test_coluna_em_percentual_nao_e_lida_como_razao():
    assert numeros_sem_lastro('A taxa foi de 742%.', [[7.42]], colunas=['taxa_pct']) == ['742%']
    assert numeros_sem_lastro('A taxa foi de 7,42%.', [[7.42]], colunas=['taxa_pct']) == []
    # Sem o nome, o valor pode ser a razão: 0,0742 → 7,42%.
    assert numeros_sem_lastro('A taxa foi de 7,42%.', [[0.0742]], colunas=['taxa']) == []
