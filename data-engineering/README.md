# Landing → Bronze de faturas

O notebook `Landing_to_Bronze_Faturas.ipynb` ingere um `faturas.csv` em uma tabela
Delta no Databricks Free Edition. A tabela corrente guarda somente a extração
completa mais recente, conforme as decisões confirmadas nesta implementação.

## Contrato da carga

| Item | Comportamento |
|---|---|
| Fonte local fornecida | `../base_dados_1/faturas.csv` |
| Landing de execução | Um arquivo completo em Unity Catalog Volume; caminho informado no widget |
| Formato | UTF-8 sem BOM, delimitador `;`, cabeçalho, escape CSV com aspas duplicadas |
| Destino sugerido | `workspace.bronze.tb_faturas`, tabela Delta gerenciada |
| Reexecução | Substituição integral com `overwrite`, sem acúmulo de lotes |
| Tipos de origem | Todas as 11 colunas permanecem STRING |
| `ingestion_datetime` | TIMESTAMP do início da gravação, capturado uma vez por carga, referência UTC |
| `source_file_path` | STRING com o caminho de origem no Volume |
| Vazios | String vazia; não se atribui significado de negócio nesta camada |
| Cabeçalhos internos e duplicatas | Preservados; o tratamento pertence à Silver |
| Valores de negócio | Sem trim, casts, correções de datas, normalização de status ou deduplicação |

Colunas da origem, na ordem contratada:

```text
id_fatura, id_uc, mes_referencia, data_emissao, valor_energia, tributos,
bandeira_tarifaria, valor_total, data_vencimento, data_pagamento, status
```

O CSV é mantido na landing como evidência original. O parsing retira delimitadores
e aspas estruturais, sem converter datas, números ou marcadores textuais de ausência.
O SHA-256 da origem aparece no relatório da execução para identificar o arquivo.

`ingestion_datetime` informa quando a carga atual foi gravada, e não a data da
emissão da fatura ou da produção do arquivo. Uma nova execução do mesmo CSV mantém
os dados de origem e troca o timestamp. A idempotência aplica-se aos registros
de negócio; os metadados de execução e a versão Delta podem mudar.

## Como executar

### Databricks Free Edition

1. Use um workspace com Unity Catalog, compute para notebooks Python e permissão
   de leitura no Volume, uso do catálogo e criação/escrita de schema/tabela.
2. Prepare um Volume de landing. O exemplo abaixo pressupõe o catálogo `workspace`;
   ajuste os nomes para os objetos e permissões do seu ambiente:

   ```sql
   CREATE SCHEMA IF NOT EXISTS workspace.landing;
   CREATE VOLUME IF NOT EXISTS workspace.landing.v_energy_inputs;
   ```

3. No Catalog Explorer, faça upload integral de `base_dados_1/faturas.csv` para o
   Volume. No exemplo, o caminho será
   `/Volumes/workspace/landing/v_energy_inputs/faturas.csv`.
   Conclua o upload antes de executar e mantenha o arquivo inalterado durante a carga.
4. Importe `Landing_to_Bronze_Faturas.ipynb` no workspace e selecione o compute.
5. Execute a célula de configuração para criar os widgets. Na primeira execução,
   a mensagem pedindo `landing_file_path` é esperada porque o parâmetro começa vazio.
   Preencha o caminho e confira os três parâmetros de destino:

   | Widget | Valor |
   |---|---|
   | `landing_file_path` | Caminho real de um único `faturas.csv` em `/Volumes/...` |
   | `catalog` | Sugestão: `workspace`; o catálogo deve existir |
   | `bronze_schema` | Sugestão: `bronze` |
   | `bronze_table` | Sugestão: `tb_faturas` |

   Nomes dos objetos aceitam letras ASCII, números e underscore, iniciando com
   letra ou underscore. O caminho da landing é independente do catálogo de destino.
6. Use **Run all**, começando na configuração. A pré-validação examina todos os
   registros; em seguida, o Spark lê o arquivo e verifica a conservação das contagens.
   O notebook cria somente o schema Bronze, quando ausente, e grava a tabela Delta.
7. Confira o JSON final com `validation: passed`, tabela, contagens, timestamp e
   SHA-256. Para o arquivo fornecido, são esperados **2.184.623 registros**, incluindo
   os **dois cabeçalhos internos**. Esses números descrevem este arquivo; não são
   limites fixos para novas extrações.

Se usar um Job, informe os mesmos parâmetros e limite a **uma execução simultânea**
por tabela. Nenhum Job ou agendamento foi criado nesta entrega.

Consultas para conferência, ajustando o destino se necessário:

```sql
SET TIME ZONE 'UTC';
SELECT COUNT(*) AS registros,
       COUNT(DISTINCT ingestion_datetime) AS instantes_de_ingestao,
       MIN(ingestion_datetime) AS ingestion_datetime_utc,
       SUM(CASE WHEN ingestion_datetime IS NULL THEN 1 ELSE 0 END) AS timestamps_nulos
FROM workspace.bronze.tb_faturas;

SELECT COUNT(*) AS cabecalhos_internos
FROM workspace.bronze.tb_faturas
WHERE id_fatura = 'id_fatura' AND id_uc = 'id_uc'
  AND mes_referencia = 'mes_referencia' AND data_emissao = 'data_emissao'
  AND valor_energia = 'valor_energia' AND tributos = 'tributos'
  AND bandeira_tarifaria = 'bandeira_tarifaria' AND valor_total = 'valor_total'
  AND data_vencimento = 'data_vencimento' AND data_pagamento = 'data_pagamento'
  AND status = 'status';
```

A apresentação de TIMESTAMP depende do fuso da sessão. Para mostrar o mesmo instante
no horário de Fortaleza, configure `SET TIME ZONE 'America/Fortaleza'` na sessão de
consulta; mantenha UTC na sessão de ingestão. Filtros por dia devem explicitar o fuso.

### Verificação local do CSV e do notebook

Não requer Spark, Java ou pacotes de terceiros. Na raiz do projeto, com Python 3.10+:

```powershell
python .\data-engineering\verificar_faturas.py
```

Em Linux/macOS:

```bash
python3 data-engineering/verificar_faturas.py
```

O script verifica a estrutura e a sintaxe das células, exercita o contrato de parsing
com arquivos temporários válidos/inválidos e aplica a pré-validação ao CSV completo.
Ele imprime um relatório JSON. Para salvar um relatório novo:

```powershell
python .\data-engineering\verificar_faturas.py --report .\data-engineering\validacao_local_faturas.json
```

Essa verificação não executa Spark, não conecta ao Databricks e não grava uma tabela
Bronze. A evidência local entregue está em `validacao_local_faturas.json`.

## Validações e limites

- Antes de escrever: arquivo existente e não vazio; UTF-8; cabeçalho exato; quantidade
  de campos de todos os registros; aspas válidas; ausência de NUL; contagens iguais
  entre o parser Python e o Spark; campos de origem STRING; destino Delta com schema
  compatível quando já existe. Falhas geram exceção e impedem a escrita.
- Depois de escrever: schema, contagem total, quantidade de cabeçalhos internos e
  metadados de todas as linhas devem corresponder à carga. Isso não constitui uma
  comparação de conteúdo campo a campo entre os dois parsers.
- A pré-validação sequencial no driver evita descarte silencioso por largura de
  registro. Para fontes substancialmente maiores, reavaliar esse custo de I/O.
- Uma falha de escrita Delta não publica uma tabela parcialmente gravada. A validação
  posterior ao commit não é uma transação conjunta com a gravação: se ela falhar,
  investigue a versão antes de consumir ou reexecutar. Não há rollback automático.
- A substituição completa foi autorizada para esta tabela de faturas. A tabela
  corrente terá uma extração; versões antigas no armazenamento dependem da retenção
  Delta. O notebook não executa DROP, TRUNCATE ou VACUUM.
- O contrato bloqueia uma extração sem registros, mas não comprova que o fornecedor
  entregou todas as competências esperadas. Consistência de datas, valores, vínculos
  de UC e demais regras de qualidade pertence à Silver.
- Não houve execução remota nesta entrega: o acesso ao workspace Databricks e o
  caminho real do arquivo no Volume ainda precisam estar disponíveis no ambiente.

## Referências

- [Especificação do projeto](../docs/spec-v-energy-grid-360.md), seção de pipeline,
  qualidade e publicação: preservação da origem e reprocessamento completo idempotente.
- [Glossário do projeto](../CONTEXT.md).
- [Apache Spark — CSV](https://spark.apache.org/docs/latest/sql-data-sources-csv.html).
- [Databricks — arquivos em Volumes](https://docs.databricks.com/aws/en/volumes/volume-files).
- [Databricks — TIMESTAMP](https://docs.databricks.com/aws/en/sql/language-manual/data-types/timestamp-type).
- [Delta Lake — atualização e substituição de tabelas](https://docs.delta.io/latest/delta-batch.html).
