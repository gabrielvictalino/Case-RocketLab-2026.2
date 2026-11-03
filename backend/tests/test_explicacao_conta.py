from datetime import date
from decimal import Decimal

import pytest

from app.core.decomposicao import decompor
from app.core.errors import APIError
from app.modules.ucs.service import (
    explicar_conta,
    mascarar_documento,
    normalizar_id_uc,
)


def test_decompor_exemplo_numerico_r5():
    # Exemplo conferido do contracts/README.md: Recife, Residencial (2025-06 vs 2025-07)
    q0 = Decimal('2905')
    r0 = Decimal('2324.00')
    t0 = Decimal('2324.00')
    b0 = Decimal('0.00')

    q1 = Decimal('2652')
    r1 = Decimal('2386.80')
    t1 = Decimal('2121.60')
    b1 = Decimal('265.20')

    ef = decompor(q0, r0, t0, b0, q1, r1, t1, b1)
    assert ef.volume == Decimal('-202.40')
    assert ef.reajuste == Decimal('0.00')
    assert ef.bandeira == Decimal('265.20')
    assert ef.mix == Decimal('0.00')
    assert ef.volume + ef.reajuste + ef.bandeira + ef.mix == r1 - r0


def test_decompor_casos_de_borda():
    # Caso 1: Q0 = 0
    ef_q0_zero = decompor(
        q0=Decimal('0'),
        r0=Decimal('0.00'),
        t0=Decimal('0.00'),
        b0=Decimal('0.00'),
        q1=Decimal('100'),
        r1=Decimal('80.00'),
        t1=Decimal('80.00'),
        b1=Decimal('0.00'),
    )
    assert ef_q0_zero.volume == Decimal('80.00')
    assert ef_q0_zero.reajuste == Decimal('0.00')
    assert ef_q0_zero.bandeira == Decimal('0.00')
    assert ef_q0_zero.mix == Decimal('0.00')

    # Caso 2: T0 + B0 = 0
    ef_tb_zero = decompor(
        q0=Decimal('100'),
        r0=Decimal('80.00'),
        t0=Decimal('0.00'),
        b0=Decimal('0.00'),
        q1=Decimal('120'),
        r1=Decimal('100.00'),
        t1=Decimal('100.00'),
        b1=Decimal('0.00'),
    )
    assert ef_tb_zero.volume == Decimal('20.00')
    assert ef_tb_zero.reajuste == Decimal('0.00')
    assert ef_tb_zero.bandeira == Decimal('0.00')
    assert ef_tb_zero.mix == Decimal('0.00')

    # Caso 3: Q1 = 0
    ef_q1_zero = decompor(
        q0=Decimal('100'),
        r0=Decimal('80.00'),
        t0=Decimal('80.00'),
        b0=Decimal('0.00'),
        q1=Decimal('0'),
        r1=Decimal('0.00'),
        t1=Decimal('0.00'),
        b1=Decimal('0.00'),
    )
    assert ef_q1_zero.volume == Decimal('-80.00')
    assert ef_q1_zero.reajuste == Decimal('0.00')
    assert ef_q1_zero.bandeira == Decimal('0.00')
    assert ef_q1_zero.mix == Decimal('0.00')


def test_decompor_q1_zero_com_cobranca_fecha_no_mix():
    # Fatura anterior R$ 80 / 100 kWh; atual R$ 30 / 0 kWh: o mix preserva os R$ 30
    ef = decompor(
        q0=Decimal('100'),
        r0=Decimal('80.00'),
        t0=Decimal('80.00'),
        b0=Decimal('0.00'),
        q1=Decimal('0'),
        r1=Decimal('30.00'),
        t1=Decimal('0.00'),
        b1=Decimal('0.00'),
    )
    assert ef.volume == Decimal('-80.00')
    assert ef.reajuste == Decimal('0.00')
    assert ef.bandeira == Decimal('0.00')
    assert ef.mix == Decimal('30.00')
    assert ef.volume + ef.reajuste + ef.bandeira + ef.mix == Decimal('-50.00')


def test_normalizacao_id_uc():
    assert normalizar_id_uc('UC100123') == 'UC100123'
    assert normalizar_id_uc('uc100123') == 'UC100123'
    assert normalizar_id_uc('100123') == 'UC100123'
    assert normalizar_id_uc(' 100123 ') == 'UC100123'
    assert normalizar_id_uc('UC999999') == 'UC999999'

    with pytest.raises(APIError) as exc_info:
        normalizar_id_uc('abc')
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'UC_INVALIDA'

    with pytest.raises(APIError):
        normalizar_id_uc('12345')

    with pytest.raises(APIError):
        normalizar_id_uc('UC1234567')


def test_mascarar_documento():
    assert mascarar_documento('123.456.789-00') == '***.456.789-**'
    assert mascarar_documento('12345678900') == '***.456.789-**'
    assert mascarar_documento('12.345.678/0001-90') == '**.345.678/0001-**'
    assert mascarar_documento('12345678000190') == '**.345.678/0001-**'
    assert mascarar_documento('***.456.789-**') == '***.456.789-**'
    assert mascarar_documento('**.345.678/0001-**') == '**.345.678/0001-**'
    assert mascarar_documento('invalido') == '***'
    assert mascarar_documento('') == '***'
    assert mascarar_documento(None) == '***'


def test_explicar_conta_sem_fatura():
    exp = explicar_conta(None, None)
    assert exp.situacao == 'SEM_FATURA'
    assert exp.frase == 'A UC ainda não tem fatura emitida.'
    assert exp.atual is None
    assert exp.anterior is None


def test_explicar_conta_sem_base():
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('150'),
        'valor_total': Decimal('120.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, None)
    assert exp.situacao == 'SEM_BASE'
    assert exp.frase == (
        'Não há fatura de 06/2025 para comparar: a UC não tem um ano de histórico de faturamento.'
    )
    assert exp.atual is not None
    assert exp.anterior is None


def test_explicar_conta_consumo_subiu():
    anterior = {
        'competencia': date(2025, 6, 1),
        'id_fatura': 'FT000',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('120'),
        'valor_total': Decimal('96.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, anterior)
    assert exp.situacao == 'COMPARADA'
    assert exp.efeitos.consumo == Decimal('16.00')
    assert 'O consumo faturado subiu 20%' in exp.frase
    assert 'a fatura subiu R$ 16,00 (20,0%) principalmente pela variação do consumo.' in exp.frase


def test_explicar_conta_bandeira_mudou():
    # Consumo caiu 3% (100 -> 97), bandeira VERDE -> VERMELHA_P2
    anterior = {
        'competencia': date(2025, 6, 1),
        'id_fatura': 'FT000',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    # Atual: Q=97, tarifa=0.80, bandeira=0.15 (Vermelha P2), T=77.60, B=14.55, R=92.15
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('97'),
        'valor_total': Decimal('92.15'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.15'),
        'bandeira': 'VERMELHA_P2',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, anterior)
    assert exp.situacao == 'COMPARADA'
    assert 'caiu 3%' in exp.frase
    assert 'Vermelha P2 (antes Verde)' in exp.frase
    assert 'principalmente por causa da bandeira Vermelha P2' in exp.frase


def test_explicar_conta_reajuste_tarifa():
    # Q0=100, Q1=100, tarifa 0.70 -> 0.80
    anterior = {
        'competencia': date(2025, 6, 1),
        'id_fatura': 'FT000',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('70.00'),
        'tarifa_base': Decimal('0.70'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, anterior)
    assert exp.situacao == 'COMPARADA'
    assert 'O consumo faturado ficou estável' in exp.frase
    assert 'principalmente pelo reajuste da tarifa (de R$ 0,70 para R$ 0,80 por kWh)' in exp.frase


def test_explicar_conta_avisos_troca_e_leitura_estimada():
    # Troca no mês anterior e leitura estimada no mês atual
    anterior = {
        'competencia': date(2025, 6, 1),
        'id_fatura': 'FT000',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': True,
    }
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'ESTIMADA',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, anterior)
    # A troca só é citada: a imputação da Gold altera o consumo analítico, não a fatura
    assert 'Em 06/2025 houve troca de medidor.' in exp.frase
    assert 'estimado' not in exp.frase
    assert 'A leitura de 06/2026 foi estimada.' in exp.frase


def test_explicar_conta_aviso_supressao_estimada_quando_troca():
    # Se o mês teve troca de medidor, o aviso de leitura estimada não deve aparecer para aquele mês
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'ESTIMADA',
        'flag_troca_medidor': True,
    }
    exp = explicar_conta(atual, None)
    assert 'Em 06/2026 houve troca de medidor' in exp.frase
    assert 'A leitura de 06/2026 foi estimada.' not in exp.frase


def test_explicar_conta_delta_r_zero():
    anterior = {
        'competencia': date(2025, 6, 1),
        'id_fatura': 'FT000',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    atual = {
        'competencia': date(2026, 6, 1),
        'id_fatura': 'FT001',
        'volume_faturado_kwh': Decimal('100'),
        'valor_total': Decimal('80.00'),
        'tarifa_base': Decimal('0.80'),
        'adicional_bandeira': Decimal('0.00'),
        'bandeira': 'VERDE',
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }
    exp = explicar_conta(atual, anterior)
    assert exp.frase == 'O consumo faturado ficou estável; a fatura ficou igual.'


def _fatura(competencia, volume, valor, tarifa='0.80', adicional='0.00', bandeira='VERDE'):
    return {
        'competencia': competencia,
        'id_fatura': f'FT{competencia:%Y%m}',
        'volume_faturado_kwh': Decimal(volume),
        'valor_total': Decimal(valor),
        'tarifa_base': Decimal(tarifa),
        'adicional_bandeira': Decimal(adicional),
        'bandeira': bandeira,
        'tipo_leitura': 'REAL',
        'flag_troca_medidor': False,
    }


def test_explicar_conta_motivo_outros_componentes():
    # Alta de R$ 108: R$ 8 por consumo (100 -> 110 kWh a R$ 0,80) e R$ 100 de outros
    anterior = _fatura(date(2025, 6, 1), '100', '80.00')
    atual = _fatura(date(2026, 6, 1), '110', '188.00')
    exp = explicar_conta(atual, anterior)
    assert exp.efeitos.consumo == Decimal('8.00')
    assert exp.efeitos.outros == Decimal('100.00')
    assert 'principalmente por tributos e outros componentes' in exp.frase
    assert 'pela variação do consumo' not in exp.frase


def test_explicar_conta_base_zero():
    # 0 -> 100 kWh e R$ 0 -> R$ 80: percentuais indefinidos ficam fora da frase
    anterior = _fatura(date(2025, 6, 1), '0', '0.00')
    atual = _fatura(date(2026, 6, 1), '100', '80.00')
    exp = explicar_conta(atual, anterior)
    assert exp.variacao_valor_pct is None
    assert exp.variacao_consumo_pct is None
    assert exp.frase == (
        'O consumo faturado subiu de 0 para 100 kWh; '
        'a fatura subiu R$ 80,00 principalmente pela variação do consumo.'
    )


def test_explicar_conta_volume_atual_zero_com_cobranca():
    # R$ 80 / 100 kWh -> R$ 30 / 0 kWh: efeitos fecham em -R$ 50
    anterior = _fatura(date(2025, 6, 1), '100', '80.00')
    atual = _fatura(date(2026, 6, 1), '0', '30.00')
    exp = explicar_conta(atual, anterior)
    ef = exp.efeitos
    assert ef.consumo + ef.tarifa + ef.bandeira + ef.outros == exp.variacao_valor
    assert exp.variacao_valor == Decimal('-50.00')
    assert exp.frase == (
        'O consumo faturado caiu 100%; '
        'a fatura caiu R$ 50,00 (62,5%) principalmente pela variação do consumo.'
    )


def test_ocorrencia_uc_duracao_fracionaria():
    from datetime import datetime

    from app.modules.ucs.schemas import OcorrenciaUC

    oc = OcorrenciaUC(
        id_ocorrencia='OC123',
        data_abertura=datetime(2026, 1, 1, 10, 0),
        data_encerramento=datetime(2026, 1, 1, 10, 1, 20),
        duracao_min=Decimal('1.33'),
        duracao_efetiva_min=Decimal('1.33'),
        causa='SINTETICA',
        flag_sobreposicao=False,
    )
    dumped = oc.model_dump(mode='json')
    assert dumped['duracao_min'] == '1.33'
    assert oc.duracao_min == Decimal('1.33')
