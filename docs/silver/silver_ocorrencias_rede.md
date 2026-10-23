# Camada Silver: `ocorrencias_rede`

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/bronze_to_silver/bronze-to-silver-ocorrencias-rede.ipynb` |
| **Entrada** | `venergy.bronze.ocorrencias_rede` (180.000 linhas, todas as colunas em texto) |
| **Saída** | `venergy.silver.ocorrencias_rede` (180.000 linhas, tipada e padronizada) |
| **Grão** | Uma linha por ocorrência (`id_ocorrencia` único). Pela definição do case, cada registro é **uma UC interrompida** |
| **Depende de** | Bronze de ocorrências (PR #9) |
| **Usada por** | Gold de continuidade (DEC/FEC por alimentador ao longo do tempo) e visão 360 da UC ("a rua dele teve falta de luz?") |
| **Auditoria de origem** | `docs/auditoria_dados/auditoria_ocorrencias_rede.md` |

---

## 1. Resumo: o que muda da Bronze para a Silver

| | Bronze | Silver |
| :--- | :--- | :--- |
| Datas | texto `yyyy-MM-dd HH:mm:ss` | **`TIMESTAMP_NTZ`** (hora local, sem fuso) |
| `duracao_min` | texto; 16.200 valores com sufixo `" min"` | **inteiro** em 100% das linhas |
| `causa` | 6 causas + 4 formas de ausência (`''`, `-`, `N/A`, `NULL`) | 6 causas + **`NAO INFORMADA`** (5.400) |
| Sobreposição na mesma UC | soma direta conta **43.561 min em dobro** | `flag_sobreposicao` (331) e **`duracao_efetiva_min`** |
| Evento de 2025-07 | misturado ao resto | **`flag_mes_atipico_alimentador`** (12.836 ocorrências) |
| Colunas de apoio | — | `sigla_municipio` (14 siglas) e `ano_mes` (48 meses) |

---

## 2. Regras de transformação

### 2.1. Datas como `TIMESTAMP_NTZ` (achado 3.4)
As datas chegam num formato único e limpo. A conversão usa `try_to_timestamp`, que transforma valor inválido em nulo (barrado pela validação) em vez de quebrar a execução, e grava como **`TIMESTAMP_NTZ`**.

> **Por que sem fuso:** os horários são locais de Recife e a origem não informa fuso. Com o `TIMESTAMP` comum, o Spark interpreta o horário no fuso da sessão, e uma sessão configurada com outro fuso, ou uma exportação para outro banco, pode deslocar as horas. Com `NTZ`, `2022-07-01 16:33` é sempre `2022-07-01 16:33`. Isso foi testado trocando o fuso da sessão.

### 2.2. `duracao_min` como inteiro (achado 3.1)
A expressão `^\s*(\d+)\s*(min)?\s*$`, sem diferenciar maiúsculas, aceita `"217"`, `"217 min"` e `"217 MIN"`. Depois vem `try_cast` para inteiro. Os 16.200 valores com sufixo (1.946.610 minutos) entram corretamente. Um `cast` direto os transformaria em nulo e subestimaria o DEC em 9% das ocorrências. Qualquer outro formato (ex.: `"75 minutos"`) é barrado.

A validação confirma que a duração é **igual a `data_encerramento − data_abertura`** em 100% das linhas.

### 2.3. `causa` com ausência explícita (achado 3.2)
As 4 formas de ausência (`''`, `-`, `N/A`, `NULL`, num total de 5.400) viram **`NAO INFORMADA`**. O texto também passa por `trim`, maiúsculas e remoção de acentos, então `" n/a "` também é reconhecido.

| Bronze | Silver | Ocorrências |
| :--- | :--- | :---: |
| `-` | `NAO INFORMADA` | 1.363 |
| vazio | `NAO INFORMADA` | 1.356 |
| `N/A` | `NAO INFORMADA` | 1.341 |
| `NULL` | `NAO INFORMADA` | 1.340 |
| demais (6 causas) | iguais | 174.600 |

> **Decisão:** usei a categoria explícita em vez de `null` (a auditoria deixou a escolha para o time). Com isso, `GROUP BY causa` mostra a ausência como uma linha legível, e consultas como `WHERE causa <> 'CLIMATICA'` não perdem linhas por causa de nulo. Isso importa para o agente de IA, que escreve SQL sozinho. `NAO INFORMADA` (sem registro) continua separada de `NAO IDENTIFICADA` (causa investigada e não encontrada). Para usar `null`, basta trocar `CAUSA_NAO_INFORMADA` na configuração.

### 2.4. Interrupções sobrepostas na mesma UC (achado 4.2)
Para cada ocorrência, o notebook calcula o **maior encerramento entre as ocorrências anteriores da mesma UC** (`max(data_encerramento)` numa janela ordenada por abertura). Comparar só com a ocorrência imediatamente anterior deixaria passar 2 casos.

* **`flag_sobreposicao`:** a ocorrência começou enquanto a UC já estava sem energia (331 casos, 268 em 2025-07).
* **`duracao_efetiva_min`:** minutos desta ocorrência que **ainda não** estavam cobertos (`encerramento − maior_fim_anterior`, ou zero).

Exemplo real, a `UC107537`:

| Ocorrência | Início | Fim | `duracao_min` | `flag_sobreposicao` | `duracao_efetiva_min` |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `OC00121286` | 21/07 08:10 | 22/07 01:26 | 1.036 | false | 1.036 |
| `OC00125971` | 21/07 14:21 | 21/07 15:53 | 92 | true | **0** (contida na anterior) |
| `OC00122507` | 21/07 22:10 | 22/07 02:46 | 276 | true | **80** (01:26 → 02:46) |
| **Total** | | | 1.404 | | **1.116** = 08:10 → 02:46 |

Em toda a base, `SUM(duracao_min)` = 21.392.087 min e **`SUM(duracao_efetiva_min)` = 21.348.526 min**, que é exatamente a união dos intervalos de cada UC. São 43.561 min que uma soma direta contaria em dobro.

### 2.5. Meses atípicos por alimentador (achado 4.1)
Para cada alimentador, o notebook conta as ocorrências de cada mês **entre o primeiro e o último mês em que ele aparece** (meses sem ocorrência nesse intervalo entram com zero) e calcula a **mediana mensal**. Um mês é atípico quando passa de **5× essa mediana** (`LIMIAR_MES_ATIPICO`).

| Alimentador | Mês | Ocorrências | Mediana mensal | Razão |
| :--- | :---: | :---: | :---: | :---: |
| `ALM-REC-008` | 2025-07 | 6.887 | 28 | 246× |
| `ALM-SAO-004` | 2025-07 | 3.351 | 27 | 124× |
| `ALM-JAB-004` | 2025-07 | 2.598 | 27 | 96× |

Fora esses 3, nenhum mês de nenhum alimentador passa de **2,3×** a própria mediana, nem os picos difusos de 2025-11 e 2026-02. O limite de 5× separa os dois grupos com folga.

> **Por que limitar ao período do alimentador:** se um alimentador entrar ou sair no meio do período, os meses em que ele não existia entrariam com zero. A mediana iria a zero e todos os meses normais dele seriam marcados como atípicos. Hoje os 122 alimentadores aparecem nos 48 meses, então o resultado é o mesmo. O limite protege as próximas cargas (apontado na review do PR #23).

> **Por que uma regra e não a data fixa:** `WHERE ano_mes = '2025-07'` resolveria hoje, mas o case prevê cargas mensais. A regra marca sozinha o próximo evento parecido. O flag **não remove nada**: a Gold decide se calcula DEC/FEC com ou sem esses meses (a regulação da ANEEL também expurga dias críticos dos indicadores).

### 2.6. Colunas de apoio e duplicatas
* **`sigla_municipio`:** extraída do código do alimentador (`ALM-REC-008` → `REC`). São 14 siglas, coerentes 100% com o município do cadastro (auditoria, seção 6).
* **`ano_mes`:** mês de abertura em `yyyy-MM`, para agregações mensais.
* **Duplicatas exatas:** removidas depois da padronização. A Bronze atual não tem nenhuma, mas a regra protege as próximas cargas. O mesmo id com conteúdo diferente bloqueia a carga.

---

## 3. Validações (gate de qualidade)

Antes de gravar, o notebook confere 12 regras críticas numa única passada pelos dados. Qualquer violação **interrompe a carga antes do `overwrite`** (a Silver anterior continua intacta), e o notebook mostra até 20 linhas que violam a regra.

| Regra | Por que existe | Hoje |
| :--- | :--- | :---: |
| `id_ocorrencia` repetido após remover duplicatas exatas | Garante a chave da tabela | 0 |
| `id_ocorrencia`/`id_uc` fora do padrão `OC…`/`UC…` + dígitos | Ids malformados quebram cruzamentos | 0 |
| `alimentador` fora do padrão `ALM-AAA-999` | DEC/FEC são calculados por alimentador | 0 |
| `tipo` fora do domínio (5 valores) | Categoria nova precisa de decisão | 0 |
| `causa` fora do domínio (7 valores) | Idem | 0 |
| `data_abertura` vazia ou não convertida | Formato novo ou data impossível | 0 |
| `data_encerramento` vazia ou não convertida | Idem | 0 |
| Encerramento anterior à abertura | Datas trocadas geram duração negativa | 0 |
| Abertura no futuro | Erro de digitação de ano | 0 |
| `duracao_min` vazia ou não convertida | Formato novo (ex.: `"75 minutos"`) | 0 |
| `duracao_min` ≠ encerramento − abertura | As duas fontes de duração precisam concordar | 0 |
| `duracao_efetiva_min` fora de [0, `duracao_min`] | Sanidade do cálculo de sobreposição | 0 |

O notebook também imprime os totais de sobreposição (331 ocorrências e 43.561 min em dobro) e a lista de meses atípicos, com a contagem e a mediana de cada um.

---

## 4. Dicionário de dados: `venergy.silver.ocorrencias_rede`

| Coluna | Tipo | Nulo? | Descrição | Exemplo |
| :--- | :--- | :---: | :--- | :--- |
| `id_ocorrencia` | STRING | não | Identificador da ocorrência (chave). Cada ocorrência é uma UC interrompida | `OC00000010` |
| `id_uc` | STRING | não | UC interrompida | `UC107256` |
| `alimentador` | STRING | não | Alimentador de média tensão | `ALM-JAB-007` |
| `sigla_municipio` | STRING | não | Sigla do município, extraída do alimentador | `JAB` |
| `tipo` | STRING | não | `FALTA DE ENERGIA`, `FIO PARTIDO`, `OSCILACAO`, `SOBRECARGA` ou `DANO EM EQUIPAMENTO` | `FALTA DE ENERGIA` |
| `causa` | STRING | não | 6 causas ou `NAO INFORMADA` | `CLIMATICA` |
| `data_abertura` | TIMESTAMP_NTZ | não | Início da interrupção (hora local) | 2022-07-01 16:33:00 |
| `data_encerramento` | TIMESTAMP_NTZ | não | Fim da interrupção (hora local) | 2022-07-01 20:10:00 |
| `ano_mes` | STRING | não | Mês de abertura (`yyyy-MM`) | `2022-07` |
| `duracao_min` | INT | não | Duração registrada (= encerramento − abertura) | 217 |
| `duracao_efetiva_min` | INT | não | Minutos não cobertos por ocorrência anterior da mesma UC. **Use `SUM` desta coluna para o tempo sem energia** | 217 |
| `flag_sobreposicao` | BOOLEAN | não | `true` se a UC já estava sem energia quando a ocorrência começou. **Para contar interrupções, use as linhas com `false`** | false |
| `flag_mes_atipico_alimentador` | BOOLEAN | não | `true` se o mês do alimentador passou de 5× a mediana mensal dele | false |
| `source_file` | STRING | não | Arquivo de origem na landing | `ocorrencias_rede.csv` |
| `ingestion_datetime` | TIMESTAMP | não | Momento da carga na Bronze | — |
| `silver_datetime` | TIMESTAMP | não | Momento da carga na Silver | — |

As descrições também estão gravadas como comentários das colunas no Unity Catalog.

---

## 5. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| `TIMESTAMP_NTZ` | `TIMESTAMP` com fuso | Horário local sem fuso na origem; evita deslocamento de horas entre sessões e exportações |
| `NAO INFORMADA` explícita | `null` | Agrupamentos legíveis e SQL sem armadilhas de nulo; separada de `NAO IDENTIFICADA` |
| Sobreposição por **maior encerramento acumulado** | Comparar com a ocorrência anterior imediata | A comparação simples perde 2 casos e deixa minutos em dobro (revisão do PR #9) |
| `duracao_efetiva_min` por linha | Tabela separada de intervalos unidos | Mantém um grão só, e `SUM`/`COUNT_IF` resolvem DEC e FEC direto |
| Flag de mês atípico por **regra** (5× a mediana do período do alimentador) | Data fixa `2025-07` no código | Funciona nas próximas cargas mensais, inclusive com alimentadores novos ou desativados; nada é removido |
| Validação **antes** do `overwrite` | Validar depois de gravar | Uma carga reprovada nunca substitui a Silver boa |
| Silver sem dependência do cadastro | Cruzar com `unidades_consumidoras` aqui | A Bronze do cadastro ainda está em revisão (PR #13). Os cruzamentos estão listados na seção 9 |

---

## 6. Como executar no Databricks

### 6.1. Pré-requisito
```sql
SELECT COUNT(*) FROM venergy.bronze.ocorrencias_rede;  -- esperado: 180000
```
Se a tabela não existir, rode antes `data-engineering/landing_to_bronze/landing-to-bronze-ocorrencias-rede.ipynb`.

### 6.2. Rodar o notebook
1. **Workspace → (sua pasta) → ⋮ → Import → File** e escolha `bronze-to-silver-ocorrencias-rede.ipynb` (ou abra pelo *Git folder*).
2. **Connect → Serverless**.
3. **Run all**. O schema `venergy.silver` é criado se ainda não existir.

### 6.3. O que conferir
* **Tabela de validação:** 12 regras com `violacoes = 0` e `status = OK`.
* **Resumo:** `Bronze: 180000 linhas | Silver: 180000 linhas | duplicatas removidas: 0`.
* **Totais:** `Sobrepostas: 331 | minutos somados: 21392087 | minutos efetivos: 21348526 | em dobro: 43561` e `Ocorrências em mês atípico: 12836`.
* **Meses atípicos:** os 3 alimentadores de 2025-07, com contagem e mediana.
* **Confirmação final:** `OK: 180000 ocorrências carregadas em venergy.silver.ocorrencias_rede`.
* **Evidências:**
  * causa Bronze → Silver;
  * duração com e sem sufixo;
  * minutos somados × efetivos;
  * prévia do DEC/FEC por alimentador com e sem os meses atípicos, em que o `ALM-REC-008` cai de 35.646 h para 2.112 h sem o evento.

### 6.4. Se a validação falhar
A mensagem lista cada regra crítica violada e a quantidade de linhas, e logo acima aparecem até 20 exemplos. A Silver anterior **não** foi alterada.

| Regra que falhou | Causa provável | O que fazer |
| :--- | :--- | :--- |
| `data_* não convertida` | Formato de data/hora novo | Ajustar `FORMATO_DATA_HORA` (ou tratar mais de um formato, como em medidores) |
| `duracao_min não convertida` | Unidade nova (ex.: `"75 minutos"`, `"1h15"`) | Ajustar a expressão regular da duração |
| `duracao_min ≠ encerramento − abertura` | As fontes de duração divergem | Investigar a origem antes de escolher qual vale |
| `causa`/`tipo` fora do domínio | Categoria nova | Confirmar com o negócio e incluir em `CAUSAS_VALIDAS`/`TIPOS_VALIDOS` |
| `id_ocorrencia repetido` | Mesma ocorrência com dados diferentes | Decidir com o negócio qual versão vale |

### 6.5. No Workflow (Job)
```text
landing_to_bronze_ocorrencias_rede ──► bronze_to_silver_ocorrencias_rede ──► (Gold de DEC/FEC)
```
No Databricks: **Jobs & Pipelines → Create → Job**. Adicione uma tarefa *Notebook* por notebook e marque **Depends on**. O notebook não tem parâmetros.

---

## 7. Como usar na Gold (DEC e FEC)

Pela definição do case, cada linha é uma UC interrompida. Para um alimentador num período:
* **DEC** (horas por UC) = `SUM(duracao_efetiva_min) / 60` ÷ número de UCs do alimentador;
* **FEC** (interrupções por UC) = `COUNT_IF(NOT flag_sobreposicao)` ÷ número de UCs do alimentador.

O número de UCs por alimentador vem do cadastro (Silver de `unidades_consumidoras`).

```sql
-- Numeradores de DEC/FEC por alimentador e mês, com e sem os meses atípicos
SELECT alimentador, ano_mes,
       SUM(duracao_efetiva_min) / 60.0                       AS horas_sem_energia,
       COUNT_IF(NOT flag_sobreposicao)                       AS interrupcoes,
       BOOL_OR(flag_mes_atipico_alimentador)                 AS mes_atipico
FROM venergy.silver.ocorrencias_rede
GROUP BY alimentador, ano_mes;
```

Prévia com a base atual (soma dos 48 meses):

| Alimentador | Horas sem energia | Interrupções | Horas sem meses atípicos | Interrupções sem meses atípicos |
| :--- | :---: | :---: | :---: | :---: |
| `ALM-REC-008` | 35.645,9 | 8.063 | 2.111,5 | 1.324 |
| `ALM-SAO-004` | 18.361,7 | 4.602 | 2.088,7 | 1.313 |
| `ALM-JAB-004` | 14.826,2 | 3.868 | 2.267,4 | 1.315 |
| `ALM-REC-014` | 2.644,6 | 1.456 | 2.644,6 | 1.456 |
| `ALM-CAM-003` | 2.628,9 | 1.473 | 2.628,9 | 1.473 |

Sem os meses atípicos, o ranking de "piores alimentadores" muda completamente. Por isso a escolha entre com e sem evento precisa ser explícita na Gold e no portal.

---

## 8. Testes realizados

O notebook foi executado sem modificações num Spark 4.0.1 + Delta 4.0.0 local (ANSI ligado), em cadeia com o notebook da Bronze. O resultado foi comparado com um cálculo independente feito em Python puro sobre o CSV:
* contagens, distribuições de `tipo` e `causa`, as somas de duração (21.392.087 e 21.348.526), as 331 sobreposições (268 em 2025-07), as 179.669 interrupções distintas, os meses atípicos (os 3 de 2025-07, com 12.836 ocorrências) e os exemplos (`"217 min"` → 217; `OC00122507` → 80 min efetivos) bateram 100%;
* os horários não mudam quando o fuso da sessão muda;
* as variações `" n/a "` e `"55 MIN"` são aceitas;
* a reexecução produz o mesmo resultado e só uma versão Delta nova;
* **5 defeitos injetados na Bronze** foram barrados pela regra certa, com a Silver intacta:
  * duração `"75 minutos"`;
  * encerramento antes da abertura;
  * causa nova `RAIO`;
  * mesmo id com conteúdo diferente;
  * data impossível `2022-13-01`.
* **Alimentador novo ou desativado:** simulando o `ALM-CAM-003` só a partir de 2026-01 e o `ALM-REC-014` só até 2022-12, só os 3 meses de 2025-07 continuam marcados. Sem o limite de período, 6 meses normais de cada um seriam marcados.

**Databricks (Serverless):** o notebook também foi executado no Unity Catalog (`venergy.silver`), e a tabela de validação, os totais e as evidências deram os mesmos números do teste local.

---

## 9. Pendências e pontos que dependem de outras tabelas

* **Cadastro (`unidades_consumidoras`, PR #13):** quando a Silver do cadastro existir:
  * conferir que todo `id_uc` existe e que o `alimentador` da ocorrência é o mesmo da UC (hoje 100%, segundo a auditoria);
  * marcar as **595 ocorrências abertas antes da `data_ligacao`** da UC (auditoria, seção 4.3);
  * usar o número de UCs por alimentador como denominador do DEC/FEC.
* **Meses 2025-11 e 2026-02:** o excesso difuso (≈ 3.885 ocorrências) continua registrado na auditoria como ponto a investigar. A regra de mês atípico corretamente **não** o marca, porque nenhum alimentador passa de 2,3× a mediana.
