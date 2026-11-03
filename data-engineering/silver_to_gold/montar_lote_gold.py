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


def conferir_origem(nome, entrada, plano):
    """Vincula arquivo e metadados ao recibo do produtor, não à declaração do plano.

    Recibos devem vir de um produtor confiável. Isto não é assinatura digital.
    """
    origem = Path(entrada['file']).resolve()
    candidatos = [origem.parent / n for n in ('comercial.json', 'manifest.json')]
    recibo_path = (
        Path(entrada['receipt']).resolve()
        if 'receipt' in entrada
        else next((p for p in candidatos if p.is_file()), None)
    )
    if recibo_path is None or not recibo_path.is_file():
        raise ContractError(f'{nome}: recibo de origem obrigatório')
    try:
        recibo = json.loads(recibo_path.read_text())
        if recibo['contract_version'] != '0.3.0-provisional':
            raise ContractError(f'{nome}: versão do recibo divergente')
        if type(recibo['synthetic']) is not bool:
            raise ContractError(f'{nome}: synthetic do recibo precisa ser booleano')
        for chave in ('period', 'reference_date', 'synthetic'):
            if recibo[chave] != plano[chave]:
                raise ContractError(f'{nome}: proveniência do recibo divergente ({chave})')
        tabela = recibo['tables'][nome]
        if (recibo_path.parent / tabela['file']).resolve() != origem:
            raise ContractError(f'{nome}: arquivo não corresponde ao recibo')
        if tabela['sha256'] != entrada['sha256'] or file_hash(origem) != tabela['sha256']:
            raise ContractError(f'{nome}: hash não corresponde ao recibo')
        return recibo_path, file_hash(recibo_path)
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ContractError(f'{nome}: recibo de origem inválido') from exc


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
            recibo, hash_recibo = conferir_origem(nome, entrada, plano)
            origem = Path(entrada['file'])
            if file_hash(origem) != entrada['sha256']:
                raise ContractError(f'{nome}: hash da fonte divergente')
            arquivo = pasta / f'{nome}.csv'
            shutil.copyfile(origem, arquivo)
            if file_hash(arquivo) != entrada['sha256']:
                raise ContractError(f'{nome}: cópia divergente')
            if file_hash(recibo) != hash_recibo:
                raise ContractError(f'{nome}: recibo mudou durante a cópia')
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
