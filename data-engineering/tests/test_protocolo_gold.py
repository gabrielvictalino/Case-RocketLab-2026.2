"""Contrato de leitura e confirmação sob republicação/interrupções simuladas."""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'silver_to_gold'))
import gold_faturas as gold  # noqa: E402


class ProtocoloGoldTest(unittest.TestCase):
    def marcador(self):
        ident = 'a' * 32
        return [
            dict(
                id_execucao=ident,
                destino=f'`v-energy`.`silver`.`{nome}`',
                fonte=f'`v-energy`.`silver_revisoes`.`{nome}_revisao_{ident}`',
                versao_fonte=versao,
                versao_destino=9,
                confirmado_em=datetime(2026, 10, 22),
            )
            for nome, versao in [('tb_faturas', 3), ('tb_faturas_pendentes_cadastro', 7)]
        ]

    def test_marcador_lido_uma_vez_e_versoes_nao_zero(self):
        linhas = self.marcador()
        spark = MagicMock()
        spark.table.return_value.collect.side_effect = [linhas, self.marcador()[::-1]]
        spark.sql.return_value.first.return_value = {'format': 'delta', 'id': 'delta-id'}
        gold.ler_publicacao_silver(
            spark,
            'v-energy.silver.tb_faturas_publicacao',
            'V-ENERGY.SILVER.TB_FATURAS',
            'v-energy.silver.tb_faturas_pendentes_cadastro',
        )
        spark.table.return_value.collect.assert_called_once()
        self.assertEqual(
            [c.args for c in spark.read.option.call_args_list],
            [('versionAsOf', 3), ('versionAsOf', 7)],
        )
        self.assertEqual(
            [c.args[0] for c in spark.read.option.return_value.table.call_args_list],
            [r['fonte'] for r in linhas],
        )
        # Republicação do marcador não interfere nos snapshots já selecionados.
        self.assertFalse(any('HISTORY' in c.args[0] for c in spark.sql.call_args_list))

    def test_marcadores_invalidos_bloqueiam_sem_ler_finais(self):
        for caso in ('ausente', 'incompleto', 'id', 'destino', 'fonte', 'versao', 'data'):
            linhas = self.marcador()
            if caso == 'ausente':
                linhas = []
            elif caso == 'incompleto':
                linhas.pop()
            else:
                campo, valor = {
                    'id': ('id_execucao', 'b' * 32),
                    'destino': ('destino', linhas[0]['destino']),
                    'fonte': ('fonte', 'v-energy.silver.tb_faturas'),
                    'versao': ('versao_fonte', -1),
                    'data': ('confirmado_em', None),
                }[caso]
                linhas[1][campo] = valor
            spark = MagicMock()
            spark.table.return_value.collect.return_value = linhas
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                gold.ler_publicacao_silver(
                    spark,
                    'v-energy.silver.tb_faturas_publicacao',
                    'v-energy.silver.tb_faturas',
                    'v-energy.silver.tb_faturas_pendentes_cadastro',
                )
            spark.read.option.assert_not_called()

    def test_identificadores_equivalentes_e_schemas_proibidos(self):
        for schema in [
            'v-energy.Silver',
            'V-ENERGY.BRONZE',
            'v-energy.Default',
            'v-energy.SILVER_REVISOES',
        ]:
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                gold.validar_destinos(schema, [], [])
        with self.assertRaisesRegex(ValueError, 'coincide'):
            gold.validar_destinos(
                'v-energy.gold', ['V-ENERGY.GOLD.TB_A'], ['`v-energy`.`gold`.`tb_a`']
            )
        for nome in ['x;DROP TABLE a', 'a.b.c.d', 'a.b. c']:
            with self.assertRaises(ValueError):
                gold.qualificar(nome)

    def test_revisoes_exclusivas_e_marcador_por_ultimo(self):
        spark = MagicMock()
        spark.catalog.tableExists.return_value = False
        tabelas = {'faturas': MagicMock(), 'mensal': MagicMock()}
        ordem = []

        def publicar(_spark, recebidas, destinos, validar):
            ordem.append('revisoes')
            self.assertTrue(all('_revisao_' in t for t in destinos.values()))
            validar(recebidas)
            return recebidas, {n: {'tabela': d, 'versao_delta': 4} for n, d in destinos.items()}

        def confirmar():
            ordem.append('pre_confirmacao')

        spark.createDataFrame.side_effect = lambda *a: ordem.append('marcador') or MagicMock()
        with patch.object(gold, 'publicar_delta', side_effect=publicar):
            gold.publicar_revisoes(
                spark,
                tabelas,
                'v-energy.gold',
                lambda t: ordem.append('validar'),
                {'reference_date': '2026-10-22'},
                confirmar,
            )
        self.assertEqual(ordem, ['revisoes', 'validar', 'pre_confirmacao', 'marcador'])

    def test_interrupcoes_nao_confirmam_conjunto_incompleto(self):
        # Uma morte entre as escritas e outra antes do marcador. Nenhum finally
        # precisa executar para que o marcador anterior continue sendo a publicação.
        for ponto in ('entre_escritas', 'antes_marcador'):
            spark = MagicMock()
            spark.catalog.tableExists.return_value = False
            persistidas = {'faturas': MagicMock()}
            versoes = {'faturas': {'tabela': 'v-energy.gold.revisao', 'versao_delta': 2}}
            pub = MagicMock(return_value=(persistidas, versoes))
            antes = MagicMock()
            if ponto == 'entre_escritas':
                pub.side_effect = SystemExit('processo interrompido')
            else:
                antes.side_effect = SystemExit('processo interrompido')
            with self.subTest(ponto=ponto), patch.object(gold, 'publicar_delta', pub):
                with self.assertRaises(SystemExit):
                    gold.publicar_revisoes(
                        spark, persistidas, 'v-energy.gold', MagicMock(), {}, antes
                    )
            spark.createDataFrame.assert_not_called()
            # Recuperação no próximo processo: consumidor obtém só o conjunto anterior.
            ident = 'c' * 32
            linha = dict(
                id_execucao=ident,
                nome='faturas',
                versao_fonte=6,
                metadados='{}',
                fonte=f'v-energy.gold.tb_gold_faturas_faturas_revisao_{ident}',
            )
            spark.table.return_value.collect.return_value = [linha]
            with patch.object(gold, 'ler_snapshot_delta', return_value=('publicada', {})):
                quadros, _ = gold.ler_publicacao_gold(spark, 'v-energy.gold', ['faturas'])
            self.assertEqual(quadros, {'faturas': 'publicada'})

    def test_snapshot_fixa_versao_antes_de_republicacao_sem_cache(self):
        spark = MagicMock()
        spark.sql.return_value.first.side_effect = [
            {'format': 'delta', 'id': 'fonte-id'},
            {'version': 12},
        ]
        df, meta = gold.ler_snapshot_delta(spark, 'v-energy.silver.tb_leituras')
        spark.read.option.assert_called_once_with('versionAsOf', 12)
        self.assertEqual(meta['versao_delta'], 12)
        self.assertEqual(meta['id_delta'], 'fonte-id')
        df.persist.assert_not_called()
        df.cache.assert_not_called()

    def test_data_referencia_e_deslocamento_mensal(self):
        from datetime import date

        for valor in ['', None, '20260101', '2026-02-30', '2026-1-01']:
            with self.subTest(valor=valor), self.assertRaisesRegex(ValueError, 'AAAA-MM-DD'):
                gold.validar_data_referencia(valor)
        self.assertEqual(gold.deslocar_mes(date(2026, 1, 1), -1), date(2025, 12, 1))
        self.assertEqual(gold.deslocar_mes(date(2026, 1, 1), 12), date(2027, 1, 1))

    def test_morte_apos_primeira_escrita_preserva_marcador_e_recupera_na_proxima_execucao(self):
        spark = MagicMock()
        estado = {}
        spark.catalog.tableExists.side_effect = lambda t: t in estado
        spark.sql.side_effect = lambda c: MagicMock(first=lambda: {'version': 3})
        quadros = {n: MagicMock(schema=[]) for n in ['faturas', 'mensal']}
        escritos = []
        for nome, df in quadros.items():
            df.exceptAll.return_value.limit.return_value.count.return_value = 0

            def gravar(tabela, nome=nome, df=df):
                estado[tabela] = df
                escritos.append(tabela)
                if nome == 'mensal':
                    raise SystemExit('morte sem compensação')

            writer = df.write.format.return_value.mode.return_value.option.return_value
            writer.saveAsTable.side_effect = gravar
        spark.read.option.return_value.table.side_effect = lambda t: estado[t]
        with self.assertRaises(SystemExit):
            gold.publicar_revisoes(spark, quadros, 'v-energy.gold', MagicMock(), {})
        self.assertEqual(len(escritos), 2)
        self.assertEqual(len(estado), 2)  # Sobrevivem; manutenção poderá identificá-las.
        spark.createDataFrame.assert_not_called()
        self.assertTrue(all('_revisao_' in t for t in estado))
        # Novo processo não lê estado em memória do anterior: usa o marcador persistido.
        ident = 'b' * 32
        linhas = [
            dict(
                id_execucao=ident,
                nome=n,
                versao_fonte=8,
                metadados='{}',
                fonte=f'v-energy.gold.tb_gold_faturas_{n}_revisao_{ident}',
            )
            for n in quadros
        ]
        spark.table.return_value.collect.return_value = linhas
        with patch.object(gold, 'ler_snapshot_delta', side_effect=lambda s, t, v: (t, {})):
            publicadas, _ = gold.ler_publicacao_gold(spark, 'v-energy.gold', list(quadros))
        self.assertTrue(all('_' + ident in t for t in publicadas.values()))
        self.assertFalse(set(publicadas.values()) & set(escritos))

    def test_limpeza_protege_marcador_e_janela_de_aposentadoria(self):
        from datetime import timedelta
        from types import ModuleType

        agora = datetime.now()
        schema = '`V-Energy`.`GOLD`'
        nomes = ['faturas', 'mensal']
        antiga = 'tb_gold_faturas_faturas_revisao_' + 'a' * 32
        recente = 'tb_gold_faturas_mensal_revisao_' + 'b' * 32
        protegida = 'tb_gold_faturas_faturas_revisao_' + 'c' * 32
        tabelas = [antiga, recente, protegida, 'tb_de_outro_dominio']
        registros = [
            dict(nome=f'{schema}.`{n}`', aposentada_em=agora - timedelta(days=d))
            for n, d in [(antiga, 8), (recente, 1), (protegida, 100)]
        ]
        # Entradas antigas com/sem aspas e caixa diferente são a mesma revisão.
        registros.append({**registros[0], 'nome': f'v-energy.gold.{antiga}'})
        spark = MagicMock()
        spark.sql.return_value.collect.return_value = [dict(tableName=n) for n in tabelas]
        spark.table.return_value.collect.return_value = registros
        delta = ModuleType('delta.tables')
        delta.DeltaTable = MagicMock()
        with (
            patch.object(
                gold,
                'ler_publicacao_gold',
                return_value=({}, [dict(fonte=f'{schema}.`{protegida}`')]),
            ),
            patch.dict(sys.modules, {'delta.tables': delta}),
        ):
            gold.limpar_revisoes_gold(spark, 'v-energy.gold', nomes)
        drops = [c.args[0] for c in spark.sql.call_args_list if c.args[0].startswith('DROP')]
        self.assertEqual(drops, [f'DROP TABLE `v-energy`.`gold`.`{antiga}`'])
        # MERGE só insere: publicações próximas/reinício não renovam o prazo.
        merge = delta.DeltaTable.forName.return_value.alias.return_value.merge.return_value
        merge.whenNotMatchedInsertAll.assert_called_once()
        merge.whenMatchedUpdateAll.assert_not_called()

    def test_republicacao_com_migracao_nao_perde_fatura(self):
        anteriores = self.marcador()
        nova = [
            {**r, 'id_execucao': 'b' * 32, 'fonte': r['fonte'].replace('a' * 32, 'b' * 32)}
            for r in anteriores
        ]
        atual = [anteriores]
        spark = MagicMock()
        spark.table.return_value.collect.side_effect = lambda: list(atual[0])
        spark.sql.return_value.first.return_value = {'format': 'delta', 'id': 'id-revisao'}
        leituras = []

        def ler(tabela):
            leituras.append(tabela)
            atual[0] = nova  # Silver confirma entre as duas leituras da Gold.
            # FT1 migra de pendente antiga para principal nova. Misturar gera perda.
            return ['FT1'] if 'pendentes' in tabela else []

        spark.read.option.return_value.table.side_effect = ler
        principal, pendentes, meta = gold.ler_publicacao_silver(
            spark,
            'v-energy.silver.tb_faturas_publicacao',
            'v-energy.silver.tb_faturas',
            'v-energy.silver.tb_faturas_pendentes_cadastro',
        )
        self.assertEqual(principal + pendentes, ['FT1'])
        self.assertEqual(meta['id_execucao'], 'a' * 32)
        self.assertTrue(all('a' * 32 in t for t in leituras))
        self.assertEqual(atual[0][0]['id_execucao'], 'b' * 32)

    def test_erro_ao_confirmar_nao_remove_revisoes_potencialmente_confirmadas(self):
        spark = MagicMock()
        spark.catalog.tableExists.return_value = False
        salvar = spark.createDataFrame.return_value.write.format.return_value.mode.return_value
        salvar.saveAsTable.side_effect = RuntimeError('resposta perdida após commit')
        quadros = {'faturas': MagicMock()}
        versoes = {'faturas': {'tabela': 'v-energy.gold.revisao', 'versao_delta': 3}}
        with patch.object(gold, 'publicar_delta', return_value=(quadros, versoes)):
            with self.assertRaisesRegex(RuntimeError, 'resposta perdida'):
                gold.publicar_revisoes(spark, quadros, 'v-energy.gold', MagicMock(), {})
        self.assertFalse(
            any(c.args[0].startswith(('DROP', 'RESTORE')) for c in spark.sql.call_args_list)
        )
