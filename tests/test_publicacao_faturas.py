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


def cell_id(marker):
    matches = [i for i, cell in enumerate(NB['cells'])
               if cell['cell_type'] == 'code'
               and ''.join(cell['source']).startswith(f'# faturas: {marker}\n')]
    if len(matches) != 1:
        raise ValueError(f'Marcador de célula ausente ou duplicado: {marker}')
    return matches[0]


def source(marker):
    cell = cell_id(marker)
    return ''.join(NB['cells'][cell]['source'])


def functions(marker, namespace):
    tree = ast.parse(source(marker))
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
        functions('contrato-destinos', env)
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
               'schema_silver': '`teste`.`silver`', 'schema_revisoes': '`teste`.`revisoes`'}
        for cell in ['criar-revisoes', 'conferir-revisoes', 'plano-e-retencao', 'publicar-destinos', 'conferir-destinos', 'confirmar-publicacao']:
            exec(source(cell), env)
        self.assertEqual(spark.mock_calls, [])
        self.assertFalse(env['PUBLICACAO_FATURAS_OK'])

    def test_contrato_ids_pendentes(self):
        import subprocess
        tree = ast.parse(source('contrato-candidata'))
        patterns = [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.startswith('^(?:FT')]
        self.assertEqual(len(patterns), 1)
        java = ROOT / 'tests/RegexFaturas.java'
        # Matcher.find reproduz rlike: não usar matches/fullmatch para mascarar $.
        cases = {'FT000000001': True, 'FTX0000001': True,
                 'FT12': False, 'FTX12': False, 'id_fatura': False,
                 ' FT000000001': False, 'FTX0000001 ': False,
                 'FTX0000001\n': False, 'FT000000001\r\n': False}
        results = subprocess.check_output(
            ['java', str(java), patterns[0], *cases], text=True).splitlines()
        self.assertEqual(results, [str(expected).lower() for expected in cases.values()])

    def test_retencao_preserva_atual_recente_e_outros_nomes(self):
        env = {}
        functions('plano-e-retencao', env)
        eligible = env['revisao_expirada']
        name = 'tb_faturas_revisao_' + 'a' * 32
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        self.assertTrue(eligible(name, now - timedelta(days=8), set(), cutoff))
        self.assertFalse(eligible(name, now - timedelta(days=8), {name}, cutoff))
        self.assertFalse(eligible(name, now, set(), cutoff))
        self.assertFalse(eligible('tb_faturas', now - timedelta(days=8), set(), cutoff))

    def test_retencao_publicacoes_seguidas_e_reinicio(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        now = datetime.now(timezone.utc)
        old = 'tb_faturas_revisao_' + 'a' * 32
        new = 'tb_faturas_revisao_' + 'b' * 32
        pending = 'tb_faturas_pendentes_cadastro_revisao_' + 'c' * 32
        newest = 'tb_faturas_revisao_' + 'd' * 32
        names = [old, new, pending, newest]
        ledger = {}
        current = [new, pending]
        removed = []
        spark = MagicMock()
        spark.catalog.tableExists.return_value = True
        def table(name):
            rows = ([dict(id_execucao='atual', destino=d, fonte=n)
                     for d, n in zip(['a', 'b'], current)] if name == 'marker'
                    else [dict(nome=n, aposentada_em=t) for n, t in ledger.items()])
            return SimpleNamespace(collect=lambda: rows)
        def sql(query):
            if 'SHOW TABLES' in query:
                return SimpleNamespace(collect=lambda: [dict(tableName=n) for n in names])
            if 'DROP TABLE' in query:
                removed.append(query.split('`')[-2])
            return MagicMock()
        spark.table.side_effect = table
        spark.sql.side_effect = sql
        spark.createDataFrame.side_effect = lambda rows, schema: SimpleNamespace(alias=lambda _: rows)
        delta = MagicMock()
        class Merge:
            def alias(self, _): return self
            def merge(self, rows, _):
                self.rows = rows
                return self
            def whenNotMatchedInsertAll(self): return self
            def execute(self):
                for name, timestamp in self.rows:
                    ledger.setdefault(name, timestamp)
        delta.DeltaTable.forName.side_effect = lambda *_: Merge()
        env = {'spark': spark, 'TABELA_MARCADOR': 'marker', 'TABELA_RETENCAO': 'ledger',
               'schema_revisoes': '`test`.`revisoes`', 'RETENCAO_REVISOES_DIAS': 7,
               'esperados_por_destino': {'a': 1, 'b': 2}}
        functions('plano-e-retencao', env)
        with patch.dict(sys.modules, {'delta': SimpleNamespace(), 'delta.tables': delta}):
            # A revisão anterior pode ter 30 dias: createdAt nunca é consultado.
            env['limpar_revisoes_expiradas']()
            first_retired = ledger[old]
            self.assertGreaterEqual(first_retired, now)
            self.assertEqual(removed, [])
            current[:] = [newest, pending]
            # Nova sessão usa o ledger persistido; nova publicação não reinicia nem encurta janela.
            definitions = {node.name for node in ast.parse(source('plano-e-retencao')).body
                           if isinstance(node, ast.FunctionDef)}
            env = {key: value for key, value in env.items() if key not in definitions}
            functions('plano-e-retencao', env)
            env['limpar_revisoes_expiradas']()
            self.assertEqual(ledger[old], first_retired)
            self.assertEqual(removed, [])
            ledger[old] = now - timedelta(days=8)
            ledger[pending] = now - timedelta(days=30)
            env['limpar_revisoes_expiradas']()
            self.assertEqual(removed, [old])
            self.assertNotIn(new, removed)
            self.assertNotIn(pending, removed)
        self.assertFalse(any('createdAt' in str(c) or 'DESCRIBE DETAIL' in str(c)
                             for c in spark.sql.call_args_list))

    def test_destino_ausente_preserva_marcador(self):
        env = {'spark': MagicMock(), 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}, 'id_execucao_revisao': 'execucao',
               'validar_fontes_conferidas': lambda _: None,
               'obter_estado_delta': lambda _: None}
        functions('plano-e-retencao', env)
        with self.assertRaisesRegex(ValueError, 'Destino mudou'):
            env['confirmar_publicacao_conferida'](
                [dict(destino=d, fonte=d+'_rev', versao_fonte=0) for d in ['a', 'b']],
                {d: {'versao': 3} for d in ['a', 'b']})
        env['spark'].createDataFrame.assert_not_called()

    def test_markdown_novo_nao_desalinha_testes(self):
        NB['cells'].insert(0, {'cell_type': 'markdown', 'source': ['Introdução']})
        try:
            self.assertIn('def comparar_schemas', source('contrato-destinos'))
            self.assertIn('def limpar_revisoes_expiradas', source('plano-e-retencao'))
        finally:
            NB['cells'].pop(0)

    def test_marcador_recusa_par_incompleto(self):
        spark = MagicMock()
        env = {'spark': spark, 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}}
        functions('plano-e-retencao', env)
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
        functions('plano-e-retencao', env)
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
            exec(source('publicar-destinos'), env)
        env['confirmar_publicacao_conferida'].assert_not_called()
        self.assertFalse(env['PUBLICACAO_FATURAS_OK'])
        self.assertEqual(set(env['publicacoes_realizadas']), {'a'})
        env.update(VALIDACOES_CANDIDATA_OK=True, esperados_por_destino={'a': 1, 'b': 2})
        with self.assertRaisesRegex(ValueError, 'Falta validar'):
            exec(source('confirmar-publicacao'), env)
        env['confirmar_publicacao_conferida'].assert_not_called()
        spark.createDataFrame.assert_not_called()

    def test_destino_alterado_preserva_marcador(self):
        env = {'spark': MagicMock(), 'esperados_por_destino': {'a': 1, 'b': 2},
               'destinos_validados': {'a', 'b'}, 'id_execucao_revisao': 'execucao',
               'validar_fontes_conferidas': lambda _: None,
               'obter_estado_delta': lambda _: {'versao': 4}}
        functions('plano-e-retencao', env)
        with self.assertRaises(ValueError):
            env['confirmar_publicacao_conferida'](
                [dict(destino=d, fonte=d+'_rev', versao_fonte=0) for d in ['a', 'b']],
                {d: {'versao': 3} for d in ['a', 'b']})
        env['spark'].createDataFrame.assert_not_called()


if __name__ == '__main__':
    unittest.main()
