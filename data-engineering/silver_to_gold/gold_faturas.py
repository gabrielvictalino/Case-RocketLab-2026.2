# Databricks notebook source
"""Transformações e exportação da Gold de faturas, sem dependência de dbutils."""

from datetime import date
import hashlib
import json
from pathlib import Path

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

VERSAO_REGRAS = 'GOLD_FATURAS_V1'
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


def construir_faturas(
    faturas: DataFrame,
    cadastro: DataFrame,
    leituras: DataFrame,
    data_referencia: str,
) -> dict[str, DataFrame]:
    """Retorna detalhe elegível, exclusões reconciliáveis e resumo mensal.

    Faturas inclui as duas saídas Silver, principal e pendentes, via unionByName.
    A data é a data de referência do retrato de status da extração, não hoje.
    """
    referencia = date.fromisoformat(data_referencia)
    if referencia.isoformat() != data_referencia:
        raise ValueError('data_referencia deve usar AAAA-MM-DD')
    _exigir_colunas(faturas, COLUNAS_FATURAS, 'faturas')
    _exigir_colunas(cadastro, ['id_uc', *DIMENSOES], 'cadastro')
    _exigir_colunas(
        leituras, ['id_uc', 'mes_referencia', 'consumo_kwh', *FLAGS_LEITURAS], 'leituras'
    )
    for flag in FLAGS_LEITURAS:
        if leituras.schema[flag].dataType.simpleString() != 'boolean':
            raise ValueError(f'leituras: {flag} precisa ser boolean')
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
    if leituras.schema['consumo_kwh'].dataType.typeName() not in {
        'integer',
        'long',
        'short',
        'decimal',
    }:
        raise ValueError('leituras: consumo_kwh precisa ser inteiro ou decimal')
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
            'competencia_invalida': ~F.col('mes_referencia').rlike(
                r'^[1-9][0-9]{3}-(0[1-9]|1[0-2])$'
            ),
            'status_invalido': ~F.col('status').isin('PAGA', 'EM ABERTO'),
            'bandeira_invalida': ~F.col('bandeira_tarifaria').isin(
                'Verde', 'Amarela', 'Vermelha P1', 'Vermelha P2'
            ),
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
            'competencia_invalida': ~F.col('mes_referencia').rlike(
                r'^[1-9][0-9]{3}-(0[1-9]|1[0-2])$'
            ),
        },
        'leituras',
    )

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
            ),
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
            indice = inicio.year * 12 + inicio.month - 1 + deslocamento
            esperado = date(indice // 12, indice % 12 + 1, 1)
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
        df.write.mode('errorifexists').option('header', 'true').option(
            'dateFormat', 'yyyy-MM-dd'
        ).option('nullValue', '').option('encoding', 'UTF-8').csv(str(pasta_tabela))
        arquivos = []
        for arquivo in sorted(pasta_tabela.glob('part-*.csv')):
            digest = hashlib.sha256()
            with arquivo.open('rb') as stream:
                for bloco in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(bloco)
            arquivos.append(
                {
                    'arquivo': str(arquivo.relative_to(pasta_lote)),
                    'sha256': digest.hexdigest(),
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
    temporario = pasta_lote / 'manifest.json.tmp'
    temporario.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(pasta_lote / 'manifest.json')
    return pasta_lote


def publicar_delta(spark, tabelas, destinos, validar):
    """Publica e confere as tabelas; recupera os destinos afetados na falha.

    Exige exclusividade de escrita durante publicação e recuperação. RESTORE é
    compensação, sem isolamento/atomicidade entre tabelas para leitores externos.
    """
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
