
# Databricks notebook source
from pyspark.sql import functions as F

catalog = "workspace"
bronze_schema = "bronze"

CAMINHO_ARQUIVO = "/Volumes/workspace/venergy_bronze/landing_atendimentos/atendimentos.json"
TABELA_DESTINO = f"{catalog}.{bronze_schema}.atendimentos"

print("Arquivo de origem:", CAMINHO_ARQUIVO)
print("Tabela de destino:", TABELA_DESTINO)


# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{bronze_schema}")

print("Schema Bronze preparado.")


# COMMAND ----------

df_atendimentos = (
    spark.read
    .option("multiLine", "true")
    .option("mode", "PERMISSIVE")
    .json(CAMINHO_ARQUIVO)
)

print("Estrutura dos dados:")
df_atendimentos.printSchema()

print("Quantidade de registros:", df_atendimentos.count())

display(df_atendimentos.limit(5))


# COMMAND ----------

if "_corrupt_record" in df_atendimentos.columns:
    raise ValueError("Foram identificados possíveis registros corrompidos no JSON.")

if "ingestion_datetime" in df_atendimentos.columns:
    raise ValueError("O JSON já contém a coluna ingestion_datetime.")

if "source_file" in df_atendimentos.columns:
    raise ValueError("O JSON já contém a coluna source_file.")

df_bronze = (
    df_atendimentos
    .withColumn("ingestion_datetime", F.current_timestamp())
    .withColumn("source_file", F.lit(CAMINHO_ARQUIVO))
)

print("Estrutura dos dados da camada Bronze:")
df_bronze.printSchema()

display(df_bronze.limit(5))


# COMMAND ----------

CONFIRMAR_GRAVACAO = True

if CONFIRMAR_GRAVACAO:
    if spark.catalog.tableExists(TABELA_DESTINO):
        colunas_tabela = spark.table(TABELA_DESTINO).columns

        if "source_file" not in colunas_tabela:
            raise ValueError(
                "A tabela existente não possui a coluna source_file."
            )

        arquivo_ja_ingerido = (
            spark.table(TABELA_DESTINO)
            .filter(F.col("source_file") == CAMINHO_ARQUIVO)
            .limit(1)
            .count() > 0
        )

        if arquivo_ja_ingerido:
            raise ValueError(
                "Este arquivo já foi ingerido na camada Bronze."
            )

    (
        df_bronze.write
        .format("delta")
        .mode("append")
        .saveAsTable(TABELA_DESTINO)
    )

    print("Ingestão concluída:", TABELA_DESTINO)
else:
    print("Gravação desativada. Nenhum dado foi gravado.")


# COMMAND ----------

print("DIAGNÓSTICO DOS ATENDIMENTOS")

total_registros = df_atendimentos.count()
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

print("\nVerificação de registros corrompidos:")

if "_corrupt_record" in df_atendimentos.columns:
    print("Coluna _corrupt_record identificada.")
    print("É necessário investigar possíveis falhas de leitura.")
else:
    print("Nenhuma coluna _corrupt_record identificada.")
    print("Isso não garante ausência de inconsistências.")


# COMMAND ----------

print("VALIDAÇÃO DA INGESTÃO")

if spark.catalog.tableExists(TABELA_DESTINO):
    df_tabela_bronze = spark.table(TABELA_DESTINO)

    total_bronze = (
        df_tabela_bronze
        .filter(F.col("source_file") == CAMINHO_ARQUIVO)
        .count()
    )

    print("Registros do arquivo na Bronze:", total_bronze)
    print("Registros encontrados na origem:", total_registros)

    if total_bronze == total_registros:
        print("Quantidade de registros conferida.")
    else:
        print("A quantidade de registros precisa ser investigada.")
else:
    print("A tabela Bronze ainda não existe.")
