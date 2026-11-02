"""Gerador de manifesto de exportação Gold.

Roda no produtor (Job do Databricks) ou localmente. Depende apenas da biblioteca
padrão do Python e de PyYAML, sem importar o pacote importador.
"""

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def inspecionar_csv(arquivo: Path, colunas_controle: list[str]) -> tuple[int, str, dict[str, str]]:
    sha = hashlib.sha256()
    with arquivo.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha.update(chunk)
    digest = sha.hexdigest()

    totais = {col: Decimal(0) for col in colunas_controle}
    linhas = 0
    with arquivo.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0, digest, {col: '0' for col in colunas_controle}

        indices = {col: header.index(col) for col in colunas_controle}
        for row in reader:
            linhas += 1
            for col, idx in indices.items():
                val = row[idx]
                if val:
                    totais[col] += Decimal(val)
    return linhas, digest, {col: str(totais[col]) for col in colunas_controle}


def gerar_manifesto(
    origem: Path,
    *,
    batch_id: str,
    periodo: str,
    data_referencia: str,
    sintetico: bool = False,
) -> dict:
    origem = Path(origem)
    partes = periodo.split('..')
    if len(partes) != 2:
        raise ValueError(f'Período inválido: {periodo}. Formato esperado: AAAA-MM..AAAA-MM')
    start, end = partes
    versao = (ROOT / 'VERSION').read_text().strip()
    specs = {
        p.stem: yaml.safe_load(p.read_text()) for p in sorted((ROOT / 'tabelas').glob('*.yaml'))
    }
    manifest = {
        'batch_id': batch_id,
        'contract_version': versao,
        'synthetic': sintetico,
        'period': {'start': start, 'end': end},
        'reference_date': data_referencia,
        'tables': {},
    }
    for name, spec in specs.items():
        arquivo = origem / f'{name}.csv'
        if not arquivo.is_file():
            raise FileNotFoundError(f'Arquivo CSV ausente: {arquivo}')
        linhas, digest, totais = inspecionar_csv(arquivo, spec.get('control_totals', []))
        manifest['tables'][name] = {
            'file': f'{name}.csv',
            'rows': linhas,
            'sha256': digest,
            'totals': totais,
        }
    (origem / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description='Gera manifest.json de exportação Gold.')
    parser.add_argument('dir', type=Path, help='Diretório com os arquivos CSV')
    parser.add_argument('--batch-id', required=True, help='Identificador único do lote')
    parser.add_argument(
        '--periodo', required=True, help='Período coberto no formato AAAA-MM..AAAA-MM'
    )
    parser.add_argument('--data-referencia', required=True, help='Data de referência AAAA-MM-DD')
    parser.add_argument(
        '--sintetico', action='store_true', default=False, help='Indica amostra sintética'
    )
    args = parser.parse_args()
    gerar_manifesto(
        args.dir,
        batch_id=args.batch_id,
        periodo=args.periodo,
        data_referencia=args.data_referencia,
        sintetico=args.sintetico,
    )


if __name__ == '__main__':
    main()
