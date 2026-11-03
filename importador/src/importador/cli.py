import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from importador.contracts import ContractError
from importador.loader import load


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='Importação transacional do contrato Gold local')
    parser.add_argument(
        '--origem', required=True, help='Diretório com arquivos CSV e manifest.json'
    )
    parser.add_argument(
        '--verificar',
        action='store_true',
        default=False,
        help='Valida a carga até validate em transação e faz rollback sem alterar banco/Redis',
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        load_id = asyncio.run(
            load(
                args.origem,
                os.environ['DATABASE_URL_IMPORTADOR'],
                os.getenv('REDIS_URL'),
                verify_only=args.verificar,
            )
        )
    except ContractError as exc:
        if args.verificar:
            sys.stderr.write(f'Verificação falhou: {exc}\n')
        else:
            logging.error('Carga rejeitada: %s; publicação anterior preservada', exc)
        raise SystemExit(1) from None
    except Exception as exc:
        logging.error('Carga rejeitada (%s); publicação anterior preservada', type(exc).__name__)
        raise SystemExit(1) from None
    if not args.verificar:
        print(f'Carga publicada: {load_id}')


if __name__ == '__main__':
    main()
