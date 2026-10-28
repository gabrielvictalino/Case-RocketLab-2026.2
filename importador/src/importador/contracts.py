import csv
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / 'contracts'


class ContractError(ValueError):
    pass


def specifications():
    return {
        p.stem: yaml.safe_load(p.read_text())
        for p in sorted((CONTRACTS / 'tabelas').glob('*.yaml'))
    }


def manifest_for(origin):
    manifest = json.loads((origin / 'manifest.json').read_text())
    schema = json.loads((CONTRACTS / 'manifest.schema.json').read_text())
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(manifest)
    )
    if errors:
        raise ContractError('Manifesto inválido: ' + errors[0].message)
    if manifest['contract_version'] != (CONTRACTS / 'VERSION').read_text().strip():
        raise ContractError('Versão do contrato incompatível')
    if not manifest['synthetic']:
        raise ContractError('Contrato provisório aceita apenas dados explicitamente sintéticos')
    if manifest['period']['start'] > manifest['period']['end']:
        raise ContractError('Período invertido no manifesto')
    return manifest


def parse(value, spec):
    if value == '' and spec['nullable']:
        return None
    if value is None or value == '':
        raise ValueError('Valor obrigatório ausente')
    type_ = spec['type']
    if type_ == 'text':
        result = value
        if not value.strip():
            raise ValueError('Texto vazio')
    elif type_ == 'date':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Data deve usar ISO AAAA-MM-DD')
        result = date.fromisoformat(value)
        if spec.get('month') and result.day != 1:
            raise ValueError('Competência deve ser o primeiro dia do mês')
    elif type_ == 'timestamp':
        result = datetime.fromisoformat(value)
        if result.tzinfo is not None or 'T' not in value:
            raise ValueError('Data-hora local ISO sem fuso obrigatória')
    elif type_ == 'boolean':
        if value not in ('true', 'false'):
            raise ValueError('Booleano deve ser true ou false')
        result = value == 'true'
    elif type_ == 'integer':
        if not re.fullmatch(r'-?\d+', value):
            raise ValueError('Inteiro inválido')
        result = int(value)
    elif type_.startswith('numeric'):
        result = Decimal(value)
        precision, scale = map(int, re.findall(r'\d+', type_))
        if (
            not result.is_finite()
            or result != result.quantize(Decimal(1).scaleb(-scale))
            or abs(result) >= Decimal(10) ** (precision - scale)
        ):
            raise ValueError('Decimal fora da precisão/escala')
    elif type_ == 'jsonb':
        data = json.loads(value)
        if (
            not isinstance(data, list)
            or not data
            or not all(isinstance(x, str) and x.strip() for x in data)
        ):
            raise ValueError('Motivos devem ser uma lista de textos não vazios')
        result = json.dumps(data)
    else:
        raise ValueError('Tipo desconhecido no contrato')
    if spec.get('pattern') and not re.fullmatch(spec['pattern'], value):
        raise ValueError('Formato inválido')
    if 'enum' in spec and result not in spec['enum']:
        raise ValueError('Valor fora do domínio')
    if 'minimum' in spec and result < spec['minimum']:
        raise ValueError('Valor abaixo do mínimo')
    if 'maximum' in spec and result > spec['maximum']:
        raise ValueError('Valor acima do máximo')
    return result


def records(file, spec):
    with file.open(newline='', encoding='utf-8') as source:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames != list(spec['columns']):
            raise ContractError(f'{spec["table"]}: cabeçalho incompatível')
        for line, row in enumerate(reader, 2):
            if None in row:
                raise ContractError(f'{spec["table"]}: linha {line} tem colunas extras')
            try:
                yield tuple(parse(row[name], col) for name, col in spec['columns'].items())
            except (ValueError, TypeError, InvalidOperation) as exc:
                raise ContractError(f'{spec["table"]}: linha {line}: {exc}') from exc


def file_hash(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
