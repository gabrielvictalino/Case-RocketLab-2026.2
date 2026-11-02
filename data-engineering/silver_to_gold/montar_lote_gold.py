"""Monta lote de 12 tabelas já exportadas, sem produzir dados de outros domínios.

Plano JSON: batch_id, period {start,end}, reference_date, synthetic e tables.
Cada tabela: file (caminho), sha256, period, reference_date e synthetic.
Exige proveniência compatível para impedir misturar fixtures com exportações reais.
O importador --verificar continua obrigatório antes da homologação do lote.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'importador' / 'src'))

from contracts.manifesto import gerar_manifesto  # noqa: E402
from importador.contracts import (  # noqa: E402
    ContractError,
    file_hash,
    manifest_for,
    records,
    specifications,
)


def montar_lote(plano, destino):
    specs = specifications()
    if set(plano['tables']) != set(specs):
        raise ContractError('Lote exige exatamente as 12 tabelas contratadas')
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.gold-', dir=destino.parent) as temporaria:
        pasta = Path(temporaria)
        for nome, spec in specs.items():
            entrada = plano['tables'][nome]
            for chave in ('period', 'reference_date', 'synthetic'):
                if entrada[chave] != plano[chave]:
                    raise ContractError(f'{nome}: proveniência divergente ({chave})')
            origem = Path(entrada['file'])
            if file_hash(origem) != entrada['sha256']:
                raise ContractError(f'{nome}: hash da fonte divergente')
            arquivo = pasta / f'{nome}.csv'
            shutil.copyfile(origem, arquivo)
            if file_hash(arquivo) != entrada['sha256']:
                raise ContractError(f'{nome}: cópia divergente')
            # Validação escalar e PK em streaming; FKs e gates relacionais em --verificar.
            indices = [list(spec['columns']).index(c) for c in spec['primary_key']]
            chaves = set()
            for linha in records(arquivo, spec):
                chave = tuple(linha[i] for i in indices)
                if chave in chaves:
                    raise ContractError(f'{nome}: chave duplicada')
                chaves.add(chave)
        gerar_manifesto(
            pasta,
            batch_id=plano['batch_id'],
            periodo=plano['period']['start'] + '..' + plano['period']['end'],
            data_referencia=plano['reference_date'],
            sintetico=plano['synthetic'],
        )
        manifest_for(pasta)
        # O diretório completo só aparece após conferir todos os arquivos e manifesto.
        pasta.rename(destino)
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plano', required=True, type=Path)
    parser.add_argument('--destino', required=True, type=Path)
    args = parser.parse_args()
    montar_lote(json.loads(args.plano.read_text()), args.destino)


if __name__ == '__main__':
    main()
