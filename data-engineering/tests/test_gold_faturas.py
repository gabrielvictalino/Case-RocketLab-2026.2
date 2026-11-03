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
    FLAGS_LEITURAS,
    construir_faturas,
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
        # Receita 120/216 e volume observado 100/150 em duas competências.
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
        for flag in FLAGS_LEITURAS:
            leituras = leituras.withColumn(flag, F.lit(False))
        return faturas, cadastro, leituras

    def construir(self, faturas=None, cadastro=None, leituras=None):
        f, c, leituras_padrao = self.fontes()
        return construir_faturas(
            f if faturas is None else faturas,
            c if cadastro is None else cadastro,
            leituras_padrao if leituras is None else leituras,
            '2025-02-15',
        )

    def test_flags_ausentes_e_tipos_invalidos_bloqueiam(self):
        _, _, leituras = self.fontes()
        for flag in FLAGS_LEITURAS:
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(ValueError, 'colunas ausentes'):
                    self.construir(leituras=leituras.drop(flag))
                with self.assertRaisesRegex(ValueError, 'precisa ser boolean'):
                    self.construir(leituras=leituras.withColumn(flag, F.lit('false')))

    def test_flags_impeditivas_e_nulas_bloqueiam_volume_positivo(self):
        _, _, leituras = self.fontes()
        for flag in FLAGS_LEITURAS:
            for valor in [True, None]:
                with self.subTest(flag=flag, valor=valor):
                    tabelas = self.construir(
                        leituras=leituras.withColumn(flag, F.lit(valor).cast('boolean'))
                    )
                    self.assertEqual(tabelas['faturas'].count(), 2)
                    self.assertEqual(
                        tabelas['faturas'].filter('volume_analise_kwh IS NOT NULL').count(), 0
                    )

    def test_competencia_receita_status_e_reconciliacao(self):
        faturas, _, _ = self.fontes()
        faturas = faturas.withColumn('flag_emissao_original_ambigua', F.lit(True))
        tabelas = self.construir(faturas=faturas)
        validar_reconciliacao(faturas, tabelas)
        self.assertEqual(
            tabelas['faturamento_mensal'].schema['cobertura_volume_pct'].dataType.simpleString(),
            'decimal(5,2)',
        )
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
        self.assertEqual(set(tabelas), {'faturas', 'faturas_excluidas', 'faturamento_mensal'})

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
        mensal = tabelas['faturamento_mensal'].filter("competencia = '2025-01-01'").first()
        self.assertEqual(mensal.volume_analise_kwh, Decimal('0.00'))
        self.assertEqual(mensal.valor_total, Decimal('216.00'))
        self.assertEqual(mensal.quantidade_sem_volume, 1)
        self.assertEqual(mensal.cobertura_volume_pct, Decimal('0.00'))

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
                mensal = tabelas['faturamento_mensal'].filter("competencia = '2025-01-01'").first()
                self.assertEqual(mensal.volume_analise_kwh, Decimal('0.00'))
                self.assertEqual(mensal.receita_sem_volume_positivo, Decimal('216.00'))

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
        resumos = {r.municipio: r for r in tabelas['faturamento_mensal'].collect()}
        self.assertEqual(resumos['Olinda'].valor_total, Decimal('216.00'))
        self.assertEqual(resumos['Recife'].valor_total, Decimal('120.00'))
        self.assertEqual(sum(r.valor_total for r in resumos.values()), Decimal('336.00'))
        validar_reconciliacao(faturas, tabelas)

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

    def test_inconsistencia_financeira_e_pagamento_bloqueiam(self):
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

    def test_exportacao_csv_preserva_centavos_nulos_e_hashes(self):
        faturas, _, _ = self.fontes()
        texto = '  Bairro "Centro", rua\\nova\nRecife  '
        cadastro = self.fontes()[1].withColumn('bairro', F.lit(texto))
        faturas = faturas.withColumn('source_file', F.lit('  pasta/faturas.csv  '))
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
        tabelas = self.construir(faturas=faturas, cadastro=cadastro)
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
                    self.assertEqual(aberta['bairro'], texto)
                    self.assertEqual(aberta['source_file'], '  pasta/faturas.csv  ')
            with self.assertRaises(FileExistsError):
                exportar_csv(tabelas, str(lote), {'batch_id': 'lote'})


if __name__ == '__main__':
    unittest.main()
