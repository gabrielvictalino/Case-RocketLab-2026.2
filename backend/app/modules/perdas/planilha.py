"""Lê e escreve as planilhas de campo, sem acessar o banco.

A normalização repete as regras de `docs/silver/silver_inspecoes.md` (seção 2), para a
planilha que a equipe preenche valer o mesmo que a planilha histórica.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from pydantic import ValidationError

from app.core.errors import APIError
from app.modules.perdas.schemas import Resultado

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
LIMITE_BYTES = 5 * 1024 * 1024
# O xlsx é um zip: o tamanho enviado não limita o que a leitura vai descompactar.
LIMITE_DESCOMPACTADO = 50 * 1024 * 1024
LIMITE_LINHAS = 5_000

COLUNAS_CAMPO = (
    'id_inspecao',
    'id_uc',
    'data',
    'inspetor',
    'resultado',
    'tipo_irregularidade',
    'kwh_recuperado',
    'id_ordem',
)
# `id_inspecao` só existe para manter o layout histórico: o portal gera o seu.
COLUNAS_OBRIGATORIAS = tuple(coluna for coluna in COLUNAS_CAMPO if coluna != 'id_inspecao')

FORMATOS_DATA = (
    (re.compile(r'\d{4}-\d{2}-\d{2}', re.ASCII), '%Y-%m-%d'),
    (re.compile(r'\d{2}/\d{2}/\d{4}', re.ASCII), '%d/%m/%Y'),
    (re.compile(r'\d{2}\.\d{2}\.\d{4}', re.ASCII), '%d.%m.%Y'),
    (re.compile(r'\d{2}-\d{2}-\d{4}', re.ASCII), '%m-%d-%Y'),
)
INICIO_DA_BASE = date(2022, 7, 1)
RESULTADOS = {
    'CONFIRMADA': 'IRREGULARIDADE CONFIRMADA',
    'IRREGULARIDADE CONFIRMADA': 'IRREGULARIDADE CONFIRMADA',
    'NADA CONSTA': 'SEM IRREGULARIDADE',
    'SEM IRREGULARIDADE': 'SEM IRREGULARIDADE',
}
AUSENCIAS_DE_TIPO = {'', '-', 'NULL', 'N/A'}
TIPOS_CONHECIDOS = {
    'BY-PASS',
    'DESVIO DIRETO',
    'LACRE VIOLADO',
    'LIGACAO CLANDESTINA',
    'MEDIDOR ADULTERADO',
}
KWH = re.compile(r'-?\d+(?:[.,]\d+)?', re.ASCII)
LIMITE_KWH = Decimal(10) ** 16
UC = re.compile(r'UC\d{6}', re.ASCII)
INSPETOR = re.compile(r'INSP-(00[1-9]|0[1-3][0-9]|040)', re.ASCII)


@dataclass(frozen=True)
class LinhaLida:
    numero: int
    id_ordem: UUID | None
    id_uc: str | None
    inspetor: str | None
    resultado: Resultado
    aviso: str | None


@dataclass(frozen=True)
class LinhaComErro:
    numero: int
    motivo: str


def nome_do_arquivo(bruto: str | None) -> str:
    """O nome vem do navegador: guarda só a parte final e nada que não se imprime."""
    nome = PurePosixPath((bruto or '').replace('\\', '/')).name
    return ''.join(caractere for caractere in nome if caractere.isprintable())[:255] or 'planilha'


def gerar(titulo: str, colunas: Iterable[str], linhas: Iterable[Iterable]) -> bytes:
    livro = Workbook(write_only=True)
    folha = livro.create_sheet(titulo)
    folha.append(list(colunas))
    for linha in linhas:
        folha.append([_celula(folha, valor) for valor in linha])
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def _celula(folha, valor):
    if not isinstance(valor, str):
        return valor
    # Sem isso, um texto que começa com "=" iria para o arquivo como fórmula.
    celula = WriteOnlyCell(folha, value=valor)
    celula.data_type = 's'
    return celula


def ler(conteudo: bytes) -> list[tuple[int, dict]]:
    """Devolve (número da linha no Excel, células por coluna) de cada linha preenchida."""
    if len(conteudo) > LIMITE_BYTES:
        raise APIError(413, 'A planilha passa do limite de 5 MB', 'PLANILHA_GRANDE')
    try:
        with ZipFile(BytesIO(conteudo)) as pacote:
            descompactado = sum(item.file_size for item in pacote.infolist())
        if descompactado > LIMITE_DESCOMPACTADO:
            raise APIError(413, 'A planilha é grande demais para ler', 'PLANILHA_GRANDE')
        livro = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
        try:
            return _linhas(livro.worksheets[0].iter_rows(values_only=True))
        finally:
            livro.close()
    except APIError:
        raise
    except Exception as erro:
        # O arquivo é do usuário e o leitor falha de muitas formas num xlsx corrompido.
        raise APIError(
            422, 'O arquivo não é uma planilha Excel (.xlsx) válida', 'PLANILHA_INVALIDA'
        ) from erro


def _linhas(linhas) -> list[tuple[int, dict]]:
    colunas = [_nome_da_coluna(celula) for celula in next(linhas, ())]
    faltando = [coluna for coluna in COLUNAS_OBRIGATORIAS if coluna not in colunas]
    if faltando:
        raise APIError(
            422, f'Faltam colunas na planilha: {", ".join(faltando)}', 'PLANILHA_INVALIDA'
        )
    repetidas = [coluna for coluna in COLUNAS_CAMPO if colunas.count(coluna) > 1]
    if repetidas:
        raise APIError(
            422, f'Colunas repetidas na planilha: {", ".join(repetidas)}', 'PLANILHA_INVALIDA'
        )
    preenchidas = []
    for numero, linha in enumerate(linhas, start=2):
        if all(celula is None or str(celula).strip() == '' for celula in linha):
            continue
        if len(preenchidas) == LIMITE_LINHAS:
            raise APIError(
                413, f'A planilha passa do limite de {LIMITE_LINHAS} linhas', 'PLANILHA_GRANDE'
            )
        preenchidas.append((numero, dict(zip(colunas, map(_sem_nul, linha)))))
    if not preenchidas:
        raise APIError(422, 'A planilha não tem linhas preenchidas', 'PLANILHA_INVALIDA')
    return preenchidas


def _nome_da_coluna(celula) -> str:
    return '' if celula is None else str(celula).strip().lower()


def _sem_nul(celula):
    # O leitor decodifica `_x0000_`, e o PostgreSQL não aceita NUL em text nem em jsonb.
    return celula.replace('\x00', '') if isinstance(celula, str) else celula


def normalizar(numero: int, celulas: dict) -> LinhaLida | LinhaComErro:
    motivos: list[str] = []

    def campo(converter, nome: str):
        try:
            return converter(celulas.get(nome))
        except ValueError as erro:
            motivos.append(str(erro))
            return None

    resultado = campo(_resultado, 'resultado')
    if resultado is None and not motivos:
        # Linha exportada que a equipe ainda não preencheu.
        if all(_vazio(celulas.get(nome)) for nome in ('data', 'kwh_recuperado')):
            return LinhaComErro(numero, 'Linha sem resultado preenchido')
        motivos.append('Resultado vazio')
    id_ordem = campo(_id_ordem, 'id_ordem')
    id_uc = campo(_id_uc, 'id_uc')
    inspetor = campo(_inspetor, 'inspetor')
    data = campo(_data, 'data')
    tipo = campo(_tipo, 'tipo_irregularidade')
    kwh = campo(_kwh, 'kwh_recuperado')
    if id_ordem is None and id_uc is None and not motivos:
        motivos.append('Informe id_ordem ou id_uc')
    if motivos:
        return LinhaComErro(numero, '; '.join(motivos))
    try:
        corpo = Resultado(
            resultado=resultado, tipo_irregularidade=tipo, kwh_recuperado=kwh, data=data
        )
    except ValidationError as erro:
        return LinhaComErro(numero, _motivo_de_validacao(erro))
    aviso = None
    if tipo is not None and tipo not in TIPOS_CONHECIDOS:
        aviso = f'Tipo de irregularidade fora dos 5 tipos da base: {tipo}'
    return LinhaLida(numero, id_ordem, id_uc, inspetor, corpo, aviso)


def _motivo_de_validacao(erro: ValidationError) -> str:
    detalhe = erro.errors()[0]
    causa = detalhe.get('ctx', {}).get('error')
    if causa is not None:
        return str(causa)
    return f'Valor inválido em {".".join(map(str, detalhe["loc"]))}'


def _vazio(valor) -> bool:
    return valor is None or str(valor).strip() == ''


def _texto(valor) -> str:
    return '' if valor is None else str(valor).strip().upper()


def _resultado(valor) -> str | None:
    texto = _texto(valor)
    if not texto:
        return None
    if texto not in RESULTADOS:
        raise ValueError(f'Resultado desconhecido: {texto}')
    return RESULTADOS[texto]


def _id_ordem(valor) -> UUID | None:
    if _vazio(valor):
        return None
    try:
        return UUID(str(valor).strip())
    except ValueError:
        raise ValueError('id_ordem inválido') from None


def _id_uc(valor) -> str | None:
    texto = _texto(valor)
    if not texto:
        return None
    if not UC.fullmatch(texto):
        raise ValueError(f'UC fora do padrão: {texto}')
    return texto


def _inspetor(valor) -> str | None:
    texto = _texto(valor)
    if not texto:
        return None
    if not INSPETOR.fullmatch(texto):
        raise ValueError(f'Inspetor fora do padrão: {texto}')
    return texto


def _data(valor) -> date:
    data = _converter_data(valor)
    if data < INICIO_DA_BASE:
        raise ValueError('Data anterior ao início da base (jul/2022)')
    return data


def _converter_data(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = '' if valor is None else str(valor).strip()
    if not texto:
        raise ValueError('Data vazia')
    for padrao, formato in FORMATOS_DATA:
        if padrao.fullmatch(texto):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                raise ValueError(f'Data inexistente: {texto}') from None
    raise ValueError(f'Data em formato desconhecido: {texto}')


def _tipo(valor) -> str | None:
    texto = _texto(valor)
    return None if texto in AUSENCIAS_DE_TIPO else texto


def _kwh(valor) -> Decimal:
    texto = '' if valor is None or isinstance(valor, bool) else str(valor).strip()
    if not texto:
        raise ValueError('kWh recuperado vazio ou inválido')
    if not KWH.fullmatch(texto):
        raise ValueError(f'kWh recuperado inválido: {texto}')
    kwh = Decimal(texto.replace(',', '.'))
    if kwh < 0:
        raise ValueError('kWh recuperado negativo')
    if kwh >= LIMITE_KWH:
        raise ValueError('kWh recuperado acima do limite')
    return kwh.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
