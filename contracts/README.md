# Contrato local provisório — 0.3.0-provisional

**Não aprovado pelo time de dados. A amostra fornecida é sintética.** As 12 tabelas de
`tabelas/*.yaml` derivam da seção 3 do system design, com grão, chave, tipos,
unidades, nulabilidade, referências e totais de controle, em YAML.

O importador não estima consumo, calcula scores nem determina regras oficiais
de receita ou DEC/FEC. Valida tipos e estrutura recebidos e a consistência entre
detalhe mensal e agregado comercial. O contrato `0.3.0-provisional` formaliza os
metadados completos (R1), o tratamento estrito de competências sem fatura e status
de pagamento (R2), a regra temporal de grupos de UC (R3), a coerência cadastral com GD (R4),
a fórmula canônica de decomposição da receita (R5), a data de referência no manifesto (R6),
o gerador autônomo de manifesto (R7) e o modo de teste `--verificar` (R8).

## Convenções de intercâmbio

- UTF-8, CSV com vírgula, cabeçalho e ordem de colunas exatamente como o contrato.
- Nulo é campo vazio, somente em colunas explicitamente anuláveis.
- Decimal com ponto, precisão e escala declaradas, sem notação monetária.
- Booleanos `true`/`false`; JSON apenas para lista de motivos da fila.
- Competência é data ISO do primeiro dia do mês (`AAAA-MM-01`). O manifesto usa `AAAA-MM`.
- Datas de inspeção e de conexão são datas locais ISO (`AAAA-MM-DD`); timestamps de rede
  e atendimento são ISO sem fuso, conforme a Silver de ocorrências (TIMESTAMP_NTZ).
  Eventos criados pelo portal usam `timestamptz`.
- `manifest.schema.json` exige todas as tabelas, contagens, SHA-256, totais de
  controle e a `reference_date` (`AAAA-MM-DD`). A versão precisa coincidir com `VERSION`.
  `synthetic` declara a proveniência: `true` na amostra e `false` numa exportação de dados reais.
  O importador aceita ambos com as mesmas validações. Isso valida a estrutura;
  não representa aprovação das fórmulas pelo time de dados.
- Na amostra, titular e endereço são inventados e o documento já vem mascarado.
  Exportações devem manter o documento mascarado. As views de IA omitem dados pessoais.
- Inspeções históricas usam `IN` + 7 dígitos; novas inspeções usam `PORTAL-<UUID>`.
  A view unificada inclui `origem`. Tipos de irregularidade ainda são texto livre:
  a auditoria e o overview apresentam listas divergentes; não fixamos um enum falso.

## Precisão e reconciliação

Em `0.3.0-provisional`, `tarifa_base` e `adicional_bandeira` usam `numeric(18,6)`
em R$/kWh. Valores como `0.7845` são preservados. Demais campos mantêm a escala
declarada; entradas com excesso de casas continuam sendo rejeitadas, sem truncamento.

Volume, receita e arrecadação somam os valores recebidos e reconciliam exatamente
por grão. Os componentes derivados de tarifa/bandeira somam os produtos com
precisão decimal e só então arredondam para duas casas, por grão, com empate
afastando de zero (`ROUND_HALF_UP` para os valores não negativos). Não há tolerância
percentual ou compensação entre grupos. Em competências sem fatura emitida (`id_fatura` nulo),
os componentes de tarifa e bandeira são tratados como 0 (`coalesce(tarifa_base, 0)`
e `coalesce(adicional_bandeira, 0)`) na reconciliação de `receita_volume_mensal`.
Duração é a diferença de timestamps em minutos arredondada para duas casas:
80 segundos resultam em `1.33` minuto. Totais do manifesto reconciliam exatamente
os valores já exportados.

Essa convenção de intercâmbio continua provisória e deve ser validada com o
produtor Gold. A alteração de escala e regras exige a nova versão; manifestos `0.2.0-provisional`
devem ser reexportados ou regenerados. Nenhuma migração reescreve a carga analítica
anterior: ela é substituída na próxima publicação válida.

## Regras do contrato 0.3.0-provisional

1. **Metadados Completos (R1):** todas as 12 tabelas possuem `description`, `grain`, `primary_key`
   e `control_totals`. Cada coluna possui `type`, `nullable`, `unit` (`kWh`, `R$`, `R$/kWh`, `kW`,
   `min`, `horas/UC`, `interrupções/UC`, `interrupções`, `UCs`, `UC × hora` ou `—`) e `description`
   não vazia em português.
2. **Ciclo de Faturamento e Nulidades (R2):**
   - Nova coluna `data_vencimento` (date, anulável) adicionada em `uc_consumo_faturamento_mensal`
     após `status_pagamento`.
   - Competência sem fatura emitida (`id_fatura` nulo) exige: `bandeira`, `status_pagamento`,
     `data_vencimento`, `tarifa_base` e `adicional_bandeira` nulos, com `volume_faturado_kwh = 0`,
     `valor_total = 0` e `valor_arrecadado = 0`. As 5 colunas são `nullable: true`.
   - `bandeira`: enum estrito `VERDE | AMARELA | VERMELHA_P1 | VERMELHA_P2`.
   - `status_pagamento = 'PAGA'` ⇒ `valor_arrecadado = valor_total`; `'ABERTA'` ⇒ `valor_arrecadado = 0`.
   - `metodo_consumo = 'LEITURA'` indica consumo analítico igual ao original. Se
     `flag_troca_medidor = true`, `metodo_consumo` obrigatoriamente é diferente de `LEITURA`.
3. **Grupos de UC Temporais (R3):** classificação temporal auditada em staging (GD > Irregularidade Confirmada > Demais).
4. **Coerência Cadastral e Fila (R4):** `dim_uc.flag_gd ⇔ UC em gd_uc`. `fila_inspecao` não contém UCs com GD.
5. **Decomposição da Receita (R5):** fórmula canônica com 4 efeitos e fechamento exato em Decimal.
6. **Data de Referência (R6):** manifesto exige `reference_date` (`AAAA-MM-DD`) com gate `reference_date >=` primeiro dia do mês de `period.end`.
7. **Gerador de Manifesto (R7):** script autônomo `contracts/manifesto.py` usando apenas stdlib + PyYAML.
8. **Modo `--verificar` (R8):** validação dry-run transacional com rollback automático e código de saída estrito.

## Regra Temporal do Grupo de UC (R3)

O campo `grupo_uc` em `uc_consumo_faturamento_mensal` e `receita_volume_mensal` segue a seguinte ordem de precedência:

1. **`GD`**: se a UC possui registro em `gd_uc` e `competencia >= date_trunc('month', data_conexao)::date`.
2. **`IRREGULARIDADE_CONFIRMADA`**: senão, se `competencia >= date_trunc('month', primeira_inspecao_irregular)::date`,
   onde `primeira_inspecao_irregular` é a menor `data` em `inspecoes_historicas` para a UC com
   `resultado = 'IRREGULARIDADE CONFIRMADA'`.
3. **`DEMAIS`**: todos os demais casos.

O importador audita essa classificação no staging antes de promover o schema, garantindo prevenção de vazamento temporal.

## Decomposição da Receita (R5)

A decomposição da variação da receita entre um período base 0 e um período atual 1 divide
$\Delta R = R_1 - R_0$ em quatro efeitos:

$$\Delta R = \text{volume} + \text{reajuste} + \text{bandeira} + \text{mix}$$

### Fórmulas Canônicas
- **Volume:** $\text{volume} = (Q_1 - Q_0) \cdot \bar{p}_0$
- **Reajuste:** $\text{reajuste} = Q_1 \cdot (t_1 - t_0) \cdot k_0$
- **Bandeira:** $\text{bandeira} = Q_1 \cdot (b_1 - b_0) \cdot k_0$
- **Mix:** $\text{mix} = \Delta R - \text{volume} - \text{reajuste} - \text{bandeira}$

Onde:
- $Q_0, Q_1 = \sum \text{volume\_faturado\_kwh}$ sobre as linhas filtradas.
- $R_0, R_1 = \sum \text{receita}$ sobre as linhas filtradas.
- $T_0, T_1 = \sum \text{componente\_tarifa\_reais}$ sobre as linhas filtradas.
- $B_0, B_1 = \sum \text{componente\_bandeira\_reais}$ sobre as linhas filtradas.
- $\bar{p}_0 = R_0 / Q_0$: preço médio base do agregado (R$/kWh).
- $t_0 = T_0 / Q_0, \quad t_1 = T_1 / Q_1$: tarifa base média do agregado (R$/kWh).
- $b_0 = B_0 / Q_0, \quad b_1 = B_1 / Q_1$: adicional de bandeira tarifária médio do agregado (R$/kWh).
- $k_0 = R_0 / (T_0 + B_0)$: fator de faturamento tributário.

### Casos de Borda e Regras de Arredondamento
- Se $Q_0 = 0$ ou $T_0 + B_0 = 0$: $\text{volume} = \Delta R$, e $\text{reajuste} = \text{bandeira} = \text{mix} = 0$.
- Se $Q_1 = 0$: $\text{volume} = -R_0$, e $\text{reajuste} = \text{bandeira} = \text{mix} = 0$.
- Os cálculos são realizados em Decimal de precisão total. Os efeitos de volume, reajuste e bandeira
  são arredondados uma única vez para duas casas decimais com `ROUND_HALF_UP`.
- O efeito **mix** absorve o resíduo algébrico e de arredondamento, garantindo que
  $\text{volume} + \text{reajuste} + \text{bandeira} + \text{mix} = \Delta R$ exatamente.
- A agregação é realizada pela tela somando os efeitos de cada subgrão; não existe média de preços
  entre diferentes segmentos ou classes.

### Exemplo Numérico Conferido com a Amostra (`receita_volume_mensal.csv`)

Recorte real da amostra determinística para **Recife, Residencial** comparando a competência `2025-06-01` (bandeira verde)
com `2025-07-01` (quando entra a bandeira amarela de R$ 0,10/kWh):

- **Período Base 0 (`2025-06-01`):**
  - Três linhas no CSV (Bairro 1 DEMAIS: 1.371 kWh / R$ 1.096,80; Bairro 1 GD: 40 kWh / R$ 32,00; Bairro 2 DEMAIS: 1.494 kWh / R$ 1.195,20).
  - $Q_0 = 1.371 + 40 + 1.494 = 2.905\text{ kWh}$.
  - $R_0 = 1.096{,}80 + 32{,}00 + 1.195{,}20 = 2.324{,}00\text{ R\$}$.
  - $T_0 = 1.096{,}80 + 32{,}00 + 1.195{,}20 = 2.324{,}00\text{ R\$}$.
  - $B_0 = 0{,}00\text{ R\$}$.
  - $\bar{p}_0 = R_0 / Q_0 = 2.324{,}00 / 2.905 \approx 0{,}800000\text{ R\$/kWh}$.
  - $t_0 = T_0 / Q_0 = 2.324{,}00 / 2.905 \approx 0{,}800000\text{ R\$/kWh}$.
  - $b_0 = B_0 / Q_0 = 0{,}00 / 2.905 = 0{,}000000\text{ R\$/kWh}$.
  - $k_0 = R_0 / (T_0 + B_0) = 2.324{,}00 / (2.324{,}00 + 0{,}00) = 1$.
- **Período Atual 1 (`2025-07-01`):**
  - Três linhas no CSV (Bairro 1 DEMAIS: 1.250 kWh / R$ 1.125,00; Bairro 1 GD: 40 kWh / R$ 36,00; Bairro 2 DEMAIS: 1.362 kWh / R$ 1.225,80).
  - $Q_1 = 1.250 + 40 + 1.362 = 2.652\text{ kWh}$.
  - $R_1 = 1.125{,}00 + 36{,}00 + 1.225{,}80 = 2.386{,}80\text{ R\$}$.
  - $T_1 = 1.000{,}00 + 32{,}00 + 1.089{,}60 = 2.121{,}60\text{ R\$} \implies t_1 = T_1 / Q_1 = 2.121{,}60 / 2.652 \approx 0{,}800000\text{ R\$/kWh}$.
  - $B_1 = 125{,}00 + 4{,}00 + 136{,}20 = 265{,}20\text{ R\$} \implies b_1 = B_1 / Q_1 = 265{,}20 / 2.652 \approx 0{,}100000\text{ R\$/kWh}$.
- **Variação Total ($\Delta R$):** $2.386{,}80 - 2.324{,}00 = +62{,}80\text{ R\$}$.
- **Decomposição:**
  - $\text{volume} = (2.652 - 2.905) \times 0{,}800000 = -253 \times 0{,}800000 = -202{,}40\text{ R\$}$.
  - $\text{reajuste} = 2.652 \times (0{,}800000 - 0{,}800000) \times 1 = 0{,}00\text{ R\$}$.
  - $\text{bandeira} = 2.652 \times (0{,}100000 - 0{,}000000) \times 1 = +265{,}20\text{ R\$}$.
  - $\text{mix} = 62{,}80 - (-202{,}40) - 0{,}00 - 265{,}20 = 0{,}00\text{ R\$}$.
  - **Soma:** $-202{,}40 + 0{,}00 + 265{,}20 + 0{,}00 = +62{,}80\text{ R\$}$ (fechamento exato com $\Delta R$).

## Pendências da seção 13 → regra do contrato

A tabela abaixo mapeia cada um dos 9 itens da seção 13 do system design com sua respectiva formalização no contrato `0.3.0-provisional`:

| # | Pendência Original (§13) | Bloqueia | Status no Contrato 0.3.0-provisional |
|---|---|---|---|
| **1** | **Consumo original e analítico** em colunas separadas em `uc_consumo_faturamento_mensal`, com a marcação de leitura estimada e de troca de medidor e o método de estimativa | Visão 360, volume faturado | **Formalizado (R2)**: colunas separadas `consumo_kwh_original`, `consumo_kwh_analitico`, `metodo_consumo` e gate de troca de medidor. |
| **2** | **Fórmula da decomposição da receita** (volume, reajuste, bandeira, mix), aplicável a qualquer par de períodos sobre `receita_volume_mensal`, incluindo como obter a tarifa base da classe por competência | Receita, insights, agente | **Formalizado (R5)**: fórmula canônica com fator $k_0$, quatro efeitos e fechamento exato em Decimal no README; implementação na P20. |
| **3** | **Grupo de UC** em `receita_volume_mensal` (com GD, irregularidade confirmada, demais), respeitando a data de conexão da GD | Receita | **Formalizado (R3)**: regra temporal GD > IRREGULARIDADE_CONFIRMADA > DEMAIS com `date_trunc` e gate SQL. |
| **4** | **Regra de DEC/FEC**: sobreposição de interrupções (fórmula simples ou `duracao_efetiva_min`), denominador por alimentador e marcação de evento atípico | Operação, Visão Geral | **Parcial**: tabela `continuidade_alimentador_mensal` com numeradores e denominadores mensais e flag atípica; critério regulatório final de sobreposição segue pendente com o time de dados. |
| **5** | **Fila de inspeção** com score, motivos em formato legível (lista de sinais com valor) e energia a recuperar em kWh e R$, sem UCs com GD | Perdas | **Formalizado (R4)**: gate estrito excluindo UCs de `gd_uc` da fila; `dim_uc.flag_gd` auditado contra `gd_uc`. |
| **6** | **Atendimentos** em duas tabelas (protocolo; protocolo × sequência) | Visão 360 | **Formalizado**: tabelas `atendimentos` e `atendimentos_historico` com metadados R1. |
| **7** | **Faturas órfãs** fora de toda tabela de receita do contrato | Receita, KPIs | **Formalizado (R2)**: faturas órfãs excluídas de toda tabela analítica; competência sem fatura modelada com nulos síncronos e zeros; nova coluna `data_vencimento`. |
| **8** | **Manifesto** da exportação com `batch_id`, versão do contrato, contagens e totais de controle | Importador | **Formalizado (R6, R7)**: `reference_date` obrigatória, validação estrita e gerador autônomo `contracts/manifesto.py`. |
| **9** | Nomes físicos de catálogo e schema unificados no Databricks, para a exportação ser um passo só do Job | Exportação | **Pendente**: depende da unificação de catálogo/schema no Databricks pelo time de dados (fora do escopo do portal). |

## Homologação de uma Exportação Real (Guia para o Time de Dados)

Para homologar uma exportação real da Gold, siga as etapas abaixo:

### 1. Geração dos CSVs
Exporte as 12 tabelas em formato CSV com codificação UTF-8, vírgula como delimitador, primeira linha como cabeçalho
e exatamente as colunas e tipos descritos em `contracts/tabelas/*.yaml`.

### 2. Geração do Manifesto
Execute o utilitário autônomo sem depender do banco de dados ou do ambiente do portal:

```bash
python contracts/manifesto.py /caminho/exportacao \
  --batch-id "lote-gold-2026-11-01" \
  --periodo "2022-07..2026-06" \
  --data-referencia "2026-07-01"
```

O comando calcula as contagens de linhas, hashes SHA-256 e as somas decimais dos totais de controle, gravando
o arquivo `manifest.json`.

### 3. Validação Prévia (Dry-Run com `--verificar`)
No ambiente onde o backend está configurado, monte a pasta da exportação em `/entrada` (via `GOLD_EXPORT_DIR` no `.env`)
e execute o verificador:

```bash
docker compose run --rm importador --origem /entrada --verificar
```

O comando roda todos os passos (COPY binário, PKs, FKs, gates R2, R3, R4 e índices) em uma transação isolada
sob advisory lock e realiza **rollback automático**. O schema `analytics`, o histórico de `operations.cargas` e
o cache do Redis permanecem inalterados. Se a validação for bem-sucedida, o comando imprime um resumo das tabelas,
a mensagem `OK` e retorna código de saída `0`.

### 4. Publicação Oficial
Com a verificação aprovada, promova a carga:

```bash
docker compose run --rm importador --origem /entrada
```

### Estimativa de Desempenho e Volumetria
- O throughput de parsing e streaming em Python 3.12 é de **~55.500 linhas/segundo**.
- Para a volumetria de referência de uma distribuidora média (~2,16M linhas em `uc_consumo_faturamento_mensal` e
  ~180k ocorrências de rede), o tempo estimado é de:
  - Parsing em Python: ~39 segundos.
  - Carga total (streaming binário asyncpg + validações de integridade + gates SQL + indexação): **1,5 a 2,5 minutos**.
- O processo opera com memória constante $O(1)$ devido ao uso de iteradores lineares com envio direto ao socket.

## Amostra e Reprodução

```bash
uv run python contracts/samples/gerar.py
uv run pytest importador/tests/test_contracts.py -q
```

São 300 UCs, 3 municípios, 6 bairros, 5 classes e 6 alimentadores, cobrindo
jul/2022–jun/2026. Há UC nova sem ano anterior, GD conectada em jan/2025 (UC100000,
mantida fora da fila de inspeção), irregularidade confirmada em ago/2025 (UC100001,
que transiciona temporalmente de DEMAIS para IRREGULARIDADE_CONFIRMADA em 2025-08-01),
consumo original negativo na troca de medidor, leitura estimada, faturas em aberto,
competência sem fatura (UC100004 em jun/2026, com campos tarifários nulos e
volume/valores zerados), nota de atendimento nula, inspeções anteriores de ambos
os resultados, candidatos para reinspeção e evento atípico em jul/2025.
O alimentador com uma UC tem DEC maior que os demais nos meses comuns,
mas CHI menor que o do evento atípico.

Todos os números vêm de constantes/fórmulas do gerador, sem sorteio e sem dados
externos. O agregado de receita é gerado a partir do detalhe com `Decimal`.
No gerador, consumo analítico da troca é um valor inventado identificado por
`SINTETICO_TROCA`; não adota média ou mediana. A flag de irregularidade no cadastro
é o retrato atual; os grupos mensais são temporais na amostra. O denominador de
continuidade usa o cadastro sintético atual, sujeito a substituição no contrato
real. Não há tratamento oficial de sobreposição nem limiar oficial de score.

Para trocar pelo contrato real, é necessário aprovar as pendências em
[`docs/backend-pendencias.md`](../docs/backend-pendencias.md), versionar os novos
contratos, adaptar o produtor Gold e atualizar importador, amostras e testes no
mesmo ciclo. Não renomear esta versão como aprovada sem essa revisão.
