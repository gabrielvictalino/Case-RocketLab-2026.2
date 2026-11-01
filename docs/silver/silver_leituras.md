# Silver de leituras (`` `v-energy`.silver.tb_leituras ``)

**Notebook:** `data-engineering/bronze_to_silver/bronze-to-silver-leituras.ipynb`
**Fonte:** `` `v-energy`.bronze.tb_leituras `` (2.182.468 linhas, todas as colunas como texto) e `` `v-energy`.bronze.tb_medidores `` (cadastro de medidores).
**Destino:** `` `v-energy`.silver.tb_leituras `` (Delta, carga completa com `overwrite`).
**Base das regras:** seção 5 de `docs/auditoria_dados/auditoria_leituras.md`.

---

## 1. Contagem antes e depois de cada passo

| Passo | Regra | Linhas antes | Linhas depois | Diferença |
| :--- | :--- | :---: | :---: | :---: |
| 1 | Remove duplicatas exatas sobre as 9 colunas de negócio | 2.182.468 | 2.160.945 | −21.523 |
| 2 | Descarta leituras cujo `id_medidor` não existe em `` `v-energy`.bronze.tb_medidores `` (clones `LTX`/`MD9…`) | 2.160.945 | 2.152.336 | −8.609 |
| 3 a 8 | Normalização, datas, tipagem, sinal e flags (nenhuma linha é removida) | 2.152.336 | 2.152.336 | 0 |

Depois do passo 2 sobra exatamente **uma leitura por (`id_uc`, `mes_referencia`)**, com `id_leitura` único e nenhum `LTX` remanescente.

---

## 2. Regras aplicadas

### 2.1. Leitura fixada (`VERSION AS OF`), duplicatas exatas e clones `LTX`
* A leitura fixa a versão atual das duas tabelas de entrada (`VERSION AS OF` em `` `v-energy`.bronze.tb_leituras `` e `` `v-energy`.bronze.tb_medidores ``), garantindo que contagens, validações e escrita leiam exatamente o mesmo snapshot da Bronze.
* `dropDuplicates` sobre `id_leitura`, `id_uc`, `id_medidor`, `data_leitura`, `mes_referencia`, `leitura_anterior`, `leitura_atual`, `consumo_kwh` e `tipo_leitura`. As cópias estão sempre no mesmo arquivo, então `source_file` não muda.
* `left_semi` com os `id_medidor` distintos de `` `v-energy`.bronze.tb_medidores ``. Os 8.609 clones apontam para medidores `MD9…` inexistentes e sempre têm uma gêmea legítima `LT` com os mesmos valores, então nenhum consumo se perde.

### 2.2. `leitura_anterior`
`''` (que o leitor CSV do Spark já entrega como null), `N/A`, `NULL` e `-1` viram null **antes** da conversão para inteiro. Na base limpa:

| Representação | Bruto | Base limpa |
| :--- | :---: | :---: |
| `N/A` | 8.269 | 8.149 |
| vazio / null | 8.218 | 8.101 |
| `NULL` | 8.180 | 8.073 |
| `-1` | 8.068 | 7.962 |
| **Total** | **32.735** | **32.285** |

Nenhum outro valor deixa de converter.

### 2.3. `data_leitura`
Conversão pela expressão regular de cada valor, com `try_to_timestamp` e `to_date`:

| Regex | Formato | Base limpa |
| :--- | :--- | :---: |
| `^\d{4}-\d{2}-\d{2}$` | `yyyy-MM-dd` | 1.894.056 |
| `^\d{2}\.\d{2}\.\d{4}$` | `dd.MM.yyyy` | 86.433 |
| `^\d{2}/\d{2}/\d{4}$` | `dd/MM/yyyy` | 85.936 |
| `^\d{2}-\d{2}-\d{4}$` | **`MM-dd-yyyy`** | 85.911 |

Resultado: nenhuma data nula e o mês da data igual a `mes_referencia` em 100% das linhas.

### 2.4. `consumo_kwh` e correção de sinal
* O sufixo `.0` é removido antes da conversão para inteiro (1.717 valores na base limpa). Nenhum valor tem parte decimal diferente de `.0`.
* O sinal é invertido **só** quando `leitura_anterior` é numérica, `leitura_anterior ≤ leitura_atual` e `consumo_kwh = −(atual − anterior)` exato. Essas linhas ficam com `flag_sinal_corrigido = true`, e o valor original é `−consumo_kwh`.
* A diferença de ±1 kWh entre `consumo_kwh` e `atual − anterior` é mantida (arredondamento, 518.042 leituras positivas na base limpa). Nenhuma diferença passa de 1 kWh. `consumo_kwh` é a fonte de verdade.

### 2.5. Flags dos consumos negativos não corrigidos
Essas linhas mantêm o valor original de `consumo_kwh`, **sem** inversão, **sem** estimativa e **sem** `abs()`:

| Flag | Regra | Bruto | Base limpa |
| :--- | :--- | :---: | :---: |
| `flag_sinal_corrigido` | negativo, leituras crescentes e módulo exato (sinal invertido no passo 2.4) | 1.349 | 1.334 |
| `flag_troca_medidor` | negativo e `leitura_anterior > leitura_atual` | 6.327 | 6.215 |
| `flag_sem_leitura_anterior` | negativo e `leitura_anterior` nula | 115 | 114 |
| `flag_sinal_nao_confirmado` | negativo, leituras crescentes e módulo com ±1 kWh de diferença | 359 | 353 |

* A diferença entre o bruto e a base limpa vem das duplicatas exatas e dos clones `LTX` dessas linhas. Nas trocas, são 78 duplicatas e 34 clones (6.327 − 112 = 6.215).
* As 114 sem leitura anterior são **84 trocas de medidor** (a UC tem medidor retirado no mesmo mês) e **30** com o padrão `-N.0`. Somando, 6.215 + 84 = 6.299, exatamente o número de medidores com `status = RETIRADO` no cadastro, e cada um deles cai na mesma UC e no mesmo mês de exatamente uma dessas leituras. Contar por `data_retirada` preenchida dá 19.799, porque os medidores `ATIVO` usam a sentinela `9999-12-31` (seção 6 da auditoria).
* No mês da troca, o `id_medidor` da leitura já é o medidor **novo** (`ATIVO`). O medidor retirado é o anterior da UC, então o cruzamento da flag com o cadastro deve ser feito por (`id_uc`, mês da retirada), e não por `id_medidor`.
* Cada linha tem no máximo uma flag, e **nenhum consumo negativo fica sem flag**. Depois da correção, as 6.682 leituras com consumo negativo são as 6.215 + 114 + 353 marcadas.

### 2.6. Tipagem final

| Coluna | Tipo | Observação |
| :--- | :--- | :--- |
| `id_leitura`, `id_uc`, `id_medidor`, `tipo_leitura` | `STRING` | sem alteração (`tipo_leitura` validada em `REAL` / `ESTIMADA`) |
| `data_leitura` | `DATE` | |
| `mes_referencia` | `STRING` | `AAAA-MM`, validado por regex |
| `leitura_anterior`, `leitura_atual`, `consumo_kwh` | `INT` | `leitura_anterior` nula quando ausente |
| `flag_sinal_corrigido`, `flag_troca_medidor`, `flag_sem_leitura_anterior`, `flag_sinal_nao_confirmado` | `BOOLEAN` | nunca nulas |
| `source_file`, `ingestion_datetime` | `STRING`, `TIMESTAMP` | herdadas da Bronze |

---

## 3. Validações do notebook

**Antes de gravar** (qualquer falha interrompe o notebook e a Silver atual não é tocada):
* contagem de cada passo: 2.182.468 → 2.160.945 → 2.152.336;
* 2.152.336 linhas, 2.152.336 `id_leitura` distintos e 2.152.336 pares (`id_uc`, `mes_referencia`) distintos;
* nenhuma data nula e nenhum mês de `data_leitura` diferente de `mes_referencia`;
* `mes_referencia` no formato `AAAA-MM` e `tipo_leitura` dentro de `REAL` / `ESTIMADA` (1.761.712 `REAL` e 390.624 `ESTIMADA`) em todas as linhas;
* nenhuma `leitura_anterior` não numérica depois da normalização, nenhuma `leitura_atual` nula e nenhum `consumo_kwh` fora do padrão `-?\d+(\.0)?`;
* as linhas de `flag_sinal_nao_confirmado` diferem de `atual − anterior` em exatamente 1 kWh;
* nenhum consumo positivo tem `leitura_anterior > leitura_atual` nem diferença maior que 1 kWh em relação a `atual − anterior` (premissas das flags, que só olham os consumos negativos);
* contagens das flags iguais às da tabela 2.5, no máximo uma flag por linha e nenhum consumo negativo sem flag.

**Depois de gravar (com `RESTORE`):** confere se a tabela gravada tem exatamente as colunas do contrato (`SILVER_COLUMNS`) e as 2.152.336 linhas. Se divergir, reverte a tabela para a versão anterior ao `overwrite` (`RESTORE TABLE ... TO VERSION AS OF`), ou a remove (`DROP TABLE IF EXISTS`) se era a primeira carga.

---

## 4. Reprodução local

Os números acima foram reproduzidos fora do Databricks a partir dos CSVs brutos (todas as colunas como texto):
* com DuckDB, aplicando as mesmas regras em SQL;
* com PySpark local, executando as células do próprio notebook sobre os CSVs (a gravação é simulada).

Os dois resultados batem entre si e com as contagens da auditoria.

---

## 5. Uso e decisões pendentes

* **Somar consumo:** os meses com `flag_troca_medidor`, `flag_sem_leitura_anterior` ou `flag_sinal_nao_confirmado` ainda têm o valor negativo original. Na camada Gold, filtre `consumo_kwh >= 0` sem flags impeditivas (`volume_analise_kwh`) ou impute pela mediana da própria UC (`consumo_kwh_analitico`). **Nunca use `abs()`**: no mês da troca o valor absoluto é a leitura acumulada do medidor antigo, e isso infla o volume dos últimos 12 meses em ≈ 177%.
* **Dependência:** o notebook lê `` `v-energy`.bronze.tb_leituras `` e `` `v-energy`.bronze.tb_medidores `` da Bronze unificada (`Landing_to_Bronze.ipynb`, PR #14).
