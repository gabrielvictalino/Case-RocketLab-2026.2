import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from importador.contracts import ContractError, manifest_for, parse, specifications

ROOT = Path(__file__).resolve().parents[2]


def test_samples_are_reproducible(tmp_path):
    spec = importlib.util.spec_from_file_location('gerar', ROOT / 'contracts/samples/gerar.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.gerar(tmp_path)
    expected = ROOT / 'contracts/samples'
    for filename in expected.glob('*.csv'):
        assert filename.read_bytes() == (tmp_path / filename.name).read_bytes()
    assert (expected / 'manifest.json').read_bytes() == (tmp_path / 'manifest.json').read_bytes()


def test_contracts_metadata_r1():
    specs = specifications()
    assert len(specs) == 12, 'O contrato deve ter exatamente 12 tabelas'
    for name, spec in specs.items():
        assert spec.get('version') == '0.3.0-provisional', (
            f'{name}: versão deve ser 0.3.0-provisional'
        )
        assert spec.get('status') == 'provisorio-nao-aprovado', f'{name}: status incorreto'
        assert isinstance(spec.get('description'), str) and spec['description'].strip(), (
            f'{name}: description da tabela ausente ou vazia'
        )
        assert isinstance(spec.get('grain'), str) and spec['grain'].strip(), (
            f'{name}: grain ausente ou vazio'
        )
        assert isinstance(spec.get('primary_key'), list) and spec['primary_key'], (
            f'{name}: primary_key ausente ou vazia'
        )
        assert isinstance(spec.get('control_totals'), list), (
            f'{name}: control_totals deve ser lista'
        )
        for col, col_spec in spec['columns'].items():
            assert isinstance(col_spec.get('type'), str) and col_spec['type'].strip(), (
                f'{name}.{col}: type ausente'
            )
            assert isinstance(col_spec.get('nullable'), bool), (
                f'{name}.{col}: nullable deve ser booleano'
            )
            assert isinstance(col_spec.get('unit'), str) and col_spec['unit'].strip(), (
                f'{name}.{col}: unit ausente ou vazia'
            )
            assert (
                isinstance(col_spec.get('description'), str) and col_spec['description'].strip()
            ), f'{name}.{col}: description ausente ou vazia'


def test_gerar_manifesto_matches_committed_manifest(tmp_path):
    manifesto_spec = importlib.util.spec_from_file_location(
        'manifesto', ROOT / 'contracts/manifesto.py'
    )
    manifesto_mod = importlib.util.module_from_spec(manifesto_spec)
    manifesto_spec.loader.exec_module(manifesto_mod)

    samples_dir = ROOT / 'contracts/samples'
    for csv_file in samples_dir.glob('*.csv'):
        shutil.copy2(csv_file, tmp_path / csv_file.name)

    gerado = manifesto_mod.gerar_manifesto(
        tmp_path,
        batch_id='amostra-sintetica-v1',
        periodo='2022-07..2026-06',
        data_referencia='2026-07-01',
        sintetico=True,
    )
    esperado = json.loads((samples_dir / 'manifest.json').read_text())
    assert gerado == esperado


def test_manifest_reference_date_gate(tmp_path):
    samples_dir = ROOT / 'contracts/samples'
    shutil.copytree(samples_dir, tmp_path / 'batch')
    manifest_file = tmp_path / 'batch/manifest.json'
    manifest = json.loads(manifest_file.read_text())
    manifest['reference_date'] = '2026-05-31'  # anterior a period.end (2026-06)
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as exc:
        manifest_for(tmp_path / 'batch')
    assert 'reference_date' in str(exc.value)


def test_manifest_reference_date_invalid_calendar_date(tmp_path):
    samples_dir = ROOT / 'contracts/samples'
    shutil.copytree(samples_dir, tmp_path / 'batch')
    manifest_file = tmp_path / 'batch/manifest.json'
    manifest = json.loads(manifest_file.read_text())
    manifest['reference_date'] = '2026-02-30'
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as exc:
        manifest_for(tmp_path / 'batch')
    assert 'manifesto.reference_date inválida (R6)' in str(exc.value)


@pytest.mark.parametrize(
    'value,type_',
    [
        ('NaN', 'numeric(18,2)'),
        ('1.001', 'numeric(18,2)'),
        ('1.5', 'integer'),
        ('FALSE', 'boolean'),
        ('01/02/2025', 'date'),
        ('2025-01-01T10:00:00+00:00', 'timestamp'),
        ('{}', 'jsonb'),
    ],
)
def test_invalid_types(value, type_):
    with pytest.raises(ValueError):
        parse(value, {'type': type_, 'nullable': False})
