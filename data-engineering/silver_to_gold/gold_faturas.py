"""Transformações e exportação da Gold de faturas, sem dependência de dbutils."""

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

# Nome Silver -> (enum contratual, adicional fixo do case em R$/kWh).
BANDEIRAS = {
    'Verde': ('VERDE', '0'),
    'Amarela': ('AMARELA', '0.01885'),
    'Vermelha P1': ('VERMELHA_P1', '0.04463'),
    'Vermelha P2': ('VERMELHA_P2', '0.07877'),
}
VERSAO_REGRAS = 'GOLD_FATURAS_V2'
COMPETENCIA_REGEX = r'^[1-9][0-9]{3}-(0[1-9]|1[0-2])$'
DIMENSOES = ['municipio', 'bairro', 'classe']
FLAGS_LEITURAS = [
    'flag_troca_medidor',
    'flag_sem_leitura_anterior',
    'flag_sinal_nao_confirmado',
]
DINHEIRO = ['valor_energia', 'tributos', 'valor_total']
COLUNAS_FATURAS = [
    'id_fatura',
    'id_uc',
    'mes_referencia',
    'data_emissao',
    'valor_energia',
    'tributos',
    'bandeira_tarifaria',
    'valor_total',
    'data_vencimento',
    'data_pagamento',
    'status',
    'flag_uc_sem_cadastro',
]
COLUNAS_AUDITORIA = [
    'source_file',
    'ingestion_datetime',
    'metodo_interpretacao_emissao',
    'flag_emissao_original_ambigua',
    'flag_emissao_fora_competencia',
    'versao_regras',
]


def validar_data_referencia(data_referencia: str) -> date:
    """Exige uma data de referência preenchida no formato AAAA-MM-DD."""
    if data_referencia is None or (
        isinstance(data_referencia, str) and not data_referencia.strip()
    ):
        raise ValueError('Preencha data_referencia no formato AAAA-MM-DD (ex.: 2026-10-22)')
    try:
        referencia = date.fromisoformat(data_referencia)
    except (TypeError, ValueError) as erro:
        raise ValueError('data_referencia deve ser uma data válida no formato AAAA-MM-DD') from erro
    if referencia.isoformat() != data_referencia:
        raise ValueError('data_referencia deve usar o formato AAAA-MM-DD (ex.: 2026-10-22)')
    return referencia


def _exigir_colunas(df, colunas, nome):
    ausentes = set(colunas) - set(df.columns)
    if ausentes:
        raise ValueError(f'{nome}: colunas ausentes: {sorted(ausentes)}')


def _validar_regras(df, regras, nome):
    contagens = (
        df.agg(*[F.count(F.when(condicao, 1)).alias(regra) for regra, condicao in regras.items()])
        .first()
        .asDict()
    )
    falhas = {regra: n for regra, n in contagens.items() if n}
    if falhas:
        raise ValueError(f'{nome}: {falhas}')


def _exigir_chave(df, colunas, nome):
    if df.groupBy(*colunas).count().filter('count > 1').limit(1).count():
        raise ValueError(f'{nome}: chave duplicada {colunas}')


def _soma(coluna):
    return F.coalesce(F.sum(coluna), F.lit(0)).cast('decimal(28,2)')


@dataclass(frozen=True)
class FontesValidadas:
    cadastro: DataFrame
    leituras: DataFrame


def validar_fontes_comuns(cadastro, leituras, validacao=None):
    """Valida uma vez por par de DataFrames; APIs isoladas mantêm seus gates."""
    if validacao is not None:
        if (
            not isinstance(validacao, FontesValidadas)
            or validacao.cadastro is not cadastro
            or validacao.leituras is not leituras
        ):
            raise ValueError('Validação pertence a outros DataFrames')
        return validacao
    _exigir_colunas(cadastro, ['id_uc', *DIMENSOES], 'cadastro')
    _exigir_colunas(
        leituras, ['id_uc', 'mes_referencia', 'consumo_kwh', *FLAGS_LEITURAS], 'leituras'
    )
    for flag in FLAGS_LEITURAS:
        if leituras.schema[flag].dataType.simpleString() != 'boolean':
            raise ValueError(f'leituras: {flag} precisa ser boolean')
    if leituras.schema['consumo_kwh'].dataType.typeName() not in {
        'integer',
        'long',
        'short',
        'decimal',
    }:
        raise ValueError('leituras: consumo_kwh precisa ser inteiro ou decimal')
    _exigir_chave(cadastro, ['id_uc'], 'cadastro')
    _validar_regras(
        cadastro,
        {
            f'{c}_ausente': F.col(c).isNull() | (F.trim(F.col(c)) == '')
            for c in ['id_uc', *DIMENSOES]
        },
        'cadastro',
    )
    _exigir_chave(leituras, ['id_uc', 'mes_referencia'], 'leituras')
    _validar_regras(
        leituras,
        {
            'chave_nula': F.col('id_uc').isNull() | F.col('mes_referencia').isNull(),
            'competencia_invalida': ~F.col('mes_referencia').rlike(COMPETENCIA_REGEX),
        },
        'leituras',
    )

    return FontesValidadas(cadastro, leituras)


def construir_faturas(
    faturas: DataFrame,
    cadastro: DataFrame,
    leituras: DataFrame,
    data_referencia: str,
    fontes_validadas=None,
) -> dict[str, DataFrame]:
    """Retorna detalhe elegível, exclusões reconciliáveis e resumo mensal.

    Faturas inclui as duas saídas Silver, principal e pendentes, via unionByName.
    A data é a data de referência do retrato de status da extração, não hoje.
    """
    referencia = validar_data_referencia(data_referencia)
    _exigir_colunas(faturas, COLUNAS_FATURAS, 'faturas')
    validar_fontes_comuns(cadastro, leituras, fontes_validadas)
    tipos = {c: 'decimal(18,2)' for c in DINHEIRO}
    tipos.update({c: 'date' for c in ['data_emissao', 'data_vencimento', 'data_pagamento']})
    tipos.update(
        {
            c: 'string'
            for c in [
                'id_fatura',
                'id_uc',
                'mes_referencia',
                'bandeira_tarifaria',
                'status',
            ]
        }
    )
    tipos['flag_uc_sem_cadastro'] = 'boolean'
    for coluna, esperado in tipos.items():
        if faturas.schema[coluna].dataType.simpleString() != esperado:
            raise ValueError(f'faturas: {coluna} precisa ser {esperado}')
    faturas = faturas.select(
        *COLUNAS_FATURAS,
        *[c for c in COLUNAS_AUDITORIA if c in faturas.columns],
    )
    obrigatorias = [c for c in COLUNAS_FATURAS if c != 'data_pagamento']
    regras = {f'{c}_nulo': F.col(c).isNull() for c in obrigatorias}
    regras.update(
        {
            'id_fatura_vazio': F.trim(F.col('id_fatura')) == '',
            'id_uc_invalido': ~F.col('id_uc').rlike(r'^UC[0-9]+$'),
            'competencia_invalida': ~F.col('mes_referencia').rlike(COMPETENCIA_REGEX),
            'status_invalido': ~F.col('status').isin('PAGA', 'EM ABERTO'),
            'bandeira_invalida': ~F.col('bandeira_tarifaria').isin(*BANDEIRAS),
            'total_divergente': F.col('valor_total') != F.col('valor_energia') + F.col('tributos'),
            'paga_sem_pagamento': (F.col('status') == 'PAGA') & F.col('data_pagamento').isNull(),
            'aberta_com_pagamento': (
                (F.col('status') == 'EM ABERTO') & F.col('data_pagamento').isNotNull()
            ),
            'pagamento_futuro': F.col('data_pagamento') > F.lit(referencia),
            'emissao_futura': F.col('data_emissao') > F.lit(referencia),
            'emissao_apos_vencimento': F.col('data_emissao') > F.col('data_vencimento'),
            'pagamento_antes_emissao': F.col('data_pagamento') < F.col('data_emissao'),
        }
    )
    regras.update({f'{c}_negativo': F.col(c) < 0 for c in DINHEIRO})
    _validar_regras(faturas, regras, 'faturas')
    _exigir_chave(faturas, ['id_fatura'], 'faturas')
    if not faturas.limit(1).count():
        raise ValueError('faturas: fonte vazia')

    cadastro = cadastro.select('id_uc', *DIMENSOES)
    base = (
        faturas.withColumn('competencia', F.to_date(F.concat('mes_referencia', F.lit('-01'))))
        .withColumn(
            'quantidade_faturas_uc_mes',
            F.count('*').over(Window.partitionBy('id_uc', 'mes_referencia')),
        )
        .join(cadastro.withColumn('_cadastro_encontrado', F.lit(True)), 'id_uc', 'left')
        .withColumn(
            'motivo_exclusao',
            F.when(F.col('flag_uc_sem_cadastro'), 'PENDENTE_CADASTRO_SILVER')
            .when(F.col('_cadastro_encontrado').isNull(), 'UC_AUSENTE_CADASTRO_SILVER')
            .when(F.col('quantidade_faturas_uc_mes') > 1, 'MULTIPLAS_FATURAS_UC_MES'),
        )
        .drop('_cadastro_encontrado')
        .withColumn('data_referencia', F.lit(referencia))
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
    )
    excluidas = base.filter(F.col('motivo_exclusao').isNotNull())
    elegiveis = base.filter(F.col('motivo_exclusao').isNull()).drop('motivo_exclusao')
    leitura_bloqueada = F.lit(False)
    for flag in FLAGS_LEITURAS:
        leitura_bloqueada = leitura_bloqueada | F.coalesce(F.col(flag), F.lit(True))
    volume = F.when(~leitura_bloqueada & (F.col('consumo_kwh') >= 0), F.col('consumo_kwh'))
    leitura = leituras.select(
        'id_uc',
        'mes_referencia',
        F.col('consumo_kwh').alias('consumo_kwh_silver'),
        volume.cast('decimal(18,2)').alias('volume_analise_kwh'),
        F.lit(True).alias('_leitura_encontrada'),
    )
    detalhe = (
        elegiveis.join(leitura, ['id_uc', 'mes_referencia'], 'left')
        .withColumn(
            'situacao_volume',
            F.when(F.col('_leitura_encontrada').isNull(), 'SEM_LEITURA')
            .when(F.col('volume_analise_kwh').isNull(), 'LEITURA_NAO_UTILIZAVEL')
            .when(F.col('volume_analise_kwh') == 0, 'ZERO_KWH')
            .otherwise('VOLUME_POSITIVO'),
        )
        .drop('_leitura_encontrada')
        .withColumn(
            'valor_fatura_paga',
            F.when(F.col('status') == 'PAGA', F.col('valor_total'))
            .otherwise(F.lit(0))
            .cast('decimal(18,2)'),
        )
        .withColumn(
            'valor_em_aberto',
            F.when(F.col('status') == 'EM ABERTO', F.col('valor_total'))
            .otherwise(F.lit(0))
            .cast('decimal(18,2)'),
        )
        .withColumn(
            'dias_atraso',
            F.when(
                F.col('status') == 'EM ABERTO',
                F.greatest(F.datediff('data_referencia', 'data_vencimento'), F.lit(0)),
            ).otherwise(F.greatest(F.datediff('data_pagamento', 'data_vencimento'), F.lit(0))),
        )
        .withColumn(
            'flag_vencida_em_aberto', (F.col('status') == 'EM ABERTO') & (F.col('dias_atraso') > 0)
        )
        .withColumn(
            'preco_efetivo_total_rs_kwh',
            F.when(
                F.col('volume_analise_kwh') > 0,
                F.col('valor_total') / F.col('volume_analise_kwh'),
            ).cast('decimal(28,10)'),
        )
    )
    return {
        'faturas': detalhe,
        'faturas_excluidas': excluidas,
        'faturamento_mensal': agregar_faturamento(detalhe),
    }


def agregar_faturamento(detalhe: DataFrame) -> DataFrame:
    positivo = F.col('volume_analise_kwh') > 0
    return (
        detalhe.groupBy('competencia', *DIMENSOES, 'data_referencia')
        .agg(
            F.count('*').alias('quantidade_faturas'),
            F.countDistinct('id_uc').alias('quantidade_ucs_faturadas'),
            *[_soma(c).alias(c) for c in DINHEIRO],
            _soma('valor_fatura_paga').alias('valor_faturas_pagas'),
            _soma('valor_em_aberto').alias('valor_em_aberto'),
            F.count(F.when(F.col('status') == 'EM ABERTO', 1)).alias('quantidade_em_aberto'),
            F.count(F.when(F.col('flag_vencida_em_aberto'), 1)).alias('quantidade_vencidas'),
            _soma(F.when(F.col('flag_vencida_em_aberto'), F.col('valor_total'))).alias(
                'valor_vencido'
            ),
            F.count(F.when(positivo, 1)).alias('quantidade_com_volume_positivo'),
            F.count(F.when(F.col('volume_analise_kwh').isNull(), 1)).alias('quantidade_sem_volume'),
            F.sum('volume_analise_kwh').cast('decimal(28,2)').alias('volume_analise_kwh'),
            _soma(F.when(positivo, F.col('valor_total'))).alias('receita_com_volume_positivo'),
            _soma(F.when(~F.coalesce(positivo, F.lit(False)), F.col('valor_total'))).alias(
                'receita_sem_volume_positivo'
            ),
        )
        .withColumn(
            'cobertura_volume_pct',
            F.round(
                F.col('quantidade_com_volume_positivo') * F.lit(100) / F.col('quantidade_faturas'),
                2,
            ).cast('decimal(5,2)'),
        )
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
    )


def comparar_periodos(
    mensal: DataFrame,
    inicio_base: str,
    fim_base: str,
    inicio_atual: str,
    fim_atual: str,
) -> DataFrame:
    """Compara intervalos mensais fechados e de mesma duração, por local/classe.

    Efeito volume = (Q1-Q0)*P0; preço = delta pareado - efeito volume.
    Sem preço na base, usa o preço atual para entradas. Saídas usam o preço base.
    A receita sem volume positivo gera um efeito separado, preservando o delta total.
    """
    datas = [date.fromisoformat(s) for s in [inicio_base, fim_base, inicio_atual, fim_atual]]
    if any(d.day != 1 for d in datas):
        raise ValueError('Limites dos períodos devem ser o primeiro dia do mês')
    b0, b1, a0, a1 = datas

    def meses(x, y):
        return (y.year - x.year) * 12 + y.month - x.month + 1

    if b1 < b0 or a1 < a0 or meses(b0, b1) != meses(a0, a1):
        raise ValueError('Períodos precisam ter a mesma duração positiva')
    disponiveis = {r[0] for r in mensal.select('competencia').distinct().collect()}
    for inicio, fim in [(b0, b1), (a0, a1)]:
        for deslocamento in range(meses(inicio, fim)):
            esperado = deslocar_mes(inicio, deslocamento)
            if esperado not in disponiveis:
                raise ValueError(f'Competência ausente no período: {esperado}')

    def resumir(inicio, fim, sufixo):
        return (
            mensal.filter(F.col('competencia').between(inicio, fim))
            .groupBy(*DIMENSOES)
            .agg(
                _soma('valor_total').alias(f'receita_{sufixo}'),
                _soma('receita_com_volume_positivo').alias(f'receita_pareada_{sufixo}'),
                _soma('receita_sem_volume_positivo').alias(f'receita_sem_volume_{sufixo}'),
                _soma('volume_analise_kwh').alias(f'volume_{sufixo}_kwh'),
                F.sum('quantidade_faturas').alias(f'quantidade_faturas_{sufixo}'),
                F.sum('quantidade_com_volume_positivo').alias(f'quantidade_com_volume_{sufixo}'),
            )
        )

    comparacao = resumir(b0, b1, 'base').join(resumir(a0, a1, 'atual'), DIMENSOES, 'full')
    medidas = [c for c in comparacao.columns if c not in DIMENSOES]
    comparacao = comparacao.fillna(0, subset=medidas)
    p_base = F.when(
        F.col('volume_base_kwh') > 0, F.col('receita_pareada_base') / F.col('volume_base_kwh')
    )
    p_atual = F.when(
        F.col('volume_atual_kwh') > 0, F.col('receita_pareada_atual') / F.col('volume_atual_kwh')
    )
    preco_referencia = F.coalesce(p_base, p_atual, F.lit(0)).cast('decimal(28,10)')
    return (
        comparacao.withColumn('variacao_receita', F.col('receita_atual') - F.col('receita_base'))
        .withColumn(
            'variacao_receita_pct',
            F.when(
                F.col('receita_base') != 0,
                F.round(F.col('variacao_receita') * 100 / F.col('receita_base'), 2),
            ),
        )
        .withColumn(
            'efeito_volume',
            F.round(
                (F.col('volume_atual_kwh') - F.col('volume_base_kwh')) * preco_referencia,
                2,
            ).cast('decimal(28,2)'),
        )
        .withColumn(
            'efeito_preco_efetivo',
            (
                F.col('receita_pareada_atual')
                - F.col('receita_pareada_base')
                - F.col('efeito_volume')
            ).cast('decimal(28,2)'),
        )
        .withColumn(
            'efeito_receita_sem_volume',
            F.col('receita_sem_volume_atual') - F.col('receita_sem_volume_base'),
        )
        .withColumn('inicio_base', F.lit(b0))
        .withColumn('fim_base', F.lit(b1))
        .withColumn('inicio_atual', F.lit(a0))
        .withColumn('fim_atual', F.lit(a1))
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
    )


def validar_reconciliacao(fonte: DataFrame, tabelas: dict[str, DataFrame]) -> None:
    """Confere a partição da fonte e as somas mensais antes de qualquer escrita."""
    detalhe = tabelas['faturas']
    excluidas = tabelas['faturas_excluidas']
    reunidas = detalhe.select(*COLUNAS_FATURAS).unionByName(excluidas.select(*COLUNAS_FATURAS))
    for a, b in [
        (fonte.select(*COLUNAS_FATURAS), reunidas),
        (reunidas, fonte.select(*COLUNAS_FATURAS)),
    ]:
        if a.exceptAll(b).limit(1).count():
            raise ValueError('Detalhe + exclusões divergem da fonte Silver')
    chaves = ['competencia', *DIMENSOES, 'data_referencia']
    esperado = detalhe.groupBy(*chaves).agg(
        F.count('*').alias('quantidade_faturas'),
        *[_soma(c).alias(c) for c in DINHEIRO],
    )
    obtido = tabelas['faturamento_mensal'].select(*esperado.columns)
    if esperado.exceptAll(obtido).limit(1).count() or obtido.exceptAll(esperado).limit(1).count():
        raise ValueError('Agregado mensal diverge do detalhe')
    _validar_regras(
        tabelas['faturamento_mensal'],
        {
            'receita_nao_reconciliada': (
                F.col('valor_total')
                != F.col('receita_com_volume_positivo') + F.col('receita_sem_volume_positivo')
            ),
            'status_nao_reconciliado': (
                F.col('valor_total') != F.col('valor_faturas_pagas') + F.col('valor_em_aberto')
            ),
        },
        'faturamento_mensal',
    )


def exportar_csv(tabelas: dict[str, DataFrame], diretorio: str, metadados: dict) -> Path:
    """Exporta partes CSV por tabela e publica o manifesto somente ao concluir.

    O diretório de lote deve ser novo. Em caso de falha, não há manifesto final;
    o consumidor deve ignorar esses lotes incompletos.
    """
    pasta_lote = Path(diretorio)
    pasta_lote.mkdir(parents=True, exist_ok=False)
    manifesto = {**metadados, 'tipo': 'gold_faturas', 'versao_regras': VERSAO_REGRAS, 'tabelas': {}}
    controles = [
        *DINHEIRO,
        'valor_fatura_paga',
        'valor_faturas_pagas',
        'valor_em_aberto',
        'volume_analise_kwh',
        'receita_com_volume_positivo',
        'receita_sem_volume_positivo',
        'receita_base',
        'receita_atual',
        'variacao_receita',
        'efeito_volume',
        'efeito_preco_efetivo',
        'efeito_receita_sem_volume',
    ]
    for nome, df in tabelas.items():
        if not nome.isidentifier():
            raise ValueError(f'Nome de tabela inválido: {nome}')
        pasta_tabela = pasta_lote / nome
        df.write.mode('errorifexists').option('header', 'true').option('escape', '"').option(
            'dateFormat', 'yyyy-MM-dd'
        ).option('nullValue', '').option('encoding', 'UTF-8').option(
            'timestampFormat', "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"
        ).csv(str(pasta_tabela))
        partes = sorted(pasta_tabela.glob('part-*.csv'))
        hashes_conferidos = conferir_arquivos_csv(df, partes)
        arquivos = []
        for arquivo in partes:
            digest = hash_arquivo(arquivo)
            if digest != hashes_conferidos[str(arquivo)]:
                raise ValueError(f'CSV mudou após a conferência: {arquivo}')
            arquivos.append(
                {
                    'arquivo': str(arquivo.relative_to(pasta_lote)),
                    'sha256': digest,
                }
            )
        if not arquivos:
            raise ValueError(f'Nenhum CSV exportado: {nome}')
        colunas_controle = [c for c in controles if c in df.columns]
        totais = (
            df.agg(*[F.coalesce(F.sum(c), F.lit(0)).alias(c) for c in colunas_controle])
            .first()
            .asDict()
            if colunas_controle
            else {}
        )
        manifesto['tabelas'][nome] = {
            'registros': df.count(),
            'colunas': [{'nome': c.name, 'tipo': c.dataType.simpleString()} for c in df.schema],
            'totais_controle': {c: str(v) for c, v in totais.items()},
            'arquivos': arquivos,
        }
    for tabela in manifesto['tabelas'].values():
        for parte in tabela['arquivos']:
            if hash_arquivo(pasta_lote / parte['arquivo']) != parte['sha256']:
                raise ValueError('CSV mudou antes da confirmação do manifesto')
    temporario = pasta_lote / 'manifest.json.tmp'
    temporario.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(pasta_lote / 'manifest.json')
    return pasta_lote


def publicar_delta(spark, tabelas, destinos, validar):
    """Publica e confere as tabelas; recupera os destinos afetados na falha.

    Exige exclusividade de escrita durante publicação e recuperação. RESTORE é
    compensação, sem isolamento/atomicidade entre tabelas para leitores externos.
    """
    if not tabelas or set(tabelas) != set(destinos):
        raise ValueError('Publicação exige tabelas e destinos correspondentes não vazios')
    for destino in destinos.values():
        schema = '.'.join(qualificar(destino).split('.')[:2])
        validar_destinos(schema, [destino], [])
    anteriores = {}
    for nome in tabelas:
        destino = destinos[nome]
        if spark.catalog.tableExists(destino):
            detalhe = spark.sql(f'DESCRIBE DETAIL {destino}').first()
            if detalhe['format'] != 'delta':
                raise ValueError(f'O destino precisa ser Delta: {destino}')
            anteriores[nome] = spark.sql(f'DESCRIBE HISTORY {destino} LIMIT 1').first()['version']
        else:
            anteriores[nome] = None

    afetadas = []
    persistidas, versoes = {}, {}
    try:
        for nome, df in tabelas.items():
            destino = destinos[nome]
            # Incluir antes da escrita: ela pode efetivar o commit e depois falhar.
            afetadas.append(nome)
            (
                df.write.format('delta')
                .mode('overwrite')
                .option('overwriteSchema', 'true')
                .saveAsTable(destino)
            )
            versao = spark.sql(f'DESCRIBE HISTORY {destino} LIMIT 1').first()['version']
            persistido = spark.read.option('versionAsOf', versao).table(destino)
            esperado = [(c.name, c.dataType.simpleString()) for c in df.schema]
            gravado = [(c.name, c.dataType.simpleString()) for c in persistido.schema]
            if esperado != gravado:
                raise ValueError(f'Schema persistido divergente: {destino}')
            if (
                df.exceptAll(persistido).limit(1).count()
                or persistido.exceptAll(df).limit(1).count()
            ):
                raise ValueError(f'Conteúdo persistido divergente: {destino}')
            persistidas[nome] = persistido
            versoes[nome] = {'tabela': destino, 'versao_delta': versao}
        validar(persistidas)
    except Exception as erro:
        falhas = []
        for nome in reversed(afetadas):
            destino = destinos[nome]
            try:
                versao = anteriores[nome]
                if versao is None:
                    spark.sql(f'DROP TABLE IF EXISTS {destino}')
                else:
                    spark.sql(f'RESTORE TABLE {destino} TO VERSION AS OF {versao}')
            except Exception as falha:
                falhas.append(RuntimeError(f'Falha ao recuperar {destino}: {falha}'))
        if falhas:
            raise ExceptionGroup(
                'Publicação falhou e a recuperação ficou incompleta', [erro, *falhas]
            ) from erro
        raise
    return persistidas, versoes


def deslocar_mes(data, meses):
    indice = data.year * 12 + data.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def qualificar(nome, partes=3):
    segmentos = nome.split('.')
    if len(segmentos) != partes or any(
        not re.fullmatch(r'(?:[A-Za-z0-9_-]+|`[A-Za-z0-9_-]+`)', segmento) for segmento in segmentos
    ):
        raise ValueError(f'Identificador inválido: {nome}')
    return '.'.join('`' + segmento.strip('`') + '`' for segmento in segmentos)


def normalizar_identificador(nome, partes=3):
    return qualificar(nome, partes).lower()


def validar_destinos(schema, destinos, fontes):
    if normalizar_identificador(schema, 2).split('.')[1] in {
        '`bronze`',
        '`silver`',
        '`default`',
        '`silver_revisoes`',
    }:
        raise ValueError('O destino deve ser um schema próprio da Gold')
    if {normalizar_identificador(t) for t in destinos} & {
        normalizar_identificador(t) for t in fontes
    }:
        raise ValueError('Uma tabela de destino coincide com uma fonte')


def ler_snapshot_delta(spark, tabela, versao=None):
    tabela = qualificar(tabela)
    detalhe = spark.sql(f'DESCRIBE DETAIL {tabela}').first()
    if detalhe['format'] != 'delta':
        raise ValueError(f'A fonte precisa ser Delta: {tabela}')
    if versao is None:
        versao = spark.sql(f'DESCRIBE HISTORY {tabela} LIMIT 1').first()['version']
    if type(versao) is not int or versao < 0:
        raise ValueError('Versão Delta inválida')
    return spark.read.option('versionAsOf', versao).table(tabela), {
        'tabela': tabela,
        'id_delta': detalhe['id'],
        'versao_delta': versao,
    }


def validar_marcador_silver(linhas, principal, pendentes):
    esperados = {normalizar_identificador(t) for t in (principal, pendentes)}
    if len(esperados) != 2 or len(linhas) != 2:
        raise ValueError('Publicação Silver ausente ou incompleta')
    try:
        ids = {r['id_execucao'] for r in linhas}
        datas = {r['confirmado_em'] for r in linhas}
        destinos = {normalizar_identificador(r['destino']) for r in linhas}
        fontes = {normalizar_identificador(r['fonte']) for r in linhas}
        if (
            len(ids) != 1
            or not re.fullmatch(r'[0-9a-f]{32}', next(iter(ids)))
            or len(datas) != 1
            or None in datas
            or destinos != esperados
            or len(fontes) != 2
        ):
            raise ValueError('Identidade da publicação Silver incoerente')
        for r in linhas:
            for campo in ('versao_fonte', 'versao_destino'):
                if type(r[campo]) is not int or r[campo] < 0:
                    raise ValueError('Versão da publicação Silver inválida')
            destino = normalizar_identificador(r['destino']).split('.')
            fonte = normalizar_identificador(r['fonte']).split('.')
            nome = destino[-1].strip('`')
            if (
                fonte[:2] != [destino[0], '`silver_revisoes`']
                or fonte[-1].strip('`') != f'{nome}_revisao_{r["id_execucao"]}'
            ):
                raise ValueError('Revisão Silver fora do protocolo de publicação')
    except (KeyError, TypeError, StopIteration) as erro:
        raise ValueError('Marcador Silver inválido') from erro
    return linhas


def ler_publicacao_silver(spark, marcador, principal, pendentes):
    # Uma única ação materializa o marcador. Republicações não mudam este par.
    linhas = spark.table(qualificar(marcador)).collect()
    validar_marcador_silver(linhas, principal, pendentes)
    quadros, fontes = {}, {}
    for r in linhas:
        chave = normalizar_identificador(r['destino'])
        quadros[chave], fontes[chave] = ler_snapshot_delta(spark, r['fonte'], r['versao_fonte'])
    return (
        quadros[normalizar_identificador(principal)],
        quadros[normalizar_identificador(pendentes)],
        {
            'marcador': qualificar(marcador),
            'id_execucao': linhas[0]['id_execucao'],
            'confirmado_em': str(linhas[0]['confirmado_em']),
            'snapshots': fontes,
        },
    )


@contextmanager
def persistir_quadros(quadros):
    """Persistência seletiva MEMORY_AND_DISK, sempre liberada inclusive na falha."""
    from pyspark import StorageLevel

    persistidos = []
    try:
        for df in quadros:
            if not df.is_cached:
                df.persist(StorageLevel.MEMORY_AND_DISK)
                persistidos.append(df)
        yield
    finally:
        for df in reversed(persistidos):
            df.unpersist()


def publicar_revisoes(spark, tabelas, schema, validar, metadados, antes_confirmar=lambda: None):
    """Revisões exclusivas; só o overwrite do marcador promove o conjunto.

    Escritor único obrigatório (job + ACL). Após interrupção, ler o marcador:
    revisões não referidas são candidatas abandonadas, nunca publicação parcial.
    Não tocar nas revisões após tentar confirmar: o commit pode ter ocorrido.
    """
    validar_destinos(schema, [], [])
    if not tabelas:
        raise ValueError('Publicação vazia')
    schema = qualificar(schema, 2)
    execucao = uuid4().hex
    destinos = {n: f'{schema}.`tb_gold_faturas_{n}_revisao_{execucao}`' for n in tabelas}
    fontes_consumidas = [v['tabela'] for v in metadados.get('fontes', {}).values()]
    marcador_silver = metadados.get('publicacao_silver', {}).get('marcador')
    if marcador_silver:
        fontes_consumidas.append(marcador_silver)
    validar_destinos(
        schema, [*destinos.values(), f'{schema}.`tb_gold_faturas_publicacao`'], fontes_consumidas
    )
    for n in tabelas:
        if not n.isidentifier():
            raise ValueError(f'Nome inválido: {n}')
    if any(spark.catalog.tableExists(t) for t in destinos.values()):
        raise ValueError('Revisão já existe; UUID nunca pode ser reutilizado')
    # Mantém a compensação RESTORE/DROP para exceções capturadas nas candidatas.
    persistidas, versoes = publicar_delta(spark, tabelas, destinos, validar)
    antes_confirmar()
    linhas = [
        (
            execucao,
            n,
            v['tabela'],
            int(v['versao_delta']),
            json.dumps(metadados, ensure_ascii=False, sort_keys=True),
        )
        for n, v in versoes.items()
    ]
    marcador = spark.createDataFrame(
        linhas, 'id_execucao string, nome string, fonte string, versao_fonte long, metadados string'
    )
    (
        marcador.write.format('delta')
        .mode('overwrite')
        .saveAsTable(f'{schema}.`tb_gold_faturas_publicacao`')
    )
    return persistidas, versoes


def ler_publicacao_gold(spark, schema, nomes):
    schema = qualificar(schema, 2)
    linhas = spark.table(f'{schema}.`tb_gold_faturas_publicacao`').collect()
    if (
        not nomes
        or len(linhas) != len(nomes)
        or {r['nome'] for r in linhas} != set(nomes)
        or len({r['id_execucao'] for r in linhas}) != 1
        or len({r['metadados'] for r in linhas}) != 1
    ):
        raise ValueError('Publicação Gold incompleta ou incoerente')
    execucao = linhas[0]['id_execucao']
    if not re.fullmatch(r'[0-9a-f]{32}', execucao):
        raise ValueError('Identidade Gold inválida')
    for r in linhas:
        esperado = f'{schema}.`tb_gold_faturas_{r["nome"]}_revisao_{execucao}`'
        if (
            normalizar_identificador(r['fonte']) != normalizar_identificador(esperado)
            or type(r['versao_fonte']) is not int
            or r['versao_fonte'] < 0
        ):
            raise ValueError('Snapshot Gold inválido')
    return {
        r['nome']: ler_snapshot_delta(spark, r['fonte'], r['versao_fonte'])[0] for r in linhas
    }, linhas


def limpar_revisoes_gold(spark, schema, nomes):
    """Manutenção explícita sob a mesma exclusividade do produtor; janela de 7 dias."""
    from datetime import timedelta
    from delta.tables import DeltaTable

    validar_destinos(schema, [], [])
    schema = qualificar(schema, 2)
    _, linhas = ler_publicacao_gold(spark, schema, nomes)
    protegidas = {normalizar_identificador(r['fonte']) for r in linhas}
    padrao = (
        r'tb_gold_faturas_(' + '|'.join(re.escape(n) for n in nomes) + r')_revisao_[0-9a-f]{32}'
    )
    candidatas = [
        f'{schema}.`{r["tableName"]}`'
        for r in spark.sql(f'SHOW TABLES IN {schema}').collect()
        if re.fullmatch(padrao, r['tableName'])
    ]
    agora = datetime.now(timezone.utc)
    retiradas = [(t, agora) for t in candidatas if normalizar_identificador(t) not in protegidas]
    registro = f'{schema}.`tb_gold_faturas_retencao`'
    spark.sql(
        f'CREATE TABLE IF NOT EXISTS {registro} (nome STRING, aposentada_em TIMESTAMP) USING DELTA'
    )
    if retiradas:
        novas = spark.createDataFrame(retiradas, 'nome string, aposentada_em timestamp')
        (
            DeltaTable.forName(spark, registro)
            .alias('r')
            .merge(novas.alias('n'), 'r.nome = n.nome')
            .whenNotMatchedInsertAll()
            .execute()
        )
    for r in spark.table(registro).collect():
        aposentada_em = r['aposentada_em']
        if aposentada_em is not None and aposentada_em.tzinfo is None:
            aposentada_em = aposentada_em.replace(tzinfo=timezone.utc)
        if (
            r['nome'] in candidatas
            and normalizar_identificador(r['nome']) not in protegidas
            and aposentada_em is not None
            and aposentada_em < agora - timedelta(days=7)
        ):
            spark.sql(f'DROP TABLE {qualificar(r["nome"])}')


def hash_arquivo(arquivo):
    with Path(arquivo).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def conferir_arquivos_csv(esperado, arquivos):
    """Confere os bytes entregues como multiconjunto, além de cabeçalho/contagem.

    Não confia em _committed_*; uma parte órfã ou troca de valores de mesmo total
    é detectada pelo exceptAll. Arquivos vazios/corrompidos também bloqueiam.
    """
    import csv

    if not arquivos:
        raise ValueError('Nenhum CSV exportado')
    hashes = {str(p): hash_arquivo(p) for p in arquivos}
    for arquivo in arquivos:
        with Path(arquivo).open(newline='', encoding='utf-8') as stream:
            leitor = csv.reader(stream, strict=True)
            if next(leitor, None) != esperado.columns:
                raise ValueError(f'Cabeçalho CSV divergente: {arquivo}')
            for linha in leitor:
                if len(linha) != len(esperado.columns):
                    raise ValueError(f'Linha CSV divergente: {arquivo}')
    entregue = (
        esperado.sparkSession.read.schema(esperado.schema)
        .option('header', 'true')
        .option('escape', '"')
        .option('mode', 'FAILFAST')
        .option('multiLine', 'true')
        .option('dateFormat', 'yyyy-MM-dd')
        .option('nullValue', '')
        .option('timestampFormat', "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX")
        .csv([str(p) for p in arquivos])
    )
    if (
        esperado.exceptAll(entregue).limit(1).count()
        or entregue.exceptAll(esperado).limit(1).count()
    ):
        raise ValueError('Conteúdo CSV entregue diverge do DataFrame conferido')
    if hashes != {str(p): hash_arquivo(p) for p in arquivos}:
        raise ValueError('CSV mudou durante a conferência')
    return hashes
