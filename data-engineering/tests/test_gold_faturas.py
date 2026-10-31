"""Cenários de negócio da Gold executados com Spark real e dados sintéticos."""

import sys
import unittest
import csv
import hashlib
import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'silver_to_gold'))
from gold_faturas import (  # noqa: E402
    construir_faturas,
    comparar_periodos,
    validar_reconciliacao,
    exportar_csv,
)


class GoldFaturasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder.master('local[2]')
            .appName('gold-faturas-test')
            .config('spark.ui.enabled', 'false')
            .config('spark.sql.shuffle.partitions', '2')
            .config('spark.sql.ansi.enabled', 'true')
            .config('spark.driver.bindAddress', '127.0.0.1')
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel('ERROR')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def fontes(self):
        # R0=120, Q0=100; R1=216, Q1=150 -> volume=60, preço=36.
        linhas = [
            ('FT1', 'UC100001', '2024-01', '100.00', '20.00', 'PAGA', '2024-02-10', False),
            ('FT2', 'UC100001', '2025-01', '180.00', '36.00', 'EM ABERTO', None, False),
            # Fatura órfã não participa da receita publicada.
            ('FTX1', 'UC999999', '2025-01', '900.00', '100.00', 'EM ABERTO', None, True),
        ]
        registros = []
        for ident, uc, mes, energia, tributo, status, pagamento, pendente in linhas:
            registros.append(
                (
                    ident,
                    uc,
                    mes,
                    date.fromisoformat(mes + '-20'),
                    Decimal(energia),
                    Decimal(tributo),
                    'Verde',
                    Decimal(energia) + Decimal(tributo),
                    date.fromisoformat(mes + '-28'),
                    date.fromisoformat(pagamento) if pagamento else None,
                    status,
                    pendente,
                )
            )
        faturas = self.spark.createDataFrame(
            registros,
            """
            id_fatura string, id_uc string, mes_referencia string, data_emissao date,
            valor_energia decimal(18,2), tributos decimal(18,2), bandeira_tarifaria string,
            valor_total decimal(18,2), data_vencimento date, data_pagamento date,
            status string, flag_uc_sem_cadastro boolean
        """,
        )
        cadastro = self.spark.createDataFrame(
            [('UC100001', 'Recife', 'Centro', 'Residencial')],
            'id_uc string, municipio string, bairro string, classe string',
        )
        leituras = self.spark.createDataFrame(
            [('UC100001', '2024-01', 100), ('UC100001', '2025-01', 150)],
            'id_uc string, mes_referencia string, consumo_kwh int',
        )
        return faturas, cadastro, leituras

    def construir(self, faturas=None, cadastro=None, leituras=None):
        f, c, leituras_padrao = self.fontes()
        return construir_faturas(
            f if faturas is None else faturas,
            c if cadastro is None else cadastro,
            leituras_padrao if leituras is None else leituras,
            '2025-02-15',
        )

    def comparar(self, mensal):
        return comparar_periodos(mensal, '2024-01-01', '2024-01-01', '2025-01-01', '2025-01-01')

    def test_competencia_receita_status_e_reconciliacao(self):
        faturas, _, _ = self.fontes()
        faturas = faturas.withColumn('flag_emissao_original_ambigua', F.lit(True))
        tabelas = self.construir(faturas=faturas)
        validar_reconciliacao(faturas, tabelas)
        detalhe = {r.id_fatura: r for r in tabelas['faturas'].collect()}
        self.assertEqual(set(detalhe), {'FT1', 'FT2'})
        self.assertTrue(detalhe['FT1'].flag_emissao_original_ambigua)
        # Pagamento em fevereiro continua na competência de janeiro.
        self.assertEqual(detalhe['FT1'].competencia, date(2024, 1, 1))
        self.assertEqual(detalhe['FT1'].valor_fatura_paga, Decimal('120.00'))
        self.assertEqual(detalhe['FT1'].dias_atraso, 13)
        self.assertEqual(detalhe['FT2'].valor_em_aberto, Decimal('216.00'))
        self.assertEqual(detalhe['FT2'].dias_atraso, 18)
        self.assertTrue(detalhe['FT2'].flag_vencida_em_aberto)
        excluida = tabelas['faturas_excluidas'].first()
        self.assertEqual(excluida.id_fatura, 'FTX1')
        self.assertEqual(excluida.motivo_exclusao, 'PENDENTE_CADASTRO_SILVER')
        comparacao = self.comparar(tabelas['faturamento_mensal']).first()
        self.assertEqual(comparacao.variacao_receita, Decimal('96.00'))
        self.assertEqual(comparacao.efeito_volume, Decimal('60.00'))
        self.assertEqual(comparacao.efeito_preco_efetivo, Decimal('36.00'))
        self.assertEqual(comparacao.efeito_receita_sem_volume, Decimal('0.00'))

    def test_negativo_nao_vira_abs_e_receita_permanece(self):
        _, _, leituras = self.fontes()
        leituras = leituras.withColumn(
            'consumo_kwh',
            F.when(
                F.col('mes_referencia') == '2025-01',
                -9000,
            ).otherwise(F.col('consumo_kwh')),
        )
        tabelas = self.construir(leituras=leituras)
        atual = tabelas['faturas'].filter("id_fatura = 'FT2'").first()
        self.assertIsNone(atual.volume_analise_kwh)
        self.assertIsNone(atual.preco_efetivo_total_rs_kwh)
        self.assertEqual(atual.consumo_kwh_silver, -9000)
        self.assertEqual(atual.situacao_volume, 'LEITURA_NAO_UTILIZAVEL')
        comparacao = self.comparar(tabelas['faturamento_mensal']).first()
        self.assertEqual(comparacao.efeito_volume, Decimal('-120.00'))
        self.assertEqual(comparacao.efeito_receita_sem_volume, Decimal('216.00'))
        self.assertEqual(comparacao.variacao_receita, Decimal('96.00'))

    def test_ausencia_e_zero_nao_fabricam_preco(self):
        _, _, leituras = self.fontes()
        for leituras_caso, situacao in [
            (leituras.filter("mes_referencia = '2024-01'"), 'SEM_LEITURA'),
            (leituras.withColumn('consumo_kwh', F.lit(0)), 'ZERO_KWH'),
        ]:
            with self.subTest(situacao=situacao):
                tabelas = self.construir(leituras=leituras_caso)
                atual = tabelas['faturas'].filter("id_fatura = 'FT2'").first()
                self.assertEqual(atual.situacao_volume, situacao)
                self.assertIsNone(atual.preco_efetivo_total_rs_kwh)
                comp = self.comparar(tabelas['faturamento_mensal']).first()
                self.assertEqual(
                    comp.variacao_receita,
                    comp.efeito_volume + comp.efeito_preco_efetivo + comp.efeito_receita_sem_volume,
                )

    def test_entrada_e_saida_de_segmento_preservam_receita(self):
        faturas, cadastro, leituras = self.fontes()
        faturas = faturas.withColumn(
            'id_uc', F.when(F.col('id_fatura') == 'FT2', 'UC100002').otherwise(F.col('id_uc'))
        )
        leituras = leituras.withColumn(
            'id_uc',
            F.when(
                F.col('mes_referencia') == '2025-01',
                'UC100002',
            ).otherwise(F.col('id_uc')),
        )
        cadastro = cadastro.unionByName(
            self.spark.createDataFrame(
                [('UC100002', 'Olinda', 'Centro', 'Comercial')],
                cadastro.schema,
            )
        )
        tabelas = self.construir(faturas, cadastro, leituras)
        comps = {r.municipio: r for r in self.comparar(tabelas['faturamento_mensal']).collect()}
        self.assertEqual(comps['Olinda'].efeito_volume, Decimal('216.00'))
        self.assertIsNone(comps['Olinda'].variacao_receita_pct)
        self.assertEqual(comps['Recife'].efeito_volume, Decimal('-120.00'))
        self.assertEqual(sum(r.variacao_receita for r in comps.values()), Decimal('96.00'))

    def test_join_nao_pode_multiplicar_faturas(self):
        _, cadastro, leituras = self.fontes()
        with self.assertRaisesRegex(ValueError, 'cadastro: chave duplicada'):
            self.construir(cadastro=cadastro.unionByName(cadastro))
        with self.assertRaisesRegex(ValueError, 'leituras: chave duplicada'):
            self.construir(leituras=leituras.unionByName(leituras))

    def test_multiplas_faturas_nao_repetem_volume(self):
        faturas, _, _ = self.fontes()
        segunda = faturas.filter("id_fatura = 'FT2'").withColumn('id_fatura', F.lit('FT3'))
        tabelas = self.construir(faturas=faturas.unionByName(segunda))
        self.assertEqual(tabelas['faturas'].count(), 1)
        self.assertEqual(
            tabelas['faturas_excluidas']
            .filter("motivo_exclusao = 'MULTIPLAS_FATURAS_UC_MES'")
            .count(),
            2,
        )

    def test_novo_orfao_e_segregado_e_id_duplicado_bloqueia(self):
        faturas, cadastro, _ = self.fontes()
        tabelas = self.construir(cadastro=cadastro.limit(0))
        self.assertEqual(tabelas['faturas'].count(), 0)
        self.assertEqual(tabelas['faturas_excluidas'].count(), 3)
        with self.assertRaisesRegex(ValueError, 'faturas: chave duplicada'):
            self.construir(faturas=faturas.unionByName(faturas.limit(1)))

    def test_inconsistencia_financeira_pagamento_e_periodo_bloqueiam(self):
        faturas, _, _ = self.fontes()
        with self.assertRaisesRegex(ValueError, 'total_divergente'):
            self.construir(
                faturas=faturas.withColumn(
                    'valor_total',
                    F.lit('0.01').cast('decimal(18,2)'),
                )
            )
        with self.assertRaisesRegex(ValueError, 'paga_sem_pagamento'):
            self.construir(faturas=faturas.withColumn('data_pagamento', F.lit(None).cast('date')))
        mensal = self.construir()['faturamento_mensal']
        with self.assertRaisesRegex(ValueError, 'mesma duração'):
            comparar_periodos(mensal, '2024-01-01', '2024-02-01', '2025-01-01', '2025-01-01')
        with self.assertRaisesRegex(ValueError, 'Competência ausente'):
            comparar_periodos(mensal, '2024-02-01', '2024-02-01', '2025-02-01', '2025-02-01')

    def test_exportacao_csv_preserva_centavos_nulos_e_hashes(self):
        faturas, _, _ = self.fontes()
        for coluna in ['valor_energia', 'valor_total']:
            faturas = faturas.withColumn(
                coluna,
                (
                    F.col(coluna)
                    + F.when(F.col('id_fatura') == 'FT1', F.lit(Decimal('0.01')))
                    .when(F.col('id_fatura') == 'FT2', F.lit(Decimal('0.02')))
                    .otherwise(F.lit(0))
                ).cast('decimal(18,2)'),
            )
        tabelas = self.construir(faturas=faturas)
        tabelas['variacao_receita'] = self.comparar(tabelas['faturamento_mensal'])
        comparacao = tabelas['variacao_receita'].first()
        # P0=1,2001; delta Q=50 -> 60,005, arredondado para 60,01.
        self.assertEqual(comparacao.efeito_volume, Decimal('60.01'))
        self.assertEqual(comparacao.efeito_preco_efetivo, Decimal('36.00'))
        with tempfile.TemporaryDirectory() as pasta:
            lote = exportar_csv(
                tabelas,
                str(Path(pasta) / 'lote'),
                {
                    'batch_id': 'lote',
                    'synthetic': True,
                    'data_referencia': '2025-02-15',
                },
            )
            manifesto = json.loads((lote / 'manifest.json').read_text())
            self.assertTrue(manifesto['synthetic'])
            self.assertEqual(set(manifesto['tabelas']), set(tabelas))
            for nome, tabela in manifesto['tabelas'].items():
                linhas = []
                for parte in tabela['arquivos']:
                    arquivo = lote / parte['arquivo']
                    self.assertEqual(
                        hashlib.sha256(arquivo.read_bytes()).hexdigest(), parte['sha256']
                    )
                    with arquivo.open(encoding='utf-8', newline='') as stream:
                        leitor = csv.DictReader(stream)
                        self.assertEqual(leitor.fieldnames, [c['nome'] for c in tabela['colunas']])
                        linhas.extend(leitor)
                self.assertEqual(len(linhas), tabela['registros'])
                for coluna, total in tabela['totais_controle'].items():
                    self.assertEqual(sum(Decimal(r[coluna] or '0') for r in linhas), Decimal(total))
                if nome == 'faturas':
                    aberta = next(r for r in linhas if r['id_fatura'] == 'FT2')
                    self.assertEqual(aberta['data_pagamento'], '')
                    self.assertEqual(aberta['valor_total'], '216.02')
            with self.assertRaises(FileExistsError):
                exportar_csv(tabelas, str(lote), {'batch_id': 'lote'})


if __name__ == '__main__':
    unittest.main()
