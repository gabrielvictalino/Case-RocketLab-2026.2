"""Transformações, validações e exportação da Gold de geração distribuída."""

import hashlib
import json
from datetime import date
from pathlib import Path

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, LongType

VERSAO_REGRAS = 'GOLD_GD_V1'
PADRAO_ID_UC = r'^UC\d{6}$'
PADRAO_MES = r'^[1-9][0-9]{3}-(0[1-9]|1[0-2])$'
MODALIDADES_VALIDAS = ['PROPRIA_UC', 'AUTOCONSUMO_REMOTO', 'COMPARTILHADA']
TIPOS_LEITURA_VALIDOS = ['REAL', 'ESTIMADA']
DIMENSOES_UC = ['municipio', 'bairro', 'classe']
FLAGS_LEITURAS_BLOQUEIO = [
    'flag_troca_medidor',
    'flag_sem_leitura_anterior',
    'flag_sinal_nao_confirmado',
]
COLUNAS_GD = [
    'id_uc',
    'potencia_kwp',
    'fl_correcao_escala',
    'energia_injetada_kwh_media_mensal',
    'kwh_por_kwp_mes',
    'data_conexao',
    'fl_data_inconsistente',
    'modalidade',
    'modalidade_origem',
    'fl_deduplicado',
]
COLUNAS_CADASTRO = [
    'id_uc',
    'municipio',
    'bairro',
    'classe',
    'subgrupo_tarifario',
    'alimentador',
    'data_ligacao',
    'status',
]
COLUNAS_LEITURAS = [
    'id_uc',
    'mes_referencia',
    'consumo_kwh',
    'tipo_leitura',
    'flag_sinal_corrigido',
    *FLAGS_LEITURAS_BLOQUEIO,
]


def _exigir_colunas(df: DataFrame, colunas: list[str], nome: str) -> None:
    ausentes = set(colunas) - set(df.columns)
    if ausentes:
        raise ValueError(f'{nome}: colunas ausentes: {sorted(ausentes)}')


def _validar_regras(df: DataFrame, regras: dict, nome: str) -> None:
    contagens = (
        df.agg(*[F.count(F.when(condicao, 1)).alias(regra) for regra, condicao in regras.items()])
        .first()
        .asDict()
    )
    falhas = {regra: n for regra, n in contagens.items() if n}
    if falhas:
        raise ValueError(f'{nome}: {falhas}')


def _exigir_chave(df: DataFrame, colunas: list[str], nome: str) -> None:
    if df.groupBy(*colunas).count().filter('count > 1').limit(1).count():
        raise ValueError(f'{nome}: chave duplicada {colunas}')


def _soma_decimal(coluna, escala: int = 2):
    return F.coalesce(F.sum(coluna), F.lit(0)).cast(DecimalType(28, escala))


def validar_fontes(gd_silver: DataFrame, cadastro_silver: DataFrame, leituras_silver: DataFrame):
    """Valida contrato estrutural, tipos, chaves e domínios das três Silvers."""
    _exigir_colunas(gd_silver, COLUNAS_GD, 'gd_silver')
    _exigir_colunas(cadastro_silver, COLUNAS_CADASTRO, 'cadastro_silver')
    _exigir_colunas(leituras_silver, COLUNAS_LEITURAS, 'leituras_silver')

    tipos_gd = {
        'id_uc': 'string',
        'potencia_kwp': 'decimal(10,2)',
        'fl_correcao_escala': 'boolean',
        'energia_injetada_kwh_media_mensal': 'decimal(10,2)',
        'kwh_por_kwp_mes': 'decimal(10,2)',
        'data_conexao': 'date',
        'fl_data_inconsistente': 'boolean',
        'modalidade': 'string',
        'modalidade_origem': 'string',
        'fl_deduplicado': 'boolean',
    }
    for col_name, esperado in tipos_gd.items():
        obtido = gd_silver.schema[col_name].dataType.simpleString()
        if obtido != esperado:
            raise ValueError(f'gd_silver: {col_name} precisa ser {esperado} (obtido: {obtido})')

    for col_name in ['id_uc', 'municipio', 'bairro', 'classe', 'subgrupo_tarifario', 'alimentador']:
        if cadastro_silver.schema[col_name].dataType.simpleString() != 'string':
            raise ValueError(f'cadastro_silver: {col_name} precisa ser string')
    if cadastro_silver.schema['data_ligacao'].dataType.simpleString() != 'date':
        raise ValueError('cadastro_silver: data_ligacao precisa ser date')

    if leituras_silver.schema['consumo_kwh'].dataType.typeName() not in {
        'integer',
        'long',
        'short',
        'decimal',
    }:
        raise ValueError('leituras_silver: consumo_kwh precisa ser inteiro ou decimal')
    for flag in ['flag_sinal_corrigido', *FLAGS_LEITURAS_BLOQUEIO]:
        if leituras_silver.schema[flag].dataType.simpleString() != 'boolean':
            raise ValueError(f'leituras_silver: {flag} precisa ser boolean')

    if not gd_silver.limit(1).count():
        raise ValueError('gd_silver: fonte vazia')
    if not cadastro_silver.limit(1).count():
        raise ValueError('cadastro_silver: fonte vazia')
    if not leituras_silver.limit(1).count():
        raise ValueError('leituras_silver: fonte vazia')

    _exigir_chave(gd_silver, ['id_uc'], 'gd_silver')
    _exigir_chave(cadastro_silver, ['id_uc'], 'cadastro_silver')
    _exigir_chave(leituras_silver, ['id_uc', 'mes_referencia'], 'leituras_silver')

    _validar_regras(
        gd_silver,
        {
            'id_uc_invalido': F.col('id_uc').isNull() | ~F.col('id_uc').rlike(PADRAO_ID_UC),
            'potencia_invalida': F.col('potencia_kwp').isNull() | (F.col('potencia_kwp') <= 0),
            'energia_invalida': (
                F.col('energia_injetada_kwh_media_mensal').isNull()
                | (F.col('energia_injetada_kwh_media_mensal') <= 0)
            ),
            'rendimento_invalido': (
                F.col('kwh_por_kwp_mes').isNull() | (F.col('kwh_por_kwp_mes') <= 0)
            ),
            'data_conexao_nula': F.col('data_conexao').isNull(),
            'modalidade_invalida': (
                F.col('modalidade').isNull() | ~F.col('modalidade').isin(MODALIDADES_VALIDAS)
            ),
            'flags_nulas': (
                F.col('fl_correcao_escala').isNull()
                | F.col('fl_data_inconsistente').isNull()
                | F.col('fl_deduplicado').isNull()
            ),
        },
        'gd_silver',
    )

    _validar_regras(
        cadastro_silver,
        {
            f'{c}_ausente': F.col(c).isNull() | (F.trim(F.col(c)) == '')
            for c in ['id_uc', *DIMENSOES_UC, 'subgrupo_tarifario', 'alimentador', 'status']
        },
        'cadastro_silver',
    )

    _validar_regras(
        leituras_silver,
        {
            'chave_nula': F.col('id_uc').isNull() | F.col('mes_referencia').isNull(),
            'competencia_invalida': ~F.col('mes_referencia').rlike(PADRAO_MES),
            'consumo_nulo': F.col('consumo_kwh').isNull(),
            'tipo_leitura_invalido': (
                F.col('tipo_leitura').isNull()
                | ~F.col('tipo_leitura').isin(TIPOS_LEITURA_VALIDOS)
            ),
        },
        'leituras_silver',
    )

    orfas_cadastro = (
        gd_silver.select('id_uc')
        .join(cadastro_silver.select('id_uc'), 'id_uc', 'left_anti')
        .limit(1)
        .count()
    )
    if orfas_cadastro:
        raise ValueError('gd_silver: há UCs ausentes em cadastro_silver')


def construir_gold_gd(
    gd_silver: DataFrame,
    cadastro_silver: DataFrame,
    leituras_silver: DataFrame,
) -> dict[str, DataFrame]:
    """Constrói as 4 tabelas Gold de geração distribuída a partir das 3 Silvers."""
    validar_fontes(gd_silver, cadastro_silver, leituras_silver)

    # 1. Tabela de contrato do portal: gd_uc (1 linha por UC com GD)
    df_gd_uc = gd_silver.select(
        F.col('id_uc'),
        F.col('potencia_kwp').cast(DecimalType(18, 2)).alias('potencia_kw'),
        F.col('data_conexao'),
    ).orderBy('id_uc')

    # 2. Contexto cadastral (_ctx) e Lookup (_lk) seguindo taxonomia Star Schema
    df_cadastro_ctx = cadastro_silver.select(
        'id_uc',
        'municipio',
        'bairro',
        'classe',
        'subgrupo_tarifario',
        'alimentador',
        'data_ligacao',
        'status',
    )
    w_sk = Window.orderBy('id_uc')
    df_gd_base = (
        gd_silver.join(df_cadastro_ctx, 'id_uc', 'inner')
        .withColumn('gd_uc_sk', F.row_number().over(w_sk).cast(LongType()))
        .withColumn('competencia_conexao', F.trunc(F.col('data_conexao'), 'month'))
        .withColumn(
            'faixa_potencia',
            F.when(F.col('potencia_kwp') <= F.lit(5), F.lit('ATE_5_KWP'))
            .when(F.col('potencia_kwp') <= F.lit(10), F.lit('DE_5_A_10_KWP'))
            .when(F.col('potencia_kwp') <= F.lit(25), F.lit('DE_10_A_25_KWP'))
            .otherwise(F.lit('ACIMA_25_KWP')),
        )
    )
    df_gd_lk = df_gd_base.select(
        'gd_uc_sk',
        'id_uc',
        'municipio',
        'bairro',
        'classe',
        'subgrupo_tarifario',
        'alimentador',
        'modalidade',
        'faixa_potencia',
        'potencia_kwp',
        'energia_injetada_kwh_media_mensal',
        'data_conexao',
        'competencia_conexao',
    )

    # 3. Leituras das UCs com GD: consumo original vs consumo analítico
    leitura_bloqueada = F.lit(False)
    for flag in FLAGS_LEITURAS_BLOQUEIO:
        leitura_bloqueada = leitura_bloqueada | F.coalesce(F.col(flag), F.lit(True))

    volume_utilizavel = F.when(
        ~leitura_bloqueada & (F.col('consumo_kwh') >= 0),
        F.col('consumo_kwh').cast(DecimalType(18, 2)),
    )
    situacao_leitura = (
        F.when(F.col('flag_troca_medidor'), F.lit('TROCA_MEDIDOR'))
        .when(F.col('flag_sem_leitura_anterior'), F.lit('SEM_LEITURA_ANTERIOR'))
        .when(F.col('flag_sinal_nao_confirmado'), F.lit('SINAL_NAO_CONFIRMADO'))
        .when(F.col('consumo_kwh') < 0, F.lit('NEGATIVO_NAO_CLASSIFICADO'))
        .when(F.col('consumo_kwh') == 0, F.lit('ZERO_KWH'))
        .otherwise(F.lit('VOLUME_POSITIVO'))
    )

    df_leituras_gd = (
        leituras_silver.join(df_gd_lk, 'id_uc', 'inner')
        .withColumn('competencia', F.to_date(F.concat(F.col('mes_referencia'), F.lit('-01'))))
        .withColumn(
            'flag_gd_ativa_competencia',
            F.col('competencia') >= F.col('competencia_conexao'),
        )
        .withColumn(
            'fase_gd',
            F.when(F.col('flag_gd_ativa_competencia'), F.lit('APOS_CONEXAO')).otherwise(
                F.lit('ANTES_CONEXAO')
            ),
        )
        .withColumn('consumo_kwh_silver', F.col('consumo_kwh').cast(DecimalType(18, 2)))
        .withColumn('volume_analise_kwh', volume_utilizavel)
        .withColumn('situacao_volume', situacao_leitura)
    )

    # Mediana histórica por UC (por fase e global) para imputação analítica de meses bloqueados
    w_uc_fase = Window.partitionBy('id_uc', 'fase_gd')
    w_uc_global = Window.partitionBy('id_uc')
    mediana_fase = F.percentile_approx(F.col('volume_analise_kwh'), 0.5).over(w_uc_fase)
    mediana_global = F.percentile_approx(F.col('volume_analise_kwh'), 0.5).over(w_uc_global)

    df_ft_consumo_mensal = (
        df_leituras_gd.withColumn(
            'consumo_kwh_analitico',
            F.coalesce(F.col('volume_analise_kwh'), mediana_fase, mediana_global).cast(
                DecimalType(18, 2)
            ),
        )
        .withColumn(
            'metodo_consumo',
            F.when(F.col('volume_analise_kwh').isNotNull(), F.lit('LEITURA_UTILIZAVEL'))
            .when(mediana_fase.isNotNull(), F.lit('MEDIANA_FASE_UC'))
            .when(mediana_global.isNotNull(), F.lit('MEDIANA_HISTORICA_UC'))
            .otherwise(F.lit('INDISPONIVEL')),
        )
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
        .select(
            'gd_uc_sk',
            'id_uc',
            'mes_referencia',
            'competencia',
            'municipio',
            'bairro',
            'classe',
            'subgrupo_tarifario',
            'alimentador',
            'modalidade',
            'faixa_potencia',
            'data_conexao',
            'competencia_conexao',
            'flag_gd_ativa_competencia',
            'fase_gd',
            'potencia_kwp',
            'energia_injetada_kwh_media_mensal',
            'consumo_kwh_silver',
            'volume_analise_kwh',
            'consumo_kwh_analitico',
            'situacao_volume',
            'metodo_consumo',
            'tipo_leitura',
            'flag_sinal_corrigido',
            'flag_troca_medidor',
            'flag_sem_leitura_anterior',
            'flag_sinal_nao_confirmado',
            'versao_regras_gold',
        )
    )

    # 4. Agregação antes vs depois da conexão por UC (_agg) para enriquecer a dimensão de impacto
    df_impacto_uc_agg = df_ft_consumo_mensal.groupBy('id_uc').agg(
        F.count('*').alias('qtd_competencias_total'),
        F.count(F.when(~F.col('flag_gd_ativa_competencia'), 1)).alias(
            'qtd_competencias_antes_conexao'
        ),
        F.count(F.when(F.col('flag_gd_ativa_competencia'), 1)).alias(
            'qtd_competencias_apos_conexao'
        ),
        F.count(
            F.when(~F.col('flag_gd_ativa_competencia') & F.col('volume_analise_kwh').isNotNull(), 1)
        ).alias('qtd_leituras_utilizaveis_antes'),
        F.count(
            F.when(F.col('flag_gd_ativa_competencia') & F.col('volume_analise_kwh').isNotNull(), 1)
        ).alias('qtd_leituras_utilizaveis_apos'),
        F.round(
            F.avg(
                F.when(~F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh'))
            ),
            2,
        )
        .cast(DecimalType(18, 2))
        .alias('consumo_medio_antes_kwh'),
        F.round(
            F.avg(
                F.when(F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh'))
            ),
            2,
        )
        .cast(DecimalType(18, 2))
        .alias('consumo_medio_apos_kwh'),
        F.percentile_approx(
            F.when(~F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh')),
            0.5,
        )
        .cast(DecimalType(18, 2))
        .alias('consumo_mediano_antes_kwh'),
        F.percentile_approx(
            F.when(F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh')),
            0.5,
        )
        .cast(DecimalType(18, 2))
        .alias('consumo_mediano_apos_kwh'),
        _soma_decimal(
            F.when(
                F.col('competencia').between(
                    F.to_date(F.lit('2022-07-01')), F.to_date(F.lit('2023-06-01'))
                ),
                F.col('volume_analise_kwh'),
            )
        ).alias('volume_p0_utilizavel_kwh'),
        _soma_decimal(
            F.when(
                F.col('competencia').between(
                    F.to_date(F.lit('2025-07-01')), F.to_date(F.lit('2026-06-01'))
                ),
                F.col('volume_analise_kwh'),
            )
        ).alias('volume_p1_utilizavel_kwh'),
        _soma_decimal(
            F.when(
                F.col('competencia').between(
                    F.to_date(F.lit('2022-07-01')), F.to_date(F.lit('2023-06-01'))
                ),
                F.col('consumo_kwh_analitico'),
            )
        ).alias('volume_p0_analitico_kwh'),
        _soma_decimal(
            F.when(
                F.col('competencia').between(
                    F.to_date(F.lit('2025-07-01')), F.to_date(F.lit('2026-06-01'))
                ),
                F.col('consumo_kwh_analitico'),
            )
        ).alias('volume_p1_analitico_kwh'),
    )

    tem_base_antes_apos = (
        F.col('consumo_medio_antes_kwh').isNotNull()
        & (F.col('consumo_medio_antes_kwh') > 0)
        & F.col('consumo_medio_apos_kwh').isNotNull()
    )
    queda_media_kwh = F.when(
        tem_base_antes_apos,
        (F.col('consumo_medio_antes_kwh') - F.col('consumo_medio_apos_kwh')).cast(
            DecimalType(18, 2)
        ),
    )
    queda_media_pct = F.when(
        tem_base_antes_apos,
        F.round(
            (F.col('consumo_medio_antes_kwh') - F.col('consumo_medio_apos_kwh'))
            * F.lit(100)
            / F.col('consumo_medio_antes_kwh'),
            2,
        ).cast(DecimalType(10, 2)),
    )

    df_tb_gd_uc = (
        df_gd_base.join(df_impacto_uc_agg, 'id_uc', 'left')
        .fillna(
            0,
            subset=[
                'qtd_competencias_total',
                'qtd_competencias_antes_conexao',
                'qtd_competencias_apos_conexao',
                'qtd_leituras_utilizaveis_antes',
                'qtd_leituras_utilizaveis_apos',
            ],
        )
        .withColumn(
            'volume_p0_utilizavel_kwh',
            F.coalesce(F.col('volume_p0_utilizavel_kwh'), F.lit(0)).cast(DecimalType(28, 2)),
        )
        .withColumn(
            'volume_p1_utilizavel_kwh',
            F.coalesce(F.col('volume_p1_utilizavel_kwh'), F.lit(0)).cast(DecimalType(28, 2)),
        )
        .withColumn(
            'volume_p0_analitico_kwh',
            F.coalesce(F.col('volume_p0_analitico_kwh'), F.lit(0)).cast(DecimalType(28, 2)),
        )
        .withColumn(
            'volume_p1_analitico_kwh',
            F.coalesce(F.col('volume_p1_analitico_kwh'), F.lit(0)).cast(DecimalType(28, 2)),
        )
        .withColumn('queda_consumo_media_kwh', queda_media_kwh)
        .withColumn('queda_consumo_pct', queda_media_pct)
        .withColumn(
            'flag_queda_acima_30_pct',
            F.when(tem_base_antes_apos, F.col('queda_consumo_pct') > F.lit(30)),
        )
        .withColumn(
            'razao_queda_sobre_injecao',
            F.when(
                tem_base_antes_apos & (F.col('energia_injetada_kwh_media_mensal') > 0),
                F.round(
                    F.col('queda_consumo_media_kwh')
                    / F.col('energia_injetada_kwh_media_mensal'),
                    4,
                ).cast(DecimalType(10, 4)),
            ),
        )
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
        .select(
            'gd_uc_sk',
            'id_uc',
            'municipio',
            'bairro',
            'classe',
            'subgrupo_tarifario',
            'alimentador',
            'status',
            'data_ligacao',
            'data_conexao',
            'competencia_conexao',
            'modalidade',
            'modalidade_origem',
            'faixa_potencia',
            'potencia_kwp',
            'energia_injetada_kwh_media_mensal',
            'kwh_por_kwp_mes',
            'fl_correcao_escala',
            'fl_data_inconsistente',
            'fl_deduplicado',
            'qtd_competencias_total',
            'qtd_competencias_antes_conexao',
            'qtd_competencias_apos_conexao',
            'qtd_leituras_utilizaveis_antes',
            'qtd_leituras_utilizaveis_apos',
            'consumo_medio_antes_kwh',
            'consumo_medio_apos_kwh',
            'consumo_mediano_antes_kwh',
            'consumo_mediano_apos_kwh',
            'queda_consumo_media_kwh',
            'queda_consumo_pct',
            'flag_queda_acima_30_pct',
            'razao_queda_sobre_injecao',
            'volume_p0_utilizavel_kwh',
            'volume_p1_utilizavel_kwh',
            'volume_p0_analitico_kwh',
            'volume_p1_analitico_kwh',
            'versao_regras_gold',
        )
        .orderBy('id_uc')
    )

    # 5. Agregado mensal: competência × município × bairro × classe × modalidade
    df_resumo_mensal = (
        df_ft_consumo_mensal.groupBy(
            'competencia', 'municipio', 'bairro', 'classe', 'modalidade'
        )
        .agg(
            F.count('*').alias('quantidade_ucs_gd_cadastradas'),
            F.count(F.when(F.col('flag_gd_ativa_competencia'), 1)).alias(
                'quantidade_ucs_gd_ativas'
            ),
            F.count(
                F.when(F.col('competencia') == F.col('competencia_conexao'), 1)
            ).alias('quantidade_novas_conexoes_mes'),
            _soma_decimal('potencia_kwp').alias('potencia_cadastrada_kwp'),
            _soma_decimal(
                F.when(F.col('flag_gd_ativa_competencia'), F.col('potencia_kwp'))
            ).alias('potencia_instalada_ativa_kwp'),
            _soma_decimal(
                F.when(
                    F.col('flag_gd_ativa_competencia'),
                    F.col('energia_injetada_kwh_media_mensal'),
                )
            ).alias('energia_injetada_estimada_ativa_kwh'),
            F.count(F.when(F.col('volume_analise_kwh').isNotNull(), 1)).alias(
                'quantidade_leituras_utilizaveis'
            ),
            F.count(F.when(F.col('volume_analise_kwh').isNull(), 1)).alias(
                'quantidade_leituras_bloqueadas'
            ),
            _soma_decimal('volume_analise_kwh').alias('volume_utilizavel_kwh'),
            _soma_decimal(
                F.when(F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh'))
            ).alias('volume_utilizavel_gd_ativa_kwh'),
            _soma_decimal(
                F.when(~F.col('flag_gd_ativa_competencia'), F.col('volume_analise_kwh'))
            ).alias('volume_utilizavel_antes_conexao_kwh'),
            _soma_decimal('consumo_kwh_analitico').alias('volume_analitico_kwh'),
            _soma_decimal(
                F.when(F.col('flag_gd_ativa_competencia'), F.col('consumo_kwh_analitico'))
            ).alias('volume_analitico_gd_ativa_kwh'),
            _soma_decimal(
                F.when(~F.col('flag_gd_ativa_competencia'), F.col('consumo_kwh_analitico'))
            ).alias('volume_analitico_antes_conexao_kwh'),
        )
        .withColumn('versao_regras_gold', F.lit(VERSAO_REGRAS))
        .orderBy('competencia', 'municipio', 'bairro', 'classe', 'modalidade')
    )

    return {
        'gd_uc': df_gd_uc,
        'tb_gd_uc': df_tb_gd_uc,
        'tb_gd_consumo_mensal': df_ft_consumo_mensal,
        'tb_gd_resumo_mensal': df_resumo_mensal,
    }


def validar_reconciliacao(gd_silver: DataFrame, tabelas: dict[str, DataFrame]) -> None:
    """Confere conservação de UCs, potências, somas e invariantes antes e depois da escrita."""
    gd_uc = tabelas['gd_uc']
    tb_gd_uc = tabelas['tb_gd_uc']
    mensal_uc = tabelas['tb_gd_consumo_mensal']
    resumo = tabelas['tb_gd_resumo_mensal']

    _exigir_chave(gd_uc, ['id_uc'], 'gd_uc')
    _exigir_chave(tb_gd_uc, ['id_uc'], 'tb_gd_uc')
    _exigir_chave(tb_gd_uc, ['gd_uc_sk'], 'tb_gd_uc')
    _exigir_chave(mensal_uc, ['id_uc', 'competencia'], 'tb_gd_consumo_mensal')
    _exigir_chave(
        resumo,
        ['competencia', 'municipio', 'bairro', 'classe', 'modalidade'],
        'tb_gd_resumo_mensal',
    )

    # 1. Reconciliação exata entre gd_silver, gd_uc e tb_gd_uc
    esperado_contrato = gd_silver.select(
        F.col('id_uc'),
        F.col('potencia_kwp').cast(DecimalType(18, 2)).alias('potencia_kw'),
        F.col('data_conexao'),
    )
    for a, b in [(esperado_contrato, gd_uc), (gd_uc, esperado_contrato)]:
        if a.exceptAll(b).limit(1).count():
            raise ValueError('gd_uc diverge da fonte Silver de GD')

    esperado_dim = gd_silver.select(
        'id_uc',
        'potencia_kwp',
        'energia_injetada_kwh_media_mensal',
        'data_conexao',
        'modalidade',
    )
    obtido_dim = tb_gd_uc.select(
        'id_uc',
        'potencia_kwp',
        'energia_injetada_kwh_media_mensal',
        'data_conexao',
        'modalidade',
    )
    for a, b in [(esperado_dim, obtido_dim), (obtido_dim, esperado_dim)]:
        if a.exceptAll(b).limit(1).count():
            raise ValueError('tb_gd_uc diverge da fonte Silver de GD')

    # 2. Reconciliação entre fato mensal por UC e resumo mensal agregado
    chaves_resumo = ['competencia', 'municipio', 'bairro', 'classe', 'modalidade']
    esperado_resumo = mensal_uc.groupBy(*chaves_resumo).agg(
        F.count('*').alias('quantidade_ucs_gd_cadastradas'),
        F.count(F.when(F.col('flag_gd_ativa_competencia'), 1)).alias('quantidade_ucs_gd_ativas'),
        _soma_decimal('potencia_kwp').alias('potencia_cadastrada_kwp'),
        _soma_decimal('volume_analise_kwh').alias('volume_utilizavel_kwh'),
        _soma_decimal('consumo_kwh_analitico').alias('volume_analitico_kwh'),
    )
    obtido_resumo = resumo.select(*esperado_resumo.columns)
    for a, b in [(esperado_resumo, obtido_resumo), (obtido_resumo, esperado_resumo)]:
        if a.exceptAll(b).limit(1).count():
            raise ValueError('tb_gd_resumo_mensal diverge do detalhe mensal por UC')

    # 3. Regras de integridade algébrica do resumo mensal
    _validar_regras(
        resumo,
        {
            'volume_utilizavel_nao_reconciliado': (
                F.col('volume_utilizavel_kwh')
                != F.col('volume_utilizavel_gd_ativa_kwh')
                + F.col('volume_utilizavel_antes_conexao_kwh')
            ),
            'volume_analitico_nao_reconciliado': (
                F.col('volume_analitico_kwh')
                != F.col('volume_analitico_gd_ativa_kwh')
                + F.col('volume_analitico_antes_conexao_kwh')
            ),
            'leituras_nao_reconciliadas': (
                F.col('quantidade_ucs_gd_cadastradas')
                != F.col('quantidade_leituras_utilizaveis')
                + F.col('quantidade_leituras_bloqueadas')
            ),
            'ativas_maior_que_cadastradas': (
                F.col('quantidade_ucs_gd_ativas') > F.col('quantidade_ucs_gd_cadastradas')
            ),
        },
        'tb_gd_resumo_mensal',
    )


def exportar_csv(tabelas: dict[str, DataFrame], diretorio: str, metadados: dict) -> Path:
    """Exporta partes CSV por tabela e grava manifest.json somente ao concluir."""
    pasta_lote = Path(diretorio)
    pasta_lote.mkdir(parents=True, exist_ok=False)
    manifesto = {
        **metadados,
        'tipo': 'gold_geracao_distribuida',
        'versao_regras': VERSAO_REGRAS,
        'tabelas': {},
    }
    controles = [
        'potencia_kw',
        'potencia_kwp',
        'energia_injetada_kwh_media_mensal',
        'volume_p0_utilizavel_kwh',
        'volume_p1_utilizavel_kwh',
        'volume_p0_analitico_kwh',
        'volume_p1_analitico_kwh',
        'volume_analise_kwh',
        'consumo_kwh_analitico',
        'potencia_cadastrada_kwp',
        'potencia_instalada_ativa_kwp',
        'energia_injetada_estimada_ativa_kwh',
        'volume_utilizavel_kwh',
        'volume_utilizavel_gd_ativa_kwh',
        'volume_utilizavel_antes_conexao_kwh',
        'volume_analitico_kwh',
        'volume_analitico_gd_ativa_kwh',
        'volume_analitico_antes_conexao_kwh',
    ]
    for nome, df in tabelas.items():
        if not nome.isidentifier():
            raise ValueError(f'Nome de tabela inválido: {nome}')
        pasta_tabela = pasta_lote / nome
        (
            df.write.mode('errorifexists')
            .option('header', 'true')
            .option('dateFormat', 'yyyy-MM-dd')
            .option('nullValue', '')
            .option('encoding', 'UTF-8')
            .csv(str(pasta_tabela))
        )
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


def publicar_delta(
    spark, tabelas: dict[str, DataFrame], destinos: dict[str, str], validar
) -> tuple:
    """Publica e confere as tabelas Gold; recupera os destinos afetados em caso de falha."""
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
