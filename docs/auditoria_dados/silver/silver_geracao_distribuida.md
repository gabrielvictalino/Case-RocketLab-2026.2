# Decisões — Silver de geração distribuída

Notebook: `data-engineering/Bronze_to_Silver.ipynb`.

Lê `` `v-energy`.bronze.tb_geracao_distribuida `` e grava `` `v-energy`.silver.tb_geracao_distribuida ``. O que não dá para interpretar vai para `` `v-energy`.silver.tb_geracao_distribuida_quarentena ``. O schema `silver` é criado se ainda não existir. A gravação é `overwrite` com `overwriteSchema`.

O grão é uma linha por `id_uc`. A Bronze entra como texto. A média injetada fica na linha para classificar a UC. Ela não é subtraída do consumo da leitura nem do valor da fatura. A Gold é quem monta `possui_gd` a partir do mês de `data_conexao`. Este notebook não monta essa dimensão.

A execução no Databricks fechou com 3.510 linhas na Silver, 35 correções de escala, 5 datas inconsistentes e quarentena vazia.

## De onde vêm classe, município e data de ligação

`classe`, `municipio` e `data_ligacao` vêm de `` `v-energy`.bronze.tb_unidades_consumidoras ``, por `id_uc`. Entram como contexto de auditoria. A dimensão da UC é quem guarda classe e município.

A Bronze de unidades repete o cabeçalho numa linha (`id_uc` vale `id_uc` e `data_ligacao` vale o texto `data_ligacao`). Essa linha fica de fora da consulta. `data_ligacao` usa `try_to_date`: texto que não é data vira nulo e a carga segue.

Quando a mesma UC aparece mais de uma vez no cadastro, fica a linha com o `ingestion_datetime` mais recente. Nesta entrega, 100 UCs com solar se repetem e as cópias concordam em classe, município e data de ligação.

## Conversão

`try_cast` e `try_to_date` devolvem nulo quando o texto não converte. O nulo vira motivo de quarentena. A carga não para no meio da leitura.

| Campo | Tratamento |
| :--- | :--- |
| `id_uc` | `trim` |
| `potencia_kwp` | `trim`, vírgula trocada por ponto, `decimal(12,2)` na leitura e `decimal(10,2)` na Silver. O texto fica em `potencia_kwp_raw` |
| `energia_injetada_kwh_media_mensal` | `trim`, vírgula trocada por ponto, `decimal(12,2)` na leitura e `decimal(10,2)` na Silver. O texto fica na quarentena como `energia_raw` |
| `data_conexao` | `trim`, `try_to_date`. O texto fica na quarentena como `data_conexao_raw` |
| `modalidade` | `trim`. O texto de origem fica em `modalidade_origem` |

## Quarentena

A primeira regra que falha define o motivo. A linha sai da Silver.

| Ordem | Motivo | Quando |
| :--- | :--- | :--- |
| 1 | `id_uc_nulo` | `id_uc` nulo ou vazio depois do `trim` |
| 2 | `potencia_invalida` | potência que não converte, ou menor ou igual a zero |
| 3 | `energia_injetada_invalida` | injeção que não converte, ou menor ou igual a zero |
| 4 | `data_conexao_invalida` | data que não converte |
| 5 | `modalidade_desconhecida` | texto fora do de-para |
| 6 | `uc_inexistente` | `id_uc` sem cadastro depois de tirar o cabeçalho repetido |

Nesta entrega a quarentena tem 0 linhas. Se aparecer linha, a Silver das linhas válidas segue e o notebook avisa, com a contagem por motivo.

A quarentena guarda `id_uc`, `potencia_kwp_raw`, `energia_raw`, `data_conexao_raw`, `modalidade_origem`, `source_file`, `bronze_ingestion_datetime`, `motivo_rejeicao` e `silver_ingestion_datetime`.

## Uma linha por UC

Se o mesmo `id_uc` vier duas vezes na Bronze de geração, fica a maior `data_conexao`. O desempate é o `ingestion_datetime` mais recente. A linha que fica recebe `fl_deduplicado` verdadeiro. A cópia descartada não entra na quarentena: é a mesma UC, e a Bronze continua com as duas. Antes de gravar, Bronze tem de fechar com Silver + quarentena + duplicatas descartadas. Nesta entrega não há duplicata.

## Escala da potência

Potência convertida acima de 75 kWp cujo rendimento bruto (injeção ÷ potência original) fica abaixo de 1 kWh por kWp por mês é dividida por 1.000. `fl_correcao_escala` fica verdadeiro. O texto original permanece em `potencia_kwp_raw`.

Nesta entrega, as 3.475 linhas na escala certa vão de 1,50 a 75,00 kWp, com razão de 11,6 a 110,0 kWh/kWp/mês. As 35 linhas deslocadas vão de 3.049,99 a 8.994,91, com razão bruta de 0,014 a 0,328. Depois da divisão por 1.000, elas caem em 3,05 a 8,99 kWp.

A combinação de potência e razão separa o erro de escala em Wp de uma minigeração real. Um sistema legítimo de 500 kWp com injeção compatível (cerca de 17.000 kWh/mês, razão ~34) não tem a razão abaixo de 1, então permanece em 500 kWp e com `fl_correcao_escala` falso.

Nesta entrega são 35 linhas corrigidas.

## Data de conexão

`fl_data_inconsistente` fica verdadeiro quando `data_conexao` é anterior a 2024-01-01, posterior à data de execução (`current_date()`), ou anterior à `data_ligacao` da UC. A linha permanece na Silver.

Nesta entrega nenhuma data sai da janela. As 5 marcas são conexão anterior à ligação: `UC100259`, `UC102507`, `UC106046`, `UC110560` e `UC119180`. A validação principal confere a regra de datas em todas as linhas; se uma dessas cinco tiver a data corrigida na origem, ou se uma sexta UC entrar nessa condição, a carga segue normalmente. A lista das cinco fica apenas como aviso informativo da amostra histórica.

## Modalidade

| Texto na Bronze | Código na Silver |
| :--- | :--- |
| `GERACAO NA PROPRIA UC` | `PROPRIA_UC` |
| `AUTOCONSUMO REMOTO` | `AUTOCONSUMO_REMOTO` |
| `GERACAO COMPARTILHADA` | `COMPARTILHADA` |

Nesta entrega: 3.042, 321 e 147.

## Rendimento

`kwh_por_kwp_mes` é a injeção dividida pela potência já corrigida, em `decimal(10,2)`. Serve de auditoria. Não manda linha para a quarentena. O patamar em torno de 34 kWh por kWp por mês é o normal deste arquivo, porque a coluna de energia é excedente injetado, não geração bruta.

## Colunas gravadas na Silver

`id_uc`, `potencia_kwp_raw`, `potencia_kwp`, `fl_correcao_escala`, `energia_injetada_kwh_media_mensal`, `kwh_por_kwp_mes`, `data_conexao`, `fl_data_inconsistente`, `modalidade`, `modalidade_origem`, `fl_deduplicado`, `classe`, `municipio`, `source_file`, `bronze_ingestion_datetime`, `silver_ingestion_datetime`.

`fl_correcao_escala`, `fl_data_inconsistente` e `fl_deduplicado` não existem no CSV. A Silver cria as três.

## Validação antes e depois da gravação

As checagens que condicionam a publicação rodam sobre `df_silver` **antes** do `overwrite`, junto com o fechamento `Bronze = Silver + quarentena + duplicatas descartadas`. Se alguma falhar, o notebook lança `RuntimeError` e a tabela Silver anterior é preservada. Depois do `overwrite`, a mesma bateria roda sobre a tabela lida do catálogo para confirmar a gravação.

- Uma linha por `id_uc`.
- `potencia_kwp` maior que 0.
- `energia_injetada_kwh_media_mensal` maior que 0.
- `modalidade` dentro dos três códigos.
- `fl_correcao_escala` verdadeiro exatamente quando a potência original é maior que 75 e a razão bruta (injeção ÷ potência original) é menor que 1.
- `potencia_kwp` e `kwh_por_kwp_mes` iguais ao resultado numérico esperado da transformação em `decimal(10,2)` (dividindo por 1.000 apenas quando a condição de escala é verdadeira).
- `fl_data_inconsistente` igual à regra de datas (`data_conexao` anterior a `2024-01-01`, posterior a `current_date()` ou anterior à `data_ligacao`) em todas as linhas.
- As cinco UCs conhecidas desta entrega são conferidas depois da gravação apenas como aviso da amostra histórica, sem interromper a carga se uma data for corrigida na origem.
