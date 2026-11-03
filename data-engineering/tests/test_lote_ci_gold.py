"""Lote contratual completo e comportamento real do detector/agregador CI."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data-engineering' / 'silver_to_gold'))
from montar_lote_gold import montar_lote  # noqa: E402
from importador.contracts import ContractError, manifest_for  # noqa: E402


class LoteGoldTest(unittest.TestCase):
    def plano(self):
        pasta = ROOT / 'contracts' / 'samples'
        manifesto = json.loads((pasta / 'manifest.json').read_text())
        return {
            **{c: manifesto[c] for c in ['batch_id', 'period', 'reference_date', 'synthetic']},
            'tables': {
                n: {
                    'file': str(pasta / t['file']),
                    'sha256': t['sha256'],
                    **{c: manifesto[c] for c in ['period', 'reference_date', 'synthetic']},
                }
                for n, t in manifesto['tables'].items()
            },
        }

    def test_lote_completo_reutiliza_manifesto_03(self):
        with tempfile.TemporaryDirectory() as tmp:
            lote = montar_lote(self.plano(), Path(tmp) / 'completo')
            manifest = manifest_for(lote)
            self.assertTrue(manifest['synthetic'])
            self.assertEqual(manifest['contract_version'], '0.3.0-provisional')
            self.assertEqual(len(manifest['tables']), 12)
            self.assertEqual(manifest['reference_date'], self.plano()['reference_date'])
            for n, t in manifest['tables'].items():
                self.assertEqual(t['sha256'], self.plano()['tables'][n]['sha256'])

    def test_lotes_incompletos_mistos_e_corrompidos_nao_publicam_manifesto(self):
        for caso in ['incompleto', 'misto', 'hash', 'reference_date', 'escala', 'pk']:
            with tempfile.TemporaryDirectory() as tmp:
                plano = copy.deepcopy(self.plano())
                nome = 'receita_volume_mensal'
                entrada = plano['tables'][nome]
                if caso == 'incompleto':
                    del plano['tables']['gd_uc']
                elif caso == 'misto':
                    entrada['synthetic'] = False
                elif caso == 'hash':
                    entrada['sha256'] = '0' * 64
                elif caso == 'reference_date':
                    plano['reference_date'] = '2020-01-01'
                    for e in plano['tables'].values():
                        e['reference_date'] = plano['reference_date']
                else:
                    original = Path(entrada['file']).read_text().splitlines()
                    if caso == 'escala':
                        valores = original[1].split(',')
                        valores[6] = '1.001'
                        original[1] = ','.join(valores)
                    else:
                        original.append(original[1])
                    arquivo = Path(tmp) / 'alterado.csv'
                    arquivo.write_text('\n'.join(original) + '\n')
                    entrada['file'] = str(arquivo)
                    entrada['sha256'] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
                destino = Path(tmp) / 'lote'
                with self.subTest(caso=caso), self.assertRaises(ContractError):
                    montar_lote(plano, destino)
                self.assertFalse(destino.exists())

    def test_plano_nao_pode_reclassificar_amostras_como_reais(self):
        plano = self.plano()
        plano['synthetic'] = False
        for entrada in plano['tables'].values():
            entrada['synthetic'] = False
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ContractError, 'recibo.*synthetic'):
                montar_lote(plano, Path(tmp) / 'misto')
            self.assertFalse((Path(tmp) / 'misto').exists())


class CIGoldTest(unittest.TestCase):
    def workflow(self):
        return yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())

    def test_detector_e_agregador_executam_gold_sem_duplicacao(self):
        ci = self.workflow()
        self.assertIn('gold', ci['jobs']['ci']['needs'])
        self.assertFalse((ROOT / '.github/workflows/gold-faturas.yml').exists())
        comandos = [s.get('run', '') for s in ci['jobs']['gold']['steps']]
        self.assertTrue(any('ruff format --check' in c for c in comandos))
        self.assertTrue(any('unittest discover -s data-engineering/tests' in c for c in comandos))
        codigo = ci['jobs']['changes']['steps'][1]['run'].split("python - <<'PY'\n")[1]
        codigo = textwrap.dedent(codigo.rsplit('\nPY', 1)[0])
        for caminho, esperado in [
            ('data-engineering/silver_to_gold/gold_faturas.py', 'true'),
            ('contracts/VERSION', 'true'),
            ('importador/src/importador/loader.py', 'true'),
            ('pyproject.toml', 'true'),
            ('docs/exemplo.md', 'false'),
        ]:
            with tempfile.TemporaryDirectory() as tmp:
                pasta = Path(tmp)
                subprocess.run(['git', 'init', '-q', tmp], check=True)
                arquivo = pasta / caminho
                arquivo.parent.mkdir(parents=True, exist_ok=True)
                arquivo.write_text('fixture')
                subprocess.run(['git', 'add', '.'], cwd=tmp, check=True)
                output = pasta / 'output'
                subprocess.run(
                    [sys.executable, '-c', codigo],
                    cwd=tmp,
                    check=True,
                    env={
                        **os.environ,
                        'BASE_SHA': '',
                        'HEAD_SHA': '',
                        'GITHUB_OUTPUT': str(output),
                    },
                )
                self.assertIn('gold=' + esperado, output.read_text())

    def test_agregador_rejeita_failure_cancelled_e_skipped_indevido(self):
        script = self.workflow()['jobs']['ci']['steps'][0]['run']
        for mudou in ['true', 'false']:
            for resultado in ['success', 'failure', 'cancelled', 'skipped']:
                env = {
                    **os.environ,
                    'CHANGES_RESULT': 'success',
                    'BACKEND_CHANGED': 'false',
                    'BACKEND_RESULT': 'skipped',
                    'FRONTEND_CHANGED': 'false',
                    'FRONTEND_RESULT': 'skipped',
                    'FATURAS_CHANGED': 'true',
                    'FATURAS_RESULT': 'success',
                    'GOLD_CHANGED': mudou,
                    'GOLD_RESULT': resultado,
                }
                result = subprocess.run(['bash', '-c', script], env=env, capture_output=True)
                esperado = 'success' if mudou == 'true' else 'skipped'
                with self.subTest(mudou=mudou, resultado=resultado):
                    self.assertEqual(result.returncode == 0, resultado == esperado)
        env['CHANGES_RESULT'] = 'failure'
        self.assertNotEqual(
            subprocess.run(['bash', '-c', script], env=env, capture_output=True).returncode, 0
        )
