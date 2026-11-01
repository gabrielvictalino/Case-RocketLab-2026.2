import argparse
import asyncio
import logging
import os

from dotenv import load_dotenv

from importador.contracts import ContractError
from importador.loader import load


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='Importação transacional do contrato Gold local')
    parser.add_argument('--origem', required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        load_id = asyncio.run(
            load(args.origem, os.environ['DATABASE_URL_IMPORTADOR'], os.getenv('REDIS_URL'))
        )
    except ContractError as exc:
        logging.error('Carga rejeitada: %s; publicação anterior preservada', exc)
        raise SystemExit(1) from None
    except Exception as exc:
        # Não imprime DSN ou dados de registros em erros do driver.
        logging.error('Carga rejeitada (%s); publicação anterior preservada', type(exc).__name__)
        raise SystemExit(1) from None
    print(f'Carga publicada: {load_id}')
