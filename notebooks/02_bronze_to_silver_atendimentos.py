
from pyspark.sql import functions as F
from pyspark.sql import types as T

CATALOGO = "workspace"
SCHEMA_BRONZE = "bronze"
SCHEMA_SILVER = "silver"

TABELA_ORIGEM = f"{CATALOGO}.{SCHEMA_BRONZE}.atendimentos"
TABELA_DESTINO = f"{CATALOGO}.{SCHEMA_SILVER}.atendimentos"

CONFIRMAR_GRAVACAO = False

print("Origem:", TABELA_ORIGEM)
print("Destino:", TABELA_DESTINO)
print("Gravacao habilitada:", CONFIRMAR_GRAVACAO)


if not spark.catalog.tableExists(TABELA_ORIGEM):
    raise ValueError(
        f"Tabela Bronze nao encontrada: {TABELA_ORIGEM}"
    )

df_bronze = spark.table(TABELA_ORIGEM)

COLUNAS_OBRIGATORIAS = [
    "protocolo",
    "id_uc",
    "canal",
    "assunto",
    "subassunto",
    "data_abertura",
    "data_fechamento",
    "nota_satisfacao",
    "historico",
    "ingestion_datetime",
    "source_file"
]

colunas_ausentes = [
    coluna
    for coluna in COLUNAS_OBRIGATORIAS
    if coluna not in df_bronze.columns
]

if colunas_ausentes:
    raise ValueError(
        f"Colunas ausentes na Bronze: {colunas_ausentes}"
    )

tipo_historico = df_bronze.schema["historico"].dataType

if not isinstance(tipo_historico, T.ArrayType):
    raise ValueError("Historico deve ser um array.")

if not isinstance(tipo_historico.elementType, T.StructType):
    raise ValueError("Historico deve conter estruturas.")

campos_evento = {"sequencia", "data", "acao", "canal"}
campos_encontrados = set(tipo_historico.elementType.fieldNames())

if not campos_evento.issubset(campos_encontrados):
    raise ValueError(
        f"Campos ausentes no historico: "
        f"{campos_evento - campos_encontrados}"
    )

print("Estrutura da Bronze validada.")
df_bronze.printSchema()


df_silver = (
    df_bronze
    .withColumn(
        "protocolo",
        F.trim(F.col("protocolo").cast("string"))
    )
    .withColumn(
        "id_uc",
        F.trim(F.col("id_uc").cast("string"))
    )
    .withColumn(
        "canal",
        F.upper(F.trim(F.col("canal").cast("string")))
    )
    .withColumn(
        "assunto",
        F.upper(F.trim(F.col("assunto").cast("string")))
    )
    .withColumn(
        "subassunto",
        F.upper(F.trim(F.col("subassunto").cast("string")))
    )
    .withColumn(
        "data_abertura",
        F.expr("try_cast(data_abertura AS TIMESTAMP)")
    )
    .withColumn(
        "data_fechamento",
        F.expr("try_cast(data_fechamento AS TIMESTAMP)")
    )
    .withColumn(
        "nota_satisfacao",
        F.expr("try_cast(nota_satisfacao AS DOUBLE)")
    )
    .withColumn(
        "historico",
        F.expr("""
            transform(
                historico,
                evento -> named_struct(
                    'sequencia', try_cast(evento.sequencia AS INT),
                    'data', try_cast(evento.data AS TIMESTAMP),
                    'acao', upper(trim(cast(evento.acao AS STRING))),
                    'canal', upper(trim(cast(evento.canal AS STRING)))
                )
            )
        """)
    )
)

print("Estrutura dos dados tratados:")
df_silver.printSchema()


total_bronze = df_bronze.count()
total_silver = df_silver.count()

protocolos_duplicados = (
    df_silver
    .groupBy("protocolo")
    .count()
    .filter(F.col("count") > 1)
    .count()
)

identificadores_invalidos = df_silver.filter(
    F.col("protocolo").isNull()
    | (F.col("protocolo") == "")
    | F.col("id_uc").isNull()
    | (F.col("id_uc") == "")
).count()

datas_invalidas = df_silver.filter(
    F.col("data_abertura").isNull()
    | (
        F.col("data_fechamento").isNotNull()
        & (F.col("data_fechamento") < F.col("data_abertura"))
    )
).count()

conversoes_invalidas = {}

for coluna in [
    "data_abertura",
    "data_fechamento",
    "nota_satisfacao"
]:
    preenchidos_bronze = df_bronze.filter(
        F.col(coluna).isNotNull()
    ).count()

    preenchidos_silver = df_silver.filter(
        F.col(coluna).isNotNull()
    ).count()

    conversoes_invalidas[coluna] = (
        preenchidos_bronze - preenchidos_silver
    )

historicos_invalidos = df_silver.filter(
    F.col("historico").isNull()
    | (F.size("historico") == 0)
).count()

print("Total Bronze:", total_bronze)
print("Total Silver:", total_silver)
print("Protocolos duplicados:", protocolos_duplicados)
print("Identificadores invalidos:", identificadores_invalidos)
print("Datas invalidas:", datas_invalidas)
print("Conversoes invalidas:", conversoes_invalidas)
print("Historicos vazios ou nulos:", historicos_invalidos)

if total_bronze != total_silver:
    raise ValueError("Quantidade de atendimentos alterada.")

if (
    protocolos_duplicados > 0
    or identificadores_invalidos > 0
    or datas_invalidas > 0
    or historicos_invalidos > 0
    or any(
        quantidade > 0
        for quantidade in conversoes_invalidas.values()
    )
):
    raise ValueError(
        "Inconsistencias encontradas nos atendimentos."
    )

print("Validacao dos atendimentos concluida.")


df_eventos = (
    df_silver
    .select(
        "protocolo",
        "data_abertura",
        "data_fechamento",
        F.posexplode_outer("historico").alias(
            "posicao", "evento"
        )
    )
)

total_eventos_bronze = (
    df_bronze
    .select(
        F.explode("historico").alias("evento")
    )
    .count()
)

total_eventos_silver = df_eventos.filter(
    F.col("evento").isNotNull()
).count()

eventos_invalidos = df_eventos.filter(
    F.col("evento").isNull()
    | F.col("evento.sequencia").isNull()
    | F.col("evento.data").isNull()
    | F.col("evento.acao").isNull()
    | (F.col("evento.acao") == "")
    | F.col("evento.canal").isNull()
    | (F.col("evento.canal") == "")
).count()

sequencias_duplicadas = (
    df_eventos
    .filter(F.col("evento").isNotNull())
    .groupBy(
        "protocolo",
        F.col("evento.sequencia")
    )
    .count()
    .filter(F.col("count") > 1)
    .count()
)

sequencias_fora_de_ordem = (
    df_eventos
    .filter(F.col("evento").isNotNull())
    .filter(
        F.col("evento.sequencia") != F.col("posicao") + 1
    )
    .count()
)

datas_eventos_invalidas = df_eventos.filter(
    F.col("evento").isNotNull()
    & (
        (F.col("evento.data") < F.col("data_abertura"))
        | (
            F.col("data_fechamento").isNotNull()
            & (
                F.col("evento.data")
                > F.col("data_fechamento")
            )
        )
    )
).count()

print("Eventos Bronze:", total_eventos_bronze)
print("Eventos Silver:", total_eventos_silver)
print("Eventos invalidos:", eventos_invalidos)
print("Sequencias duplicadas:", sequencias_duplicadas)
print("Sequencias fora de ordem:", sequencias_fora_de_ordem)
print("Datas de eventos invalidas:", datas_eventos_invalidas)

if total_eventos_bronze != total_eventos_silver:
    raise ValueError("Quantidade de eventos alterada.")

if any([
    eventos_invalidos,
    sequencias_duplicadas,
    sequencias_fora_de_ordem,
    datas_eventos_invalidas
]):
    raise ValueError(
        "Inconsistencias encontradas no historico."
    )

print("Validacao do historico concluida.")


notas_nulas = df_silver.filter(
    F.col("nota_satisfacao").isNull()
).count()

print("DIAGNOSTICO FINAL")
print("Atendimentos:", total_silver)
print("Eventos:", total_eventos_silver)
print("Notas de satisfacao nulas:", notas_nulas)

print("Atendimentos por mes:")

display(
    df_silver
    .groupBy(
        F.date_format(
            "data_abertura", "yyyy-MM"
        ).alias("mes")
    )
    .count()
    .orderBy("mes")
)

print("Atendimentos por assunto:")

display(
    df_silver
    .groupBy("assunto")
    .count()
    .orderBy("assunto")
)


if CONFIRMAR_GRAVACAO:
    if spark.catalog.tableExists(TABELA_DESTINO):
        raise ValueError(
            f"A tabela {TABELA_DESTINO} ja existe. "
            "Gravacao interrompida para evitar sobrescrita."
        )

    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS "
        f"{CATALOGO}.{SCHEMA_SILVER}"
    )

    (
        df_silver.write
        .format("delta")
        .mode("errorifexists")
        .saveAsTable(TABELA_DESTINO)
    )

    print("Tabela Silver criada:", TABELA_DESTINO)

else:
    print("Transformacao Bronze para Silver preparada.")
    print("Gravacao desativada.")
    print("Destino:", TABELA_DESTINO)
    print("Nenhuma tabela foi gravada.")
