"""Conferência de versões da exportação da Gold, com histórico Delta sintético."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'silver_to_gold'))
from gold_exportacao import (  # noqa: E402
    dados_mudaram_depois,
    dentro_da_janela,
    escrita_de_dados,
    janela_de_dados,
    versao_do_marcador,
)


def historico(*commits):
    """Linhas de DESCRIBE HISTORY: (versão, momento, operação), com o momento em minutos."""
    return [{'version': v, 'timestamp': t, 'operation': op} for v, t, op in commits]


SILVER = historico(
    (0, 10, 'CREATE OR REPLACE TABLE AS SELECT'),
    (1, 20, 'COMPUTE STATS'),
    (2, 30, 'CREATE OR REPLACE TABLE AS SELECT'),
    (3, 40, 'OPTIMIZE'),
)


class JanelaDeDadosTest(unittest.TestCase):
    def test_versao_de_manutencao_vale_desde_a_escrita_anterior(self):
        self.assertEqual(janela_de_dados(SILVER, 1), (10, 30))

    def test_sem_escrita_posterior_a_janela_fica_aberta(self):
        self.assertEqual(janela_de_dados(SILVER, 3), (30, None))
        self.assertEqual(janela_de_dados(SILVER, 2), (30, None))

    def test_versao_sem_escrita_de_dados_para(self):
        so_manutencao = historico((0, 10, 'SET TBLPROPERTIES'), (1, 20, 'WRITE'))
        with self.assertRaisesRegex(ValueError, 'sem escrita de dados'):
            janela_de_dados(so_manutencao, 0)

    def test_dentro_da_janela_exclui_os_limites(self):
        self.assertTrue(dentro_da_janela(25, (10, 30)))
        self.assertTrue(dentro_da_janela(99, (30, None)))
        self.assertFalse(dentro_da_janela(10, (10, 30)))
        self.assertFalse(dentro_da_janela(30, (10, 30)))


class EscritaDeDadosTest(unittest.TestCase):
    """Item 1 da 2ª review do #146: a Gold exportada cuja última versão é manutenção."""

    GOLD = historico(
        (0, 15, 'CREATE OR REPLACE TABLE AS SELECT'),
        (1, 35, 'OPTIMIZE'),
    )

    def test_optimize_posterior_nao_conta_como_gravacao(self):
        # Gravada aos 15, com a Silver da versão 0; o OPTIMIZE aos 35 cai na janela da versão 2
        commit = escrita_de_dados(self.GOLD, 1)
        self.assertEqual(commit['timestamp'], 15)
        self.assertFalse(dentro_da_janela(commit['timestamp'], janela_de_dados(SILVER, 2)))
        self.assertTrue(dentro_da_janela(commit['timestamp'], janela_de_dados(SILVER, 0)))

    def test_restore_seguido_de_optimize_continua_restore(self):
        gold = historico(
            (0, 15, 'CREATE OR REPLACE TABLE AS SELECT'),
            (1, 32, 'CREATE OR REPLACE TABLE AS SELECT'),
            (2, 33, 'RESTORE'),
            (3, 50, 'OPTIMIZE'),
        )
        self.assertEqual(escrita_de_dados(gold, 3)['operation'], 'RESTORE')

    def test_manutencao_durante_a_exportacao_nao_muda_os_dados(self):
        gold = self.GOLD + historico((2, 60, 'OPTIMIZE'), (3, 61, 'COMPUTE STATS'))
        self.assertFalse(dados_mudaram_depois(gold, 1))
        self.assertTrue(dados_mudaram_depois(gold + historico((4, 70, 'WRITE')), 1))


class VersaoDoMarcadorTest(unittest.TestCase):
    """Item 2 da 2ª review do #146: o marcador da Silver de faturas lido pela Gold de perdas."""

    MARCADOR = historico(
        (0, 10, 'CREATE TABLE AS SELECT'),
        (1, 30, 'CREATE OR REPLACE TABLE AS SELECT'),
        (2, 35, 'OPTIMIZE'),
        (3, 50, 'CREATE OR REPLACE TABLE AS SELECT'),
    )
    IDS = {0: {'a'}, 1: {'b'}, 2: {'b'}, 3: {'c'}}

    def test_acha_a_versao_da_execucao_e_a_janela(self):
        lidas = []

        def ids(versao):
            lidas.append(versao)
            return self.IDS[versao]

        versao = versao_do_marcador(self.MARCADOR, ids, 'b')
        self.assertEqual(versao, 1)
        self.assertEqual(lidas, [3, 1])  # manutenção não é lida
        self.assertEqual(janela_de_dados(self.MARCADOR, versao), (30, 50))

    def test_execucao_atual_le_uma_versao_so(self):
        lidas = []

        def ids(versao):
            lidas.append(versao)
            return self.IDS[versao]

        self.assertEqual(versao_do_marcador(self.MARCADOR, ids, 'c'), 3)
        self.assertEqual(lidas, [3])

    def test_execucao_ausente_para(self):
        with self.assertRaisesRegex(ValueError, 'execução z'):
            versao_do_marcador(self.MARCADOR, self.IDS.get, 'z')


if __name__ == '__main__':
    unittest.main()
