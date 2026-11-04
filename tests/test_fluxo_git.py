"""Exercita eventos reais contra um repositório Git temporário."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'fluxo', Path(__file__).parents[1] / 'scripts/validar-fluxo-git.py'
)
fluxo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fluxo)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.folder.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Test')
        Path('example').write_text('base\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Histórico legado')
        self.base = self.git('rev-parse', 'HEAD')

    def tearDown(self):
        os.chdir(self.previous)
        self.folder.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', *args], text=True).strip()

    def change(self, title='feat(backend): adiciona cálculo', content='novo\n'):
        Path('example').write_text(content)
        self.git('add', '.')
        self.git('commit', '-qm', title)
        return self.git('rev-parse', 'HEAD')

    def event(self, end, base='dev', head='feat/42-calculo', repo='owner/repo'):
        return {
            'pull_request': {
                'base': {'ref': base, 'sha': self.base},
                'head': {'ref': head, 'sha': end, 'repo': {'full_name': repo}},
                'title': 'chore(ci): configura validações',
            }
        }

    def test_valid_feature_ignores_legacy_commits(self):
        fluxo.validate(self.event(self.change()), 'pull_request', 'owner/repo')

    def test_invalid_commit_is_rejected(self):
        with self.assertRaises(ValueError):
            fluxo.validate(self.event(self.change('wip')), 'pull_request', 'owner/repo')

    def test_main_requires_same_repository_dev(self):
        end = self.change()
        fluxo.validate(self.event(end, 'main', 'dev'), 'pull_request', 'owner/repo')
        for branch, repo in [('feat/calculo', 'owner/repo'), ('dev', 'other/repo')]:
            with self.assertRaises(ValueError):
                fluxo.validate(self.event(end, 'main', branch, repo), 'pull_request', 'owner/repo')

    def test_invalid_branch_or_title_is_rejected(self):
        end = self.change()
        event = self.event(end, head='feature/Calculo')
        with self.assertRaises(ValueError):
            fluxo.validate(event, 'pull_request', 'owner/repo')
        event = self.event(end)
        event['pull_request']['title'] = 'Atualiza projeto'
        with self.assertRaises(ValueError):
            fluxo.validate(event, 'pull_request', 'owner/repo')

    def test_whitespace_is_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):
            fluxo.validate(
                self.event(self.change(content='novo  \n')), 'pull_request', 'owner/repo'
            )

    def test_push_and_first_push(self):
        end = self.change()
        for before in (self.base, '0' * 40):
            fluxo.validate(
                {'ref': 'refs/heads/dev', 'before': before, 'after': end}, 'push', 'owner/repo'
            )


if __name__ == '__main__':
    unittest.main()
