
# Databricks notebook source
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.errors import AnalysisException
import json
import hashlib

catalog = "workspace"
bronze_schema = "bronze"

CAMINHO_ARQUIVO = "/Volumes/workspace/venergy_bronze/landing_atendimentos/atendimentos.json"
TABELA_DESTINO = f"{catalog}.{bronze_schema}.atendimentos"

CONFIRMAR_GRAVACAO = False

print("Arquivo de origem:", CAMINHO_ARQUIVO)
print("Tabela de destino:", TABELA_DESTINO)
print("Gravacao habilitada:", CONFIRMAR_GRAVACAO)


# COMMAND ----------

if CONFIRMAR_GRAVACAO:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{bronze_schema}")

print("Configuracao da Bronze preparada.")


# COMMAND ----------

df_atendimentos = (
    spark.read
    .option("multiLine", "true")
    .option("mode", "FAILFAST")
    .json(CAMINHO_ARQUIVO)
)

if df_atendimentos.isEmpty():
    raise ValueError("O arquivo de atendimentos esta vazio.")

if "_corrupt_record" in df_atendimentos.columns:
    raise ValueError("Foram identificados registros corrompidos no JSON.")

print("Estrutura dos dados:")
df_atendimentos.printSchema()

total_registros = df_atendimentos.count()
print("Quantidade de registros:", total_registros)

display(df_atendimentos.limit(5))


# COMMAND ----------

COLUNAS_OBRIGATORIAS = [
    "protocolo",
    "id_uc",
    "canal",
    "assunto",
    "subassunto",
    "data_abertura",
    "data_fechamento",
    "nota_satisfacao",
    "historico"
]

colunas_ausentes = [
    coluna
    for coluna in COLUNAS_OBRIGATORIAS
    if coluna not in df_atendimentos.columns
]

if colunas_ausentes:
    raise ValueError(
        f"Colunas obrigatorias ausentes: {colunas_ausentes}"
    )

colunas_reservadas = [
    "source_file",
    "ingestion_datetime"
]

colunas_reservadas_presentes = [
    coluna
    for coluna in colunas_reservadas
    if coluna in df_atendimentos.columns
]

if colunas_reservadas_presentes:
    raise ValueError(
        f"O JSON possui colunas reservadas: {colunas_reservadas_presentes}"
    )

campo_historico = df_atendimentos.schema["historico"].dataType

if not isinstance(campo_historico, T.ArrayType):
    raise ValueError("A coluna historico deve ser um array.")

if not isinstance(campo_historico.elementType, T.StructType):
    raise ValueError("Os elementos de historico devem ser estruturas.")

campos_historico = {
    campo.name
    for campo in campo_historico.elementType.fields
}

campos_historico_obrigatorios = {
    "sequencia",
    "data",
    "acao",
    "canal"
}

if not campos_historico_obrigatorios.issubset(campos_historico):
    raise ValueError(
        "A estrutura de historico nao possui todos os campos obrigatorios."
    )

print("Validacao estrutural concluida.")


# COMMAND ----------

df_bronze = (
    df_atendimentos
    .withColumn("ingestion_datetime", F.current_timestamp())
    .withColumn("source_file", F.lit(CAMINHO_ARQUIVO))
)

print("Estrutura dos dados da camada Bronze:")
df_bronze.printSchema()

display(df_bronze.limit(5))


# COMMAND ----------

tabela_existe = spark.catalog.tableExists(TABELA_DESTINO)

if tabela_existe:
    df_existente = spark.table(TABELA_DESTINO)

    if "source_file" not in df_existente.columns:
        raise ValueError(
            "A tabela existente nao possui a coluna source_file."
        )

    if "ingestion_datetime" not in df_existente.columns:
        raise ValueError(
            "A tabela existente nao possui a coluna ingestion_datetime."
        )

    schema_origem = {
        campo.name: campo.dataType.simpleString()
        for campo in df_bronze.schema.fields
    }

    schema_destino = {
        campo.name: campo.dataType.simpleString()
        for campo in df_existente.schema.fields
    }

    if schema_origem != schema_destino:
        raise ValueError(
            "O schema do JSON nao corresponde ao schema da Bronze existente. "
            f"Origem: {schema_origem}. "
            f"Destino: {schema_destino}."
        )

    print("Schema compativel com a tabela existente.")
else:
    print("A tabela Bronze ainda nao existe.")
    print("O schema sera definido na primeira gravacao.")


# COMMAND ----------

ids_invalidos = df_atendimentos.filter(
    F.col("protocolo").isNull() |
    (F.trim(F.col("protocolo").cast("string")) == "")
).count()

if ids_invalidos > 0:
    raise ValueError(
        f"Foram encontrados {ids_invalidos} protocolos invalidos."
    )

protocolos_distintos = df_atendimentos.select("protocolo").distinct().count()

if protocolos_distintos != total_registros:
    raise ValueError(
        "Foram encontrados protocolos duplicados no arquivo de origem."
    )

print("Validacao de protocolos concluida.")


# COMMAND ----------

if CONFIRMAR_GRAVACAO:
    if tabela_existe:
        (
            df_bronze.write
            .format("delta")
            .mode("overwrite")
            .option(
                "replaceWhere",
                f"source_file = '{CAMINHO_ARQUIVO}'"
            )
            .saveAsTable(TABELA_DESTINO)
        )

        print("Registros do arquivo substituidos na Bronze.")
    else:
        (
            df_bronze.write
            .format("delta")
            .mode("errorifexists")
            .saveAsTable(TABELA_DESTINO)
        )

        print("Tabela Bronze criada com sucesso.")
else:
    print("Gravacao desativada. Nenhum dado foi gravado.")


# COMMAND ----------

print("DIAGNOSTICO DOS ATENDIMENTOS")

print("Total de registros:", total_registros)

print("\nColunas encontradas:")
df_atendimentos.printSchema()

print("\nValores nulos por coluna:")

expressoes_nulos = [
    F.sum(
        F.when(
            F.col(f"`{coluna.replace('`', '``')}`").isNull(),
            1
        ).otherwise(0)
    ).alias(f"nulos_{indice}")
    for indice, coluna in enumerate(df_atendimentos.columns)
]

if expressoes_nulos:
    resultado_nulos = df_atendimentos.agg(*expressoes_nulos)

    for indice, coluna in enumerate(df_atendimentos.columns):
        print(f"nulos_{indice}: {coluna}")

    display(resultado_nulos)
else:
    print("Nenhuma coluna identificada.")

print("\nVerificacao de registros corrompidos:")

if "_corrupt_record" in df_atendimentos.columns:
    print("Coluna _corrupt_record identificada.")
else:
    print("Nenhuma coluna _corrupt_record identificada.")


# COMMAND ----------

print("VALIDACAO DA INGESTAO")

if spark.catalog.tableExists(TABELA_DESTINO):
    df_tabela_bronze = spark.table(TABELA_DESTINO)

    total_bronze = (
        df_tabela_bronze
        .filter(F.col("source_file") == CAMINHO_ARQUIVO)
        .count()
    )

    print("Registros do arquivo na Bronze:", total_bronze)
    print("Registros encontrados na origem:", total_registros)

    if CONFIRMAR_GRAVACAO:
        if total_bronze != total_registros:
            raise ValueError(
                "A quantidade de registros gravados nao corresponde a origem."
            )

        print("Quantidade de registros conferida.")
    else:
        print(
            "Gravacao desativada: os dados existentes podem ser "
            "de uma execucao anterior."
        )
else:
    print("A tabela Bronze ainda nao existe.")
