"""Adaptador comercial do contrato 0.3.0-provisional; nenhuma tarifa é inferida."""

from pathlib import Path

import yaml
from pyspark.sql import functions as F
from pyspark.sql import Window

from gold_faturas import (
    COMPETENCIA_REGEX,
    DIMENSOES,
    FLAGS_LEITURAS,
    _exigir_chave,
    _exigir_colunas,
    _validar_regras,
    validar_data_referencia,
)

CONTRATOS = Path(__file__).resolve().parents[2] / 'contracts'
COMERCIAIS = ('uc_consumo_faturamento_mensal', 'receita_volume_mensal')
CAMPOS_COMPLEMENTO = ['volume_faturado_kwh', 'tarifa_base', 'adicional_bandeira']


def especificacoes(raiz=CONTRATOS):
    if (raiz / 'VERSION').read_text().strip() != '0.3.0-provisional':
        raise ValueError('Adaptador exige contrato 0.3.0-provisional')
    return {n: yaml.safe_load((raiz / 'tabelas' / f'{n}.yaml').read_text()) for n in COMERCIAIS}


def validar_tabela_contratual(df, spec):
    """Valida antes de converter para evitar truncar/normalizar entradas inválidas."""
    _exigir_colunas(df, spec['columns'], spec['table'])
    regras = {}
    for nome, col in spec['columns'].items():
        valor = F.col(nome)
        if not col['nullable']:
            regras[f'{nome}_nulo'] = valor.isNull()
        if col['type'] == 'text':
            regras[f'{nome}_vazio'] = F.trim(valor) == ''
        if 'enum' in col:
            regras[f'{nome}_enum'] = ~valor.isin(col['enum'])
        if 'pattern' in col:
            regras[f'{nome}_formato'] = ~valor.rlike(col['pattern'])
        if 'minimum' in col:
            regras[f'{nome}_minimo'] = valor < col['minimum']
        if col.get('month'):
            regras[f'{nome}_mes'] = F.dayofmonth(valor) != 1
        tipo = col['type'].replace('numeric', 'decimal').replace('text', 'string')
        if tipo.startswith('decimal'):
            if df.schema[nome].dataType.typeName() not in {'integer', 'long', 'short', 'decimal'}:
                raise ValueError(f'{spec["table"]}.{nome}: precisa ser inteiro ou Decimal')
            convertido = valor.try_cast(tipo)
            regras[f'{nome}_precisao'] = valor.isNotNull() & (
                convertido.isNull() | (convertido != valor)
            )
    _validar_regras(df, regras, spec['table'])
    _exigir_chave(df, spec['primary_key'], spec['table'])
    return df.select(
        *[
            F.col(n)
            .cast(c['type'].replace('numeric', 'decimal').replace('text', 'string'))
            .alias(n)
            for n, c in spec['columns'].items()
        ]
    )


def construir_consumo_contratual(leituras, cadastro, gd, inspecoes, data_referencia):
    """Métodos da GD generalizados para todas as UCs, com proveniência auxiliar.

    Mediana aproximada Spark (mesma convenção da Gold GD), apenas de leituras
    utilizáveis da própria UC; nunca do gerador sintético. Sem doadores, bloqueia.
    """
    referencia = validar_data_referencia(data_referencia)
    _exigir_colunas(
        leituras,
        ['id_uc', 'mes_referencia', 'consumo_kwh', 'tipo_leitura', *FLAGS_LEITURAS],
        'leituras',
    )
    _exigir_colunas(cadastro, ['id_uc', *DIMENSOES], 'cadastro')
    _exigir_colunas(gd, ['id_uc', 'data_conexao'], 'gd')
    _exigir_colunas(inspecoes, ['id_uc', 'data', 'resultado'], 'inspecoes')
    if leituras.schema['consumo_kwh'].dataType.typeName() not in {
        'integer',
        'long',
        'short',
        'decimal',
    }:
        raise ValueError('leituras: consumo_kwh precisa ser inteiro ou decimal')
    for flag in FLAGS_LEITURAS:
        if leituras.schema[flag].dataType.simpleString() != 'boolean':
            raise ValueError(f'leituras: {flag} precisa ser boolean')
    for df, chaves, nome in [
        (leituras, ['id_uc', 'mes_referencia'], 'leituras'),
        (cadastro, ['id_uc'], 'cadastro'),
        (gd, ['id_uc'], 'gd'),
    ]:
        _exigir_chave(df, chaves, nome)
    for df, coluna, nome in [(gd, 'data_conexao', 'gd'), (inspecoes, 'data', 'inspecoes')]:
        if df.schema[coluna].dataType.simpleString() != 'date':
            raise ValueError(f'{nome}: {coluna} precisa ser date')
        _validar_regras(
            df, {'id_nulo': F.col('id_uc').isNull(), 'data_nula': F.col(coluna).isNull()}, nome
        )
    _validar_regras(inspecoes, {'resultado_nulo': F.col('resultado').isNull()}, 'inspecoes')
    _validar_regras(
        leituras,
        {
            'chave_nula': F.col('id_uc').isNull() | F.col('mes_referencia').isNull(),
            'competencia_invalida': ~F.col('mes_referencia').rlike(COMPETENCIA_REGEX),
            'consumo_nulo': F.col('consumo_kwh').isNull(),
            'consumo_precisao': (
                F.col('consumo_kwh').try_cast('decimal(18,2)').isNull()
                | (F.col('consumo_kwh').try_cast('decimal(18,2)') != F.col('consumo_kwh'))
            ),
            'tipo_invalido': F.col('tipo_leitura').isNull()
            | ~F.col('tipo_leitura').isin('REAL', 'ESTIMADA'),
            **{f'{f}_nula': F.col(f).isNull() for f in FLAGS_LEITURAS},
        },
        'leituras contratuais',
    )
    primeira = (
        inspecoes.filter(F.col('resultado') == 'IRREGULARIDADE CONFIRMADA')
        .groupBy('id_uc')
        .agg(F.min('data').alias('primeira_inspecao_irregular'))
    )
    base = (
        leituras.join(cadastro.select('id_uc'), 'id_uc', 'inner')
        .join(gd.select('id_uc', 'data_conexao'), 'id_uc', 'left')
        .join(primeira, 'id_uc', 'left')
        .withColumn('competencia', F.to_date(F.concat('mes_referencia', F.lit('-01'))))
    )
    _validar_regras(
        base, {'competencia_futura': F.col('competencia') > F.lit(referencia)}, 'consumo contratual'
    )
    ativa = F.col('competencia') >= F.trunc('data_conexao', 'month')
    irregular = F.col('competencia') >= F.trunc('primeira_inspecao_irregular', 'month')
    bloqueada = F.lit(False)
    for flag in FLAGS_LEITURAS:
        bloqueada = bloqueada | F.col(flag)
    base = (
        base.withColumn(
            'grupo_uc',
            F.when(ativa, 'GD').when(irregular, 'IRREGULARIDADE_CONFIRMADA').otherwise('DEMAIS'),
        )
        .withColumn('fase_gd', F.when(ativa, 'APOS_CONEXAO').otherwise('ANTES_CONEXAO'))
        .withColumn('consumo_kwh_original', F.col('consumo_kwh').cast('decimal(18,2)'))
        .withColumn(
            '_utilizavel',
            F.when(~bloqueada & (F.col('consumo_kwh') >= 0), F.col('consumo_kwh_original')),
        )
    )
    fase = Window.partitionBy('id_uc', 'fase_gd')
    uc = Window.partitionBy('id_uc')
    base = (
        base.withColumn('mediana_fase_kwh', F.percentile_approx('_utilizavel', 0.5).over(fase))
        .withColumn('mediana_historica_kwh', F.percentile_approx('_utilizavel', 0.5).over(uc))
        .withColumn('doadores_fase', F.count('_utilizavel').over(fase))
        .withColumn('doadores_historico', F.count('_utilizavel').over(uc))
        .withColumn(
            'consumo_kwh_analitico',
            F.coalesce('_utilizavel', 'mediana_fase_kwh', 'mediana_historica_kwh').cast(
                'decimal(18,2)'
            ),
        )
        .withColumn(
            'metodo_consumo',
            F.when(F.col('_utilizavel').isNotNull(), 'LEITURA_UTILIZAVEL')
            .when(F.col('mediana_fase_kwh').isNotNull(), 'MEDIANA_FASE_UC')
            .when(F.col('mediana_historica_kwh').isNotNull(), 'MEDIANA_HISTORICA_UC'),
        )
    )
    _validar_regras(
        base,
        {'sem_mediana': F.col('consumo_kwh_analitico').isNull()},
        'consumo contratual: sem doadores utilizáveis da UC',
    )
    return base.drop('_utilizavel')


def construir_saidas_contratuais(
    consumo, tabelas_auxiliares, cadastro, complemento, raiz=CONTRATOS
):
    """Complemento homologado por id_fatura; exige valores e proveniência explícitos."""
    detalhe = tabelas_auxiliares['faturas']
    _exigir_colunas(
        complemento,
        ['id_fatura', *CAMPOS_COMPLEMENTO, 'proveniencia'],
        'complemento homologado de faturamento',
    )
    _exigir_chave(complemento, ['id_fatura'], 'complemento homologado de faturamento')
    _validar_regras(
        complemento,
        {
            'id_nulo': F.col('id_fatura').isNull(),
            'proveniencia_ausente': F.col('proveniencia').isNull() | (F.trim('proveniencia') == ''),
        },
        'complemento homologado de faturamento',
    )
    # Fatura elegível sem leitura não pode desaparecer nem receber um original inventado.
    chaves = ['id_uc', 'competencia']
    competencias_com_fatura = (
        detalhe.select(*chaves)
        .unionByName(tabelas_auxiliares['faturas_excluidas'].select(*chaves))
        .join(cadastro.select('id_uc'), 'id_uc', 'inner')
        .select(*chaves)
        .distinct()
    )
    if competencias_com_fatura.join(consumo, chaves, 'left_anti').limit(1).count():
        raise ValueError(
            'Competência com fatura sem leitura: consumo original obrigatório indisponível'
        )
    faturado = detalhe.select(
        *chaves, 'id_fatura', 'valor_total', 'data_vencimento', 'bandeira_tarifaria', 'status'
    ).join(complemento, 'id_fatura', 'left')
    base = consumo.join(faturado, chaves, 'left')
    tem_fatura = F.col('id_fatura').isNotNull()
    base = (
        base.withColumn(
            'bandeira',
            F.when(
                tem_fatura,
                F.create_map(
                    F.lit('Verde'),
                    F.lit('VERDE'),
                    F.lit('Amarela'),
                    F.lit('AMARELA'),
                    F.lit('Vermelha P1'),
                    F.lit('VERMELHA_P1'),
                    F.lit('Vermelha P2'),
                    F.lit('VERMELHA_P2'),
                )[F.col('bandeira_tarifaria')],
            ),
        )
        .withColumn(
            'status_pagamento',
            F.when(
                tem_fatura,
                F.when(F.col('status') == 'PAGA', 'PAGA').when(
                    F.col('status') == 'EM ABERTO', 'ABERTA'
                ),
            ),
        )
        .withColumn(
            'valor_arrecadado',
            F.when(F.col('status') == 'PAGA', F.col('valor_total')).otherwise(F.lit(0)),
        )
    )
    for c in ['volume_faturado_kwh', 'valor_total', 'valor_arrecadado']:
        base = base.withColumn(c, F.when(tem_fatura, F.col(c)).otherwise(F.lit(0)))
    for c in ['tarifa_base', 'adicional_bandeira', 'data_vencimento']:
        base = base.withColumn(c, F.when(tem_fatura, F.col(c)))
    _validar_regras(
        base,
        {
            **{
                f'{c}_ausente': tem_fatura & F.col(c).isNull()
                for c in [
                    *CAMPOS_COMPLEMENTO,
                    'proveniencia',
                    'data_vencimento',
                    'bandeira',
                    'status_pagamento',
                ]
            },
        },
        'fatura sem complemento homologado',
    )
    specs = especificacoes(raiz)
    mensal_uc = validar_tabela_contratual(base, specs[COMERCIAIS[0]])
    receita = agregar_receita_contratual(mensal_uc, cadastro)
    receita = validar_tabela_contratual(receita, specs[COMERCIAIS[1]])
    return {COMERCIAIS[0]: mensal_uc, COMERCIAIS[1]: receita}


def agregar_receita_contratual(mensal_uc, cadastro):
    # Produtos decimal(18,2) × decimal(18,6) = decimal(37,8); somar antes de round.
    return (
        mensal_uc.join(cadastro.select('id_uc', *DIMENSOES), 'id_uc', 'inner')
        .groupBy('competencia', *DIMENSOES, 'grupo_uc')
        .agg(
            F.sum('volume_faturado_kwh').alias('volume_faturado_kwh'),
            F.sum('valor_total').alias('receita'),
            F.sum('valor_arrecadado').alias('receita_arrecadada'),
            F.round(
                F.sum(F.col('volume_faturado_kwh') * F.coalesce('tarifa_base', F.lit(0))), 2
            ).alias('componente_tarifa_reais'),
            F.round(
                F.sum(F.col('volume_faturado_kwh') * F.coalesce('adicional_bandeira', F.lit(0))), 2
            ).alias('componente_bandeira_reais'),
        )
    )


def validar_reconciliacao_contratual(tabelas, cadastro, raiz=CONTRATOS):
    specs = especificacoes(raiz)
    for nome in COMERCIAIS:
        validar_tabela_contratual(tabelas[nome], specs[nome])
    detalhe = tabelas[COMERCIAIS[0]]
    sem = F.col('id_fatura').isNull()
    regras = {}
    for c in [
        'bandeira',
        'status_pagamento',
        'data_vencimento',
        'tarifa_base',
        'adicional_bandeira',
    ]:
        regras[f'{c}_nulidade'] = (sem & F.col(c).isNotNull()) | (~sem & F.col(c).isNull())
    for c in ['volume_faturado_kwh', 'valor_total', 'valor_arrecadado']:
        regras[f'{c}_sem_fatura'] = sem & (F.col(c) != 0)
    regras.update(
        {
            'paga': (F.col('status_pagamento') == 'PAGA')
            & (F.col('valor_arrecadado') != F.col('valor_total')),
            'aberta': (F.col('status_pagamento') == 'ABERTA') & (F.col('valor_arrecadado') != 0),
            'leitura_alterada': (F.col('metodo_consumo') == 'LEITURA_UTILIZAVEL')
            & (F.col('consumo_kwh_original') != F.col('consumo_kwh_analitico')),
            'troca_sem_mediana': F.col('flag_troca_medidor')
            & (F.col('metodo_consumo') == 'LEITURA_UTILIZAVEL'),
        }
    )
    _validar_regras(detalhe, regras, 'R2')
    esperado = agregar_receita_contratual(detalhe, cadastro).select(*tabelas[COMERCIAIS[1]].columns)
    obtido = tabelas[COMERCIAIS[1]]
    if esperado.exceptAll(obtido).limit(1).count() or obtido.exceptAll(esperado).limit(1).count():
        raise ValueError('Reconciliação contratual por grão divergente')


def exportar_comerciais(tabelas, diretorio, metadados, raiz=CONTRATOS):
    """Dois CSVs canônicos; recibo de domínio, sem fingir manifesto de 12 tabelas."""
    import csv
    import hashlib
    import json
    import shutil
    from gold_faturas import conferir_arquivos_csv

    def hash_csv(arquivo):
        with arquivo.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    specs = especificacoes(raiz)
    pasta = Path(diretorio)
    pasta.mkdir(parents=True, exist_ok=False)
    recibo = {**metadados, 'contract_version': '0.3.0-provisional', 'tables': {}}
    for nome in COMERCIAIS:
        df = validar_tabela_contratual(tabelas[nome], specs[nome])
        temporaria = pasta / f'_{nome}'
        (
            df.write.mode('errorifexists')
            .option('header', 'true')
            .option('nullValue', '')
            .option('dateFormat', 'yyyy-MM-dd')
            .csv(str(temporaria))
        )
        partes = sorted(temporaria.glob('part-*.csv'))
        conferir_arquivos_csv(df, partes)
        arquivo = pasta / f'{nome}.csv'
        with arquivo.open('x', newline='', encoding='utf-8') as destino:
            escritor = csv.writer(destino, lineterminator='\n')
            escritor.writerow(df.columns)
            for parte in partes:
                with parte.open(newline='', encoding='utf-8') as fonte:
                    leitor = csv.reader(fonte, strict=True)
                    next(leitor)
                    escritor.writerows(leitor)
        # Conferir o arquivo final, não apenas a pasta temporária.
        hashes = conferir_arquivos_csv(df, [arquivo])
        totais = {c: 0 for c in specs[nome]['control_totals']}
        from decimal import Decimal

        linhas = 0
        with arquivo.open(newline='', encoding='utf-8') as fonte:
            for r in csv.DictReader(fonte):
                linhas += 1
                for c in totais:
                    totais[c] += Decimal(r[c])
        if hash_csv(arquivo) != hashes[str(arquivo)]:
            raise ValueError('CSV comercial mudou após a conferência')
        recibo['tables'][nome] = {
            'file': arquivo.name,
            'rows': linhas,
            'sha256': hashes[str(arquivo)],
            'totals': {c: str(v) for c, v in totais.items()},
        }
        shutil.rmtree(temporaria)
    for tabela in recibo['tables'].values():
        if hash_csv(pasta / tabela['file']) != tabela['sha256']:
            raise ValueError('CSV comercial mudou antes da confirmação do recibo')
    temporario = pasta / 'comercial.json.tmp'
    temporario.write_text(json.dumps(recibo, ensure_ascii=False, indent=2) + '\n')
    temporario.replace(pasta / 'comercial.json')
    return pasta
