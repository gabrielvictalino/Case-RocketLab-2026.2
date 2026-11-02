"""R2/R3, precisão e intercâmbio comercial em fixtures, sem dados do workspace."""

import csv
import json
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'silver_to_gold'))
from gold_contrato_faturas import (  # noqa: E402
    COMERCIAIS,
    agregar_receita_contratual,
    construir_consumo_contratual,
    construir_saidas_contratuais,
    especificacoes,
    exportar_comerciais,
    validar_reconciliacao_contratual,
    validar_tabela_contratual,
)
from gold_faturas import (  # noqa: E402
    FLAGS_LEITURAS,
    conferir_arquivos_csv,
    construir_faturas,
    exportar_csv,
    persistir_quadros,
)
import test_gold_faturas  # noqa: E402


class ContratoGoldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_gold_faturas.GoldFaturasTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def contexto(self):
        gd = self.spark.createDataFrame(
            [('UC100001', date(2025, 1, 15))], 'id_uc string, data_conexao date'
        )
        inspecoes = self.spark.createDataFrame(
            [
                ('UC100001', date(2024, 3, 2), 'IRREGULARIDADE CONFIRMADA'),
                ('UC100001', date(2024, 2, 2), 'SEM IRREGULARIDADE'),
                ('UC100001', date(2024, 5, 2), 'IRREGULARIDADE CONFIRMADA'),
            ],
            'id_uc string, data date, resultado string',
        )
        return gd, inspecoes

    def test_medianas_temporais_preservam_original_e_proveniencia(self):
        _, cadastro, _ = test_gold_faturas.GoldFaturasTest.fontes(self)
        linhas = [
            ('UC100001', '2024-01', 100, False),
            ('UC100001', '2024-02', -500, True),
            ('UC100001', '2024-03', 300, False),
            ('UC100001', '2025-01', 40, False),
            ('UC100001', '2025-02', -999, True),
            # Outra UC sem doador na fase após conexão: usa histórico.
            ('UC100002', '2024-01', 800, False),
            ('UC100002', '2025-01', -8000, True),
        ]
        leituras = self.spark.createDataFrame(
            linhas,
            'id_uc string, mes_referencia string, consumo_kwh int, flag_troca_medidor boolean',
        )
        leituras = leituras.withColumn('tipo_leitura', F.lit('REAL'))
        for f in FLAGS_LEITURAS[1:]:
            leituras = leituras.withColumn(f, F.lit(False))
        cadastro = cadastro.unionByName(cadastro.withColumn('id_uc', F.lit('UC100002')))
        gd, inspecoes = self.contexto()
        gd = gd.unionByName(gd.withColumn('id_uc', F.lit('UC100002')))
        consumo = construir_consumo_contratual(leituras, cadastro, gd, inspecoes, '2026-10-22')
        rows = {(r.id_uc, r.mes_referencia): r for r in consumo.collect()}
        troca = rows['UC100001', '2025-02']
        self.assertEqual(troca.consumo_kwh_original, Decimal('-999.00'))
        self.assertEqual(troca.consumo_kwh_analitico, Decimal('40.00'))
        self.assertEqual(troca.metodo_consumo, 'MEDIANA_FASE_UC')
        self.assertEqual(troca.doadores_fase, 1)
        fallback = rows['UC100002', '2025-01']
        self.assertEqual(fallback.metodo_consumo, 'MEDIANA_HISTORICA_UC')
        self.assertEqual(fallback.consumo_kwh_analitico, Decimal('800.00'))
        self.assertEqual(rows['UC100001', '2024-02'].grupo_uc, 'DEMAIS')
        self.assertEqual(rows['UC100001', '2024-03'].grupo_uc, 'IRREGULARIDADE_CONFIRMADA')
        self.assertEqual(rows['UC100001', '2025-01'].grupo_uc, 'GD')
        for r in rows.values():
            if r.metodo_consumo == 'LEITURA_UTILIZAVEL':
                self.assertEqual(r.consumo_kwh_original, r.consumo_kwh_analitico)
        with self.assertRaisesRegex(ValueError, 'sem doadores'):
            construir_consumo_contratual(
                leituras.filter('flag_troca_medidor'), cadastro, gd, inspecoes, '2026-10-22'
            )

    def test_sem_fatura_multiplas_status_e_bloqueio_de_campos_sem_fonte(self):
        faturas, cadastro, leituras = test_gold_faturas.GoldFaturasTest.fontes(self)
        segunda = faturas.filter("id_fatura = 'FT2'").withColumn('id_fatura', F.lit('FT3'))
        faturas = faturas.unionByName(segunda)
        leituras = leituras.withColumn('tipo_leitura', F.lit('ESTIMADA'))
        gd, inspecoes = self.contexto()
        auxiliares = construir_faturas(faturas, cadastro, leituras, '2025-02-15')
        consumo = construir_consumo_contratual(leituras, cadastro, gd, inspecoes, '2025-02-15')
        complemento = self.spark.createDataFrame(
            [
                (
                    'FT1',
                    Decimal('100.00'),
                    Decimal('0.800001'),
                    Decimal('0.100001'),
                    'fixture:fonte-teste',
                )
            ],
            'id_fatura string, volume_faturado_kwh decimal(18,2), tarifa_base decimal(18,6), '
            'adicional_bandeira decimal(18,6), proveniencia string',
        )
        with persistir_quadros([consumo, *auxiliares.values()]):
            tabelas = construir_saidas_contratuais(consumo, auxiliares, cadastro, complemento)
            with persistir_quadros(list(tabelas.values())):
                validar_reconciliacao_contratual(tabelas, cadastro)
                detalhe = {r.competencia: r for r in tabelas[COMERCIAIS[0]].collect()}
                paga, sem = detalhe[date(2024, 1, 1)], detalhe[date(2025, 1, 1)]
                self.assertEqual(paga.valor_arrecadado, paga.valor_total)
                self.assertEqual(paga.status_pagamento, 'PAGA')
                self.assertEqual(paga.bandeira, 'VERDE')
                self.assertEqual(paga.data_vencimento, date(2024, 1, 28))
                self.assertEqual(sem.consumo_kwh_analitico, Decimal('150.00'))
                self.assertIsNone(sem.id_fatura)
                for c in [
                    'bandeira',
                    'status_pagamento',
                    'data_vencimento',
                    'tarifa_base',
                    'adicional_bandeira',
                ]:
                    self.assertIsNone(sem[c])
                for c in ['volume_faturado_kwh', 'valor_total', 'valor_arrecadado']:
                    self.assertEqual(sem[c], Decimal(0))
                self.assertEqual(auxiliares['faturas_excluidas'].count(), 3)
                with tempfile.TemporaryDirectory() as pasta:
                    lote = exportar_comerciais(
                        tabelas,
                        str(Path(pasta) / 'comercial'),
                        {'reference_date': '2025-02-15', 'synthetic': True},
                    )
                    self.assertFalse((lote / 'manifest.json').exists())
                    recibo = json.loads((lote / 'comercial.json').read_text())
                    self.assertEqual(recibo['contract_version'], '0.3.0-provisional')
                    for nome, spec in especificacoes().items():
                        with (lote / f'{nome}.csv').open(newline='') as f:
                            self.assertEqual(next(csv.reader(f)), list(spec['columns']))
                adulteradas = dict(tabelas)
                adulteradas[COMERCIAIS[1]] = tabelas[COMERCIAIS[1]].withColumn(
                    'receita', F.col('receita') + F.lit(Decimal('0.01'))
                )
                with self.assertRaisesRegex(ValueError, 'por grão'):
                    validar_reconciliacao_contratual(adulteradas, cadastro)
            with self.assertRaisesRegex(ValueError, 'consumo original obrigatório'):
                construir_saidas_contratuais(
                    consumo.filter("mes_referencia != '2025-01'"),
                    auxiliares,
                    cadastro,
                    complemento,
                )
            for c in ['volume_faturado_kwh', 'tarifa_base', 'adicional_bandeira']:
                with self.subTest(c=c), self.assertRaisesRegex(ValueError, 'ausente'):
                    construir_saidas_contratuais(
                        consumo,
                        auxiliares,
                        cadastro,
                        complemento.withColumn(c, F.lit(None).cast(complemento.schema[c].dataType)),
                    )

    def test_aberta_e_sem_fatura_real_preservam_consumo(self):
        faturas, cadastro, leituras = test_gold_faturas.GoldFaturasTest.fontes(self)
        leituras = leituras.unionByName(
            leituras.limit(1).withColumn('mes_referencia', F.lit('2024-04'))
        )
        leituras = leituras.withColumn('tipo_leitura', F.lit('REAL'))
        gd, inspecoes = self.contexto()
        aux = construir_faturas(faturas, cadastro, leituras, '2025-02-15')
        consumo = construir_consumo_contratual(leituras, cadastro, gd, inspecoes, '2025-02-15')
        comp = self.spark.createDataFrame(
            [
                ('FT1', Decimal('100.00'), Decimal('0.8'), Decimal('0'), 'fixture'),
                ('FT2', Decimal('150.00'), Decimal('0.9'), Decimal('0.1'), 'fixture'),
            ],
            'id_fatura string, volume_faturado_kwh decimal(18,2), tarifa_base decimal(18,6), '
            'adicional_bandeira decimal(18,6), proveniencia string',
        )
        with persistir_quadros([consumo, *aux.values()]):
            ts = construir_saidas_contratuais(consumo, aux, cadastro, comp)
            rows = {r.competencia: r for r in ts[COMERCIAIS[0]].collect()}
            self.assertEqual(rows[date(2025, 1, 1)].status_pagamento, 'ABERTA')
            self.assertEqual(rows[date(2025, 1, 1)].valor_arrecadado, Decimal(0))
            self.assertIsNone(rows[date(2024, 4, 1)].id_fatura)
            self.assertEqual(rows[date(2024, 4, 1)].consumo_kwh_original, Decimal('100'))

    def test_arredondamento_soma_produtos_e_escala_excedida_rejeitada(self):
        df = self.spark.createDataFrame(
            [
                (
                    'UC100001',
                    date(2025, 1, 1),
                    'DEMAIS',
                    Decimal('1.00'),
                    Decimal('1.00'),
                    Decimal('0.00'),
                    Decimal('0.004999'),
                    Decimal('0.000001'),
                ),
                (
                    'UC100002',
                    date(2025, 1, 1),
                    'DEMAIS',
                    Decimal('1.00'),
                    Decimal('1.00'),
                    Decimal('0.00'),
                    Decimal('0.004999'),
                    Decimal('0.000001'),
                ),
            ],
            'id_uc string, competencia date, grupo_uc string, volume_faturado_kwh decimal(18,2), '
            'valor_total decimal(18,2), valor_arrecadado decimal(18,2), tarifa_base decimal(18,6), '
            'adicional_bandeira decimal(18,6)',
        )
        cadastro = self.spark.createDataFrame(
            [(uc, 'Recife', 'Centro', 'Residencial') for uc in ['UC100001', 'UC100002']],
            'id_uc string, municipio string, bairro string, classe string',
        )
        agregado = agregar_receita_contratual(df, cadastro)
        self.assertEqual(agregado.first().componente_tarifa_reais, Decimal('0.01'))
        spec = especificacoes()[COMERCIAIS[1]]
        with self.assertRaisesRegex(ValueError, 'precisao'):
            validar_tabela_contratual(agregado.withColumn('receita', F.lit(Decimal('1.001'))), spec)

    def test_exportador_rejeita_orfas_e_alteracoes_com_mesmo_total(self):
        df = self.spark.createDataFrame(
            [(1, Decimal('1.01')), (2, Decimal('2.02'))], 'id int, valor_total decimal(18,2)'
        )
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            primeiro = pasta / 'part-1.csv'
            segundo = pasta / 'part-2.csv'
            primeiro.write_text('id,valor_total\n1,1.01\n2,2.02\n')
            conferir_arquivos_csv(df, [primeiro])
            segundo.write_bytes(primeiro.read_bytes())
            with self.assertRaisesRegex(ValueError, 'diverge'):
                conferir_arquivos_csv(df, [primeiro, segundo])
            primeiro.write_text('id,valor_total\n1,2.02\n2,1.01\n')
            with self.assertRaisesRegex(ValueError, 'diverge'):
                conferir_arquivos_csv(df, [primeiro])
            with patch('gold_faturas.conferir_arquivos_csv', side_effect=ValueError('diverge')):
                with self.assertRaisesRegex(ValueError, 'diverge'):
                    exportar_csv({'faturas': df}, str(pasta / 'lote'), {})
            self.assertFalse((pasta / 'lote' / 'manifest.json').exists())

    def test_notebook_validar_com_24_meses_sem_gravacao(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import MagicMock
        import gold_faturas

        faturas, cadastro, leituras = test_gold_faturas.GoldFaturasTest.fontes(self)
        fatura = faturas.filter("id_fatura = 'FT2'").first().asDict()
        leitura = leituras.first().asDict()
        registros_f, registros_l = [], []
        for i in range(24):
            mes = gold_faturas.deslocar_mes(date(2023, 1, 1), i)
            registros_f.append(
                {
                    **fatura,
                    'id_fatura': f'FT{i:09d}',
                    'mes_referencia': mes.strftime('%Y-%m'),
                    'data_emissao': mes.replace(day=20),
                    'data_vencimento': mes.replace(day=28),
                }
            )
            registros_l.append({**leitura, 'mes_referencia': mes.strftime('%Y-%m')})
        faturas = self.spark.createDataFrame(registros_f, faturas.schema)
        leituras = self.spark.createDataFrame(registros_l, leituras.schema)
        leituras = leituras.withColumn('tipo_leitura', F.lit('REAL'))
        gd, inspecoes = self.contexto()
        dbutils = MagicMock()
        widgets = {'data_referencia': '2025-02-15'}
        dbutils.widgets.text.side_effect = lambda n, v: widgets.setdefault(n, v)
        dbutils.widgets.get.side_effect = lambda n: widgets[n]
        ns = {n: getattr(gold_faturas, n) for n in dir(gold_faturas) if not n.startswith('__')}
        ns.update(spark=self.spark, dbutils=dbutils, display=lambda df: None)

        def ler(spark, nome, versao=None):
            df = {
                'v-energy.silver.tb_unidades_consumidoras': cadastro,
                'v-energy.silver.tb_leituras': leituras,
                'v-energy.silver.tb_geracao_distribuida': gd,
                'venergy.silver.inspecoes': inspecoes,
            }[nome]
            return df, {
                'tabela': gold_faturas.qualificar(nome),
                'id_delta': 'fixture',
                'versao_delta': 8,
            }

        ns['ler_snapshot_delta'] = ler
        ns['ler_publicacao_silver'] = lambda *a: (
            faturas,
            faturas.limit(0),
            {'snapshots': {}, 'id_execucao': 'fixture'},
        )
        ns['publicar_revisoes'] = MagicMock(side_effect=AssertionError('escrita indevida'))
        notebook = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / 'silver_to_gold'
                / 'silver-to-gold-faturas.ipynb'
            ).read_text()
        )
        saida = StringIO()
        with redirect_stdout(saida):
            for i in [2, 4, 6, 8]:
                exec(''.join(notebook['cells'][i]['source']), ns)
        self.assertIn('BLOQUEIO CONTRATUAL', saida.getvalue())
        self.assertIn('Nenhum schema, tabela ou CSV foi gravado', saida.getvalue())
        ns['publicar_revisoes'].assert_not_called()
        # Mesmo retrato, mesmo resultado em outro dia: o notebook não usa o relógio
        # para status/atraso. Sem complemento, publicar é recusado antes de gravar.
        ns['config']['modo'] = 'publicar'
        with self.assertRaisesRegex(ValueError, 'complemento homologado indisponível'):
            ns['executar_gold']()
        ns['publicar_revisoes'].assert_not_called()
