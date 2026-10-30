# Relatório de Auditoria e Qualidade de Dados (`geracao_distribuida.csv`)

**Escopo da Análise:** Auditoria estrutural e de regras de negócio do cadastro de geração distribuída, feita sobre o bruto (colunas lidas como texto).
**Volume Total:** 3.510 registros em um único arquivo CSV. Uma linha por UC. Não é série mensal: cada linha traz a média mensal de energia injetada.
**Período Coberto nos Dados:** `data_conexao` de 2024-01-01 a 2026-06-27.
**Destino na Bronze:** `` `v-energy`.bronze.tb_geracao_distribuida `` (conteúdo preservado, mais `source_file` e `ingestion_datetime`).

---

## 1. Sumário Executivo de Anomalias

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção (%) | Criticidade |
| :--- | :--- | :---: | :---: | :---: |
| **`potencia_kwp`** | Vírgula decimal (`"5,03"`), entre aspas no CSV | 316 | 9,00% | **Alta** |
| **`potencia_kwp`** | Escala mil vezes grande (3.050 a 8.995 no lugar de 3,05 a 8,99 kWp) | 35 | 1,00% | **Alta** |
| **`data_conexao` × cadastro** | Conexão anterior à `data_ligacao` da UC | 5 | 0,14% | **Média** |
| **Tipagem** | Potência, injeção e data chegam como texto | 3.510 | 100,0% | **Média** |

**Atributos íntegros:** 3.510 `id_uc` distintos, todos presentes no cadastro e todos com status `ATIVA`. Nenhum campo vazio. `data_conexao` inteira em `AAAA-MM-DD`, dentro de 2024-01-01 a 2026-06-27. `modalidade` em três valores estáveis. `energia_injetada_kwh_media_mensal` já usa ponto decimal, sem vírgula e sem valor menor ou igual a zero.

---

## 2. Diagnóstico Estrutural

Um arquivo com cabeçalho de 5 colunas, separador vírgula, quebra de linha LF. As 316 potências com vírgula vêm entre aspas (`"5,03"`), então continuam um campo só. As outras linhas não usam aspas. Todas as 3.510 linhas têm os cinco campos preenchidos.

| Coluna | Significado neste arquivo |
| :--- | :--- |
| `id_uc` | Unidade com sistema solar conectado à rede |
| `potencia_kwp` | Potência instalada, em kWp |
| `data_conexao` | Data em que a distribuidora homologou a conexão |
| `modalidade` | Onde o crédito da energia injetada é usado |
| `energia_injetada_kwh_media_mensal` | Média mensal do que foi para a rede, em kWh. É excedente, não a geração bruta do painel |

| `modalidade` | Linhas |
| :--- | :---: |
| `GERACAO NA PROPRIA UC` | 3.042 |
| `AUTOCONSUMO REMOTO` | 321 |
| `GERACAO COMPARTILHADA` | 147 |

Conexões por ano: 1.845 em 2024, 1.304 em 2025 e 361 em 2026.

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Vírgula decimal em `potencia_kwp`

316 valores usam vírgula (`UC100150`: `"5,03"`, `UC100276`: `"6,82"`, `UC100415`: `"8,46"`). Os outros 3.194 usam ponto (`6.31`). O número é 5,03 kWp, não 503. A vírgula está entre aspas no arquivo e a Bronze guarda o texto `5,03`.

`energia_injetada_kwh_media_mensal` não tem esse problema: as 3.510 linhas usam ponto.

### 3.2. Escala de `potencia_kwp`

Escala aqui é a unidade em que o número foi escrito. kWp é quilowatt-pico. Um telhado residencial nesta base fica entre 1,50 e 75,00 kWp. Não há nenhum valor entre 75 e 3.049.

35 linhas saltam para a faixa de 3.049,99 a 8.994,91. A injeção dessas linhas continua a de telhado (dezenas ou poucas centenas de kWh por mês), não a de uma usina de milhares de kWp. Dividir o número por 1.000 devolve 3,05 a 8,99 kWp.

| Exemplo | Texto na origem | Lido como kWp | Depois de ÷ 1.000 | Injeção média |
| :--- | :--- | ---: | ---: | ---: |
| `UC142950` | `3049.99` | 3.049,99 | 3,05 | 348,70 kWh |
| `UC119197` | `8908.67` | 8.908,67 | 8,91 | 178,50 kWh |
| `UC120737` | `8994,91` | 8.994,91 | 8,99 | 298,30 kWh |

Dessas 35, 31 usam ponto e 4 usam vírgula. A vírgula continua sendo decimal. O erro é a grandeza, não o separador. `UC120737` junta os dois: vírgula decimal e escala mil vezes grande.

O rendimento (injeção ÷ potência) das 3.475 linhas na escala certa tem mediana de 33,8 kWh por kWp por mês. Nas 35, depois da divisão por 1.000, a mediana fica em 33,3. Sem a divisão, o mesmo rendimento cairia para cerca de 0,03, incompatível com o resto do arquivo.

Há 44 UCs que injetam mais de 2.000 kWh por mês. A potência delas está entre 22,78 e 75,00 kWp, na escala certa. São sistemas grandes. Não entram na correção.

A correção de escala é essa divisão por 1.000, com a marca `fl_correcao_escala`. O texto original permanece em `potencia_kwp_raw`. A regra combina potência convertida acima de 75 kWp e rendimento bruto (injeção ÷ potência original) abaixo de 1 kWh por kWp por mês.

### 3.3. Data de conexão anterior à ligação

`data_conexao` converte em todas as linhas e nenhuma cai fora de 2024-01-01 a 2026-06-30. Em 5 UCs a conexão é anterior à `data_ligacao` do cadastro. A UC já aparece como `ATIVA` e `Residencial`.

| `id_uc` | `data_conexao` | `data_ligacao` | Município |
| :--- | :--- | :--- | :--- |
| `UC100259` | 2024-01-10 | 2025-03-24 | Ipojuca |
| `UC102507` | 2024-06-03 | 2024-09-01 | Jaboatão dos Guararapes |
| `UC106046` | 2024-04-12 | 2025-07-29 | Igarassu |
| `UC110560` | 2024-09-12 | 2024-12-09 | Recife |
| `UC119180` | 2024-09-18 | 2024-11-12 | Olinda |

Data inconsistente é essa marca, `fl_data_inconsistente`. A linha permanece na Silver. Apagar a UC esconderia o sistema solar da visão 360. A flag também cobre uma `data_conexao` anterior a 2024-01-01 ou no futuro (`> current_date()`). Nesta entrega nenhuma data cai fora dessa faixa, então as 5 linhas acima são o conjunto inteiro.

A `data_ligacao` usada na comparação vem de `tb_unidades_consumidoras`. Esse cadastro repete o cabeçalho numa linha (`id_uc` vale `id_uc` e `data_ligacao` vale o texto `data_ligacao`). Essa linha fica de fora da consulta. Cem UCs com solar aparecem mais de uma vez no cadastro, e as cópias concordam em `data_ligacao`, `classe` e `municipio`.

---

## 4. Plano aplicado na Silver

Notebook: `data-engineering/Bronze_to_Silver.ipynb`. Tabela: `` `v-energy`.silver.tb_geracao_distribuida ``. Grão: uma linha por `id_uc`.

1. Trocar a vírgula de `potencia_kwp` por ponto e converter para `decimal(10,2)`. Guardar o texto em `potencia_kwp_raw`.
2. Se a potência convertida for maior que 75 e a razão bruta (injeção ÷ potência original) for menor que 1 kWh por kWp por mês, dividir por 1.000 e ligar `fl_correcao_escala`.
3. Trocar eventual vírgula de `energia_injetada_kwh_media_mensal` por ponto e converter para `decimal(10,2)`.
4. Converter `data_conexao` para `date`. Ligar `fl_data_inconsistente` quando a data é anterior a 2024-01-01, posterior a `current_date()` ou anterior à `data_ligacao`.
5. Traduzir a modalidade para `PROPRIA_UC`, `AUTOCONSUMO_REMOTO` ou `COMPARTILHADA`. O texto de origem fica em `modalidade_origem`.
6. Calcular `kwh_por_kwp_mes` depois da correção de escala, só como auditoria. O patamar perto de 34 kWh por kWp por mês é o normal deste arquivo e não reprova linha.

Valor que não converte, potência ou injeção menor ou igual a zero, modalidade fora da lista ou `id_uc` sem cadastro vai para `` `v-energy`.silver.tb_geracao_distribuida_quarentena ``. Nesta entrega a quarentena fica vazia: 3.510 linhas na Silver, 35 com correção de escala e 5 com data inconsistente.

A média injetada classifica a UC. Ela não é subtraída do consumo da leitura nem do valor da fatura.
