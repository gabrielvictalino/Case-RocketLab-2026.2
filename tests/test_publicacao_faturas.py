"""Proteções do notebook, sem dependência de Spark/Databricks."""
import ast
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT / 'data-engineering/bronze-to-silver-faturas.ipynb').read_text())


def source(cell):
    return ''.join(NB['cells'][cell]['source'])


def functions(cell, namespace):
    tree = ast.parse(source(cell))
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name not in namespace]
    exec(compile(tree, '<notebook-functions>', 'exec'), namespace)


class PublicacaoFaturasTests(unittest.TestCase):
    def test_operacionais_sem_confirmacao_salva(self):
        for path in (ROOT / 'data-engineering').rglob('*.ipynb'):
            nb = json.loads(path.read_text())
            meta = nb.get('metadata', {}).get('application/vnd.databricks.v1+notebook', {})
            widget = meta.get('widgets', {}).get('confirmar_publicacao')
            if widget:
                self.assertEqual(widget['currentValue'], 'false', str(path))
                self.assertEqual(widget['widgetInfo']['defaultValue'], 'false', str(path))
        for cell in NB['cells']:
            if cell['cell_type'] == 'code':
                self.assertEqual(cell['outputs'], [])
                compile(''.join(cell['source']), '<cell>', 'exec')

    def test_evidencias_estaticas_preservam_exports_originais(self):
        import hashlib
        import html
        hashes = {
            'faturas-2026-10-29/publicacao.html': 'abb10db73e3c4e956f51d408fc2eb043f93c3f321c5940a14d9886ee966a4dee',
        }
        for relative, expected in hashes.items():
            page = (ROOT / 'docs/auditoria_dados/evidencias' / relative).read_text()
            raw = html.unescape(re.search(r'<pre>(.*)</pre>', page, re.S).group(1))
            self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), expected)
            self.assertNotIn('<script', page.lower())

    def test_schema_divergente_bloqueia(self):
        env = {'display': MagicMock(), 'spark': MagicMock()}
        functions(82, env)
        def frame(name, kind):
            field = MagicMock()
            field.name = name
            field.dataType.simpleString.return_value = kind
            df = MagicMock()
            df.schema.fields = [field]
            return df
        compare = env['comparar_schemas']
        for candidate in [frame('renomeada', 'string'), frame('id', 'long')]:
            with self.assertRaises(ValueError):
                compare(frame('id', 'string'), candidate)
        compare(frame('id', 'string'), frame('id', 'string'))

    def test_false_nao_grava_nem_limpa(self):
        spark = MagicMock()
        env = {'spark': spark, 'publicacao_autorizada': lambda: False,
               'VALIDACOES_CANDIDATA_OK': True, 'CONTRATO_DESTINOS_OK': True,
               'schema_silver': '`teste`.`silver`'}
        for cell in [85, 86, 88, 89, 90, 91]:
            exec(source(cell), env)
        self.assertEqual(spark.mock_calls, [])
        self.assertFalse(env['PUBLICACAO_FATURAS_OK'])

    def test_contrato_ids_pendentes(self):
        # A expressão é extraída da regra real, não uma cópia do padrão.
        tree = ast.parse(source(71))
        patterns = [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.startswith('^(?:FT')]
        self.assertEqual(len(patterns), 1)
        for value in ['FT000000001', 'FTX0000001']:
            self.assertIsNotNone(re.fullmatch(patterns[0], value))
        for value in ['FT12', 'FTX12', 'id_fatura', ' FT000000001', 'FTX0000001 ']:
            self.assertIsNone(re.fullmatch(patterns[0], value))

    def test_retencao_preserva_atual_recente_e_outros_nomes(self):
        env = {}
        functions(88, env)
        eligible = env['revisao_expirada']
        name = 'tb_faturas_revisao_' + 'a' * 32
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        self.assertTrue(eligible(name, now - timedelta(days=8), set(), cutoff))
        self.assertFalse(eligible(name, now - timedelta(days=8), {name}, cutoff))
        self.assertFalse(eligible(name, now, set(), cutoff))
        self.assertFalse(eligible('tb_faturas', now - timedelta(days=8), set(), cutoff))

    def test_marcador_recusa_par_incompleto(self):
        spark = MagicMock()
        env = {'spark': spark, 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}}
        functions(88, env)
        with self.assertRaises(ValueError):
            env['confirmar_publicacao_conferida']([{'destino': 'a'}], {'a': {}})
        self.assertEqual(spark.mock_calls, [])

    def test_marcador_so_grava_par_conferido(self):
        spark = MagicMock()
        env = {'spark': spark, 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}, 'id_execucao_revisao': 'execucao',
               'validar_fontes_conferidas': MagicMock(),
               'obter_estado_delta': lambda _: {'versao': 3},
               'TABELA_MARCADOR': 'marcador'}
        functions(88, env)
        plan = [{'destino': name, 'fonte': name + '_rev', 'versao_fonte': 0}
                for name in ['a', 'b']]
        published = {name: {'versao': 3} for name in ['a', 'b']}
        env['confirmar_publicacao_conferida'](plan, published)
        rows = spark.createDataFrame.call_args.args[0]
        self.assertEqual({row[1] for row in rows}, {'a', 'b'})
        self.assertEqual({row[2] for row in rows}, {'a_rev', 'b_rev'})
        spark.createDataFrame.return_value.write.format.return_value.mode.return_value.saveAsTable.assert_called_once_with('marcador')

    def test_falha_segunda_escrita_nao_confirma_marcador(self):
        spark = MagicMock()
        spark.sql.side_effect = [None, MagicMock(), RuntimeError('segunda escrita falhou')]
        env = {'spark': spark, 'publicacao_autorizada': lambda: True,
               'validar_fontes_conferidas': lambda _: None,
               'obter_estado_delta': lambda _: None,
               'plano_publicacao': [dict(destino=d, fonte=d+'_rev', versao_fonte=0,
                                        referencia=MagicMock(), estado_anterior=None)
                                    for d in ['a', 'b']],
               'confirmar_publicacao_conferida': MagicMock()}
        with self.assertRaisesRegex(RuntimeError, 'segunda escrita'):
            exec(source(89), env)
        env['confirmar_publicacao_conferida'].assert_not_called()
        self.assertFalse(env['PUBLICACAO_FATURAS_OK'])
        self.assertEqual(set(env['publicacoes_realizadas']), {'a'})

    def test_destino_alterado_preserva_marcador(self):
        env = {'spark': MagicMock(), 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}, 'id_execucao_revisao': 'execucao',
               'validar_fontes_conferidas': lambda _: None,
               'obter_estado_delta': lambda _: {'versao': 4}}
        functions(88, env)
        with self.assertRaises(ValueError):
            env['confirmar_publicacao_conferida'](
                [dict(destino=d, fonte=d+'_rev', versao_fonte=0) for d in ['a', 'b']],
                {d: {'versao': 3} for d in ['a', 'b']})
        env['spark'].createDataFrame.assert_not_called()


if __name__ == '__main__':
    unittest.main()
