"""Falhas da publicação com catálogo simulado, sem alegar transação Databricks."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'silver_to_gold'))
from gold_faturas import publicar_delta  # noqa: E402


class PublicacaoDeltaTest(unittest.TestCase):
    def ambiente(self, existentes=True, falha_escrita=None, falha_restore=None):
        spark = MagicMock()
        nomes = ['faturas', 'excluidas', 'mensal', 'variacao']
        destinos = {n: f'`catalogo`.`gold`.`tb_{n}`' for n in nomes}
        estado = {d: 7 for d in destinos.values()} if existentes else {}
        comandos = []
        spark.catalog.tableExists.side_effect = lambda d: d in estado

        def sql(comando):
            comandos.append(comando)
            palavras = comando.split()
            if comando.startswith('DESCRIBE DETAIL'):
                return MagicMock(first=lambda: {'format': 'delta'})
            if comando.startswith('DESCRIBE HISTORY'):
                return MagicMock(first=lambda: {'version': estado[palavras[2]]})
            destino = palavras[2] if palavras[0] == 'RESTORE' else palavras[-1]
            if comando.startswith('RESTORE'):
                if destino == falha_restore:
                    raise RuntimeError('restore indisponível')
                estado[destino] = int(palavras[-1])
            else:
                estado.pop(destino, None)

        spark.sql.side_effect = sql
        tabelas = {n: MagicMock(schema=[]) for n in nomes}
        for nome, df in tabelas.items():
            destino = destinos[nome]

            def gravar(d, destino=destino):
                self.assertEqual(d, destino)
                estado[d] = estado.get(d, -1) + 1
                if d == falha_escrita:
                    raise RuntimeError('falha após commit')

            writer = df.write.format.return_value.mode.return_value.option.return_value
            writer.saveAsTable.side_effect = gravar
            df.exceptAll.return_value.limit.return_value.count.return_value = 0
        spark.read.option.return_value.table.side_effect = lambda d: tabelas[
            next(n for n, destino in destinos.items() if destino == d)
        ]
        return spark, tabelas, destinos, estado, comandos

    def test_sucesso_confere_todas_e_registra_versoes(self):
        spark, tabelas, destinos, estado, comandos = self.ambiente()
        validar = MagicMock()
        persistidas, versoes = publicar_delta(spark, tabelas, destinos, validar)
        validar.assert_called_once_with(persistidas)
        self.assertEqual(set(persistidas), set(tabelas))
        self.assertTrue(all(v['versao_delta'] == 8 for v in versoes.values()))
        self.assertFalse(any(c.startswith('RESTORE') for c in comandos))

    def test_falha_de_escrita_recupera_inclusive_tabela_que_falhou(self):
        destino = '`catalogo`.`gold`.`tb_mensal`'
        for existentes in [True, False]:
            with self.subTest(existentes=existentes):
                spark, tabelas, destinos, estado, comandos = self.ambiente(
                    existentes, falha_escrita=destino
                )
                original = dict(estado)
                with self.assertRaisesRegex(RuntimeError, 'falha após commit'):
                    publicar_delta(spark, tabelas, destinos, MagicMock())
                self.assertEqual(estado, original)
                recuperacoes = [c for c in comandos if c.startswith(('RESTORE', 'DROP'))]
                self.assertEqual(len(recuperacoes), 3)

    def test_falha_de_conferencia_final_recupera_as_quatro(self):
        spark, tabelas, destinos, estado, comandos = self.ambiente()
        original = dict(estado)
        with self.assertRaisesRegex(ValueError, 'reconciliação'):
            publicar_delta(
                spark, tabelas, destinos, MagicMock(side_effect=ValueError('reconciliação'))
            )
        self.assertEqual(estado, original)
        self.assertEqual(sum(c.startswith('RESTORE') for c in comandos), 4)

    def test_recuperacao_falha_mas_tenta_demais_destinos(self):
        spark, tabelas, destinos, estado, comandos = self.ambiente(
            falha_restore='`catalogo`.`gold`.`tb_mensal`'
        )
        with self.assertRaises(ExceptionGroup) as captura:
            publicar_delta(
                spark, tabelas, destinos, MagicMock(side_effect=ValueError('reconciliação'))
            )
        self.assertEqual(len(captura.exception.exceptions), 2)
        self.assertEqual(sum(c.startswith('RESTORE') for c in comandos), 4)
        self.assertEqual(estado[destinos['faturas']], 7)

    def test_falha_de_snapshot_impede_qualquer_escrita(self):
        spark, tabelas, destinos, _, _ = self.ambiente()
        spark.sql.side_effect = RuntimeError('sem permissão de histórico')
        with self.assertRaisesRegex(RuntimeError, 'sem permissão'):
            publicar_delta(spark, tabelas, destinos, MagicMock())
        for df in tabelas.values():
            df.write.format.assert_not_called()

    def test_schema_ou_conteudo_divergente_recupera_destino(self):
        for erro in ['schema', 'conteudo']:
            with self.subTest(erro=erro):
                spark, tabelas, destinos, estado, _ = self.ambiente()
                original = dict(estado)
                persistido = MagicMock(schema=[])
                if erro == 'schema':
                    persistido.schema = [MagicMock()]
                else:
                    diferentes = tabelas['faturas'].exceptAll.return_value.limit.return_value
                    diferentes.count.return_value = 1
                spark.read.option.return_value.table.side_effect = None
                spark.read.option.return_value.table.return_value = persistido
                with self.assertRaisesRegex(ValueError, 'persistido divergente'):
                    publicar_delta(spark, tabelas, destinos, MagicMock())
                self.assertEqual(estado, original)
