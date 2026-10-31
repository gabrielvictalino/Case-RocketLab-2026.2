# Decisões — Silver de geração distribuída

Notebook: `data-engineering/bronze_to_silver/bronze-to-silver-geracao-distribuida.ipynb`.
Auditoria de origem: `docs/auditoria_dados/auditoria_geracao_distribuida.md`.

Lê `` `v-energy`.bronze.tb_geracao_distribuida `` e grava `` `v-energy`.silver.tb_geracao_distribuida ``. O que não dá para interpretar vai para `` `v-energy`.silver.tb_geracao_distribuida_quarentena ``. O schema `silver` é criado se ainda não existir. A gravação é `overwrite` com `overwriteSchema`.

O grão é uma linha por `id_uc`. A Bronze entra como texto. A média injetada fica na linha para classificar a UC. Ela não é subtraída do consumo da leitura nem do valor da fatura. A Gold é quem monta `possui_gd` a partir do mês de `data_conexao`. Este notebook não monta essa dimensão.

A execução no Databricks fechou com 3.510 linhas na Silver, 35 correções de escala, 5 datas inconsistentes e quarentena vazia.

## Proteção de leitura e escrita (`VERSION AS OF` e `RESTORE`)

A leitura fixa a versão atual das duas tabelas de entrada (`VERSION AS OF` em `tb_geracao_distribuida` e `tb_unidades_consumidoras`). Assim, contagens, validações pré-escrita e `saveAsTable` leem exatamente o mesmo snapshot da Bronze, mesmo que uma recarga concorra com o notebook.

Antes do `overwrite`, o notebook registra a versão atual da Silver e da quarentena (`DESCRIBE HISTORY ... LIMIT 1`). Se a gravação de qualquer uma das duas tabelas ou a conferência pós-escrita falhar, ambas voltam para a versão anterior (`RESTORE TABLE ... TO VERSION AS OF`, ou `DROP TABLE IF EXISTS` na primeira carga) antes de relançar o erro.

## De onde vêm classe, município e data de ligação

`classe`, `municipio` e `data_ligacao` vêm de `` `v-energy`.bronze.tb_unidades_consumidoras ``, por `id_uc` normalizado (`upper(trim(id_uc))`). Entram como contexto de auditoria. A dimensão da UC é quem guarda classe e município.

- A linha de cabeçalho repetido (`upper(trim(id_uc)) == 'ID_UC'`) fica de fora.
- `classe` e `municipio` passam por `texto_padrao` (remove acentos, colapsa espaços e aplica `initcap`), evitando categorias duplicadas como `RESIDENCIAL` vs `Residencial`.
- `data_ligacao` exige o formato ISO `^\d{4}-\d{2}-\d{2}$` antes de `try_to_date(..., 'yyyy-MM-dd')`. Se alguma UC tiver `data_ligacao` preenchida que não converte, o notebook emite um `[AVISO]` com a contagem.
- Quando a mesma UC aparece mais de uma vez no cadastro, a deduplicação ordena por `ingestion_datetime` mais recente, `data_ligacao` mais recente, `source_file` e hash SHA-256 determinístico das colunas. Nesta entrega, 100 UCs com solar se repetem e as cópias concordam em classe, município e data de ligação.

## Conversão e precisão única (`decimal(10,2)`)

A triagem e a Silver usam a mesma precisão (`decimal(10,2)`) e o padrão ISO `^\d{4}-\d{2}-\d{2}$` para datas. Qualquer valor que não converta, estoure `decimal(10,2)` ou venha com data truncada (`'2024'`, `'2024-3'`) vira nulo na leitura e vai para a quarentena, sem quebrar o cast final.

| Campo | Tratamento |
| :--- | :--- |
| `id_uc` | `upper(trim(id_uc))` |
| `potencia_kwp` | `trim`, vírgula trocada por ponto, `try_cast` direto para `decimal(10,2)`. O texto fica em `potencia_kwp_raw` |
| `energia_injetada_kwh_media_mensal` | `trim`, vírgula trocada por ponto, `try_cast` direto para `decimal(10,2)`. O texto fica na quarentena como `energia_raw` |
| `data_conexao` | `trim`, exige regex `^\d{4}-\d{2}-\d{2}$` e `try_to_date(..., 'yyyy-MM-dd')`. O texto fica na quarentena como `data_conexao_raw` |
| `modalidade` | `trim`. O texto de origem fica em `modalidade_origem` |

## Quarentena

A primeira regra que falha define o motivo. A linha sai da Silver.

| Ordem | Motivo | Quando |
| :--- | :--- | :--- |
| 1 | `id_uc_nulo` | `id_uc` nulo ou vazio depois do `trim` |
| 2 | `potencia_invalida` | potência que não converte em `decimal(10,2)`, menor ou igual a zero, ou com escala ambígua (acima de 75 kWp e razão bruta `<= 0,35`, mas que dividida por 1.000 não cai em `[1, 75]` kWp com rendimento `>= 1`) |
| 3 | `energia_injetada_invalida` | injeção que não converte em `decimal(10,2)`, menor ou igual a zero, ou cujo rendimento calculado (`kwh_por_kwp_mes`) estoura `decimal(10,2)` / arredonda para zero |
| 4 | `data_conexao_invalida` | data fora do padrão `yyyy-MM-dd` ou inexistente no calendário |
| 5 | `modalidade_desconhecida` | texto fora do de-para |
| 6 | `uc_inexistente` | `id_uc` sem cadastro depois de tirar o cabeçalho repetido |

Nesta entrega a quarentena tem 0 linhas. Se aparecer linha, a Silver das linhas válidas segue e o notebook avisa, com a contagem por motivo.

A quarentena guarda `id_uc`, `potencia_kwp_raw`, `energia_raw`, `data_conexao_raw`, `modalidade_origem`, `source_file`, `bronze_ingestion_datetime`, `motivo_rejeicao` e `silver_ingestion_datetime`.

## Uma linha por UC (deduplicação determinística)

Se o mesmo `id_uc` vier mais de uma vez na Bronze de geração, a janela prioriza:

1. Data consistente primeiro (`fl_data_inconsistente` falso antes de verdadeiro), evitando que um erro de digitação como `2062-03-10` vença uma data válida como `2025-03-10`.
2. Maior `data_conexao`.
3. `bronze_ingestion_datetime` mais recente.
4. `source_file` e hash SHA-256 de todas as colunas brutas da linha, tornando o desempate determinístico mesmo quando `ingestion_datetime` empata num `overwrite`.

A linha que fica recebe `fl_deduplicado` verdadeiro. A cópia descartada não entra na quarentena: é a mesma UC, e a Bronze continua com as duas. Antes de gravar, Bronze tem de fechar com Silver + quarentena + duplicatas descartadas. Nesta entrega não há duplicata.

## Escala da potência

Potência convertida acima de 75 kWp cujo rendimento bruto (`injeção ÷ potência original`) é menor ou igual a `0,35` kWh por kWp por mês (`RAZAO_ESCALA_MAX = 0.35`) e cuja divisão por 1.000 resulta em `potencia_kwp` entre `1` e `75` kWp com rendimento corrigido `>= 1` é dividida por 1.000, e `fl_correcao_escala` fica verdadeiro. O texto original permanece em `potencia_kwp_raw`.

Se uma linha tiver potência acima de 75 kWp e razão bruta `<= 0,35`, mas a divisão por 1.000 não cair em `[1, 75]` kWp com rendimento `>= 1` (por exemplo, `500` kWp com `100` kWh, que viraria `0,50` kWp), ela é encaminhada à quarentena como `potencia_invalida` (escala ambígua), em vez de derrubar a carga inteira na validação pós-transformação.

Nesta entrega, as 3.475 linhas na escala certa vão de 1,50 a 75,00 kWp, com razão de 11,6 a 110,0 kWh/kWp/mês. As 35 linhas deslocadas (registradas em Wp, entre 3.049,99 e 8.994,91) têm razão bruta entre `0,014` e `0,328` kWh/kWp/mês; depois da divisão por 1.000, caem em 3,05 a 8,99 kWp, com rendimento mediano de 33,3 kWh/kWp/mês.

O teto `0,35` fica colado ao intervalo observado do erro em Wp (`0,014` a `0,328`, três ordens de grandeza abaixo do normal) e preserva uma minigeração real com alto autoconsumo (por exemplo, 300 kWp injetando 200 kWh/mês de excedente, razão `0,67`), que não é dividida.

Nesta entrega são 35 linhas corrigidas.

## Data de conexão

`fl_data_inconsistente` fica verdadeiro quando `data_conexao` é anterior a `2024-01-01` (`DATA_MIN`), posterior à data de execução (`current_date()`), ou anterior à `data_ligacao` da UC. Assim, conexões válidas homologadas após junho de 2026 não são marcadas como inconsistentes, apenas datas no futuro. A linha permanece na Silver.

Nesta entrega nenhuma data sai da janela. As 5 marcas são conexão anterior à ligação: `UC100259`, `UC102507`, `UC106046`, `UC110560` e `UC119180`. A validação principal confere a regra de datas em todas as linhas; a lista das cinco fica apenas como aviso informativo da amostra histórica.

## Modalidade

| Texto na Bronze | Código na Silver |
| :--- | :--- |
| `GERACAO NA PROPRIA UC` | `PROPRIA_UC` |
| `AUTOCONSUMO REMOTO` | `AUTOCONSUMO_REMOTO` |
| `GERACAO COMPARTILHADA` | `COMPARTILHADA` |

Nesta entrega: 3.042, 321 e 147.

## Rendimento

`kwh_por_kwp_mes` é a injeção dividida pela potência já corrigida, convertido com `cast_decimal_10_2_seguro` (arredonda e verifica se cabe em `<= 99.999.999,99` antes de converter para `decimal(10,2)`, evitando exceção no modo ANSI ou `NULL` silencioso). Se a divisão estourar `decimal(10,2)` (como `1.000.000 / 0,01 = 100.000.000,00`) ou arredondar para `<= 0`, a linha vai para a quarentena na triagem (`energia_injetada_invalida`). O patamar em torno de 34 kWh por kWp por mês é o normal deste arquivo, porque a coluna de energia é excedente injetado, não geração bruta.

## Colunas gravadas na Silver

`id_uc`, `potencia_kwp_raw`, `potencia_kwp`, `fl_correcao_escala`, `energia_injetada_kwh_media_mensal`, `kwh_por_kwp_mes`, `data_conexao`, `fl_data_inconsistente`, `modalidade`, `modalidade_origem`, `fl_deduplicado`, `classe`, `municipio`, `source_file`, `bronze_ingestion_datetime`, `silver_ingestion_datetime`.

`fl_correcao_escala`, `fl_data_inconsistente` e `fl_deduplicado` não existem no CSV. A Silver cria as três.

## Validação antes e depois da gravação

A transformação e a validação compartilham a mesma função `calcular_regras_gd`. As checagens rodam sobre `df_silver` **antes** do `overwrite` (junto com o fechamento `Bronze = Silver + quarentena + duplicatas descartadas`) e novamente sobre a tabela gravada. Se a validação pós-escrita ou a escrita falhar, `restaurar_tabela` desfaz a publicação nas duas tabelas via `RESTORE`.

- Uma linha por `id_uc`.
- `potencia_kwp` maior que 0, `energia_injetada_kwh_media_mensal` maior que 0 e `kwh_por_kwp_mes` não nulo e maior que 0.
- `modalidade` dentro dos três códigos.
- `fl_correcao_escala`, `potencia_kwp`, `kwh_por_kwp_mes` e `fl_data_inconsistente` iguais ao retorno de `calcular_regras_gd` em `decimal(10,2)` (comparados com `eqNullSafe`, de modo que um `NULL` nunca passe despercebido).
- Invariante independente pós-correção: toda linha com `fl_correcao_escala` verdadeiro fica com `potencia_kwp` entre `1` e `75` kWp e `kwh_por_kwp_mes >= 1`.
- As cinco UCs conhecidas desta entrega são conferidas depois da gravação apenas como aviso da amostra histórica.
