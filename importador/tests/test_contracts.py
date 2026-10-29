import importlib.util
from pathlib import Path

import pytest

from importador.contracts import parse

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
