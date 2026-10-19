# Relatório de Auditoria e Qualidade de Dados (`ocorrencias_rede.csv`)

**Escopo da Análise:** Auditoria estrutural, tipológica, semântica e de regras de negócio da base de interrupções de fornecimento, feita sobre o bruto (todas as colunas lidas como texto, sem nenhuma conversão).
**Volume Total:** 180.000 registros em um único arquivo CSV. Cada registro corresponde a **uma unidade consumidora interrompida** (definição do case).
**Período Coberto nos Dados:** `data_abertura` de 2022-07-01 a 2026-06-30.
**Destino na Bronze:** `venergy.bronze.ocorrencias_rede` (conteúdo preservado, mais `source_file` e `ingestion_datetime`).

---

## 1. Sumário Executivo de Anomalias

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção (%) | Criticidade |
| :--- | :--- | :---: | :---: | :---: |
| **Volume mensal** | Pico de 2025-07: 17.844 ocorrências (5,3× a média), 97% climáticas e concentradas em 3 alimentadores | 17.844 | 9,91% | **Crítica** |
| **`duracao_min`** | Formato numérico inconsistente: sufixo `" min"` em parte dos valores | 16.200 | 9,00% | **Alta** |
| **`causa`** | 4 representações de ausência: `-`, vazio, `N/A` e `NULL` | 5.400 | 3,00% | **Alta** |
| **Intervalos por UC** | Interrupções sobrepostas na mesma UC (contam tempo em dobro no DEC se somadas direto) | 329 | 0,18% | **Alta** |
| **Datas x cadastro** | Ocorrência aberta antes da `data_ligacao` da UC | 595 (219 UCs) | 0,33% | **Média** |
| **`duracao_min`** | Interrupções de 24 h ou mais (máximo de 48 h) | 275 | 0,15% | **Média** |
| **Volume mensal** | Meses 2025-11 e 2026-02 com ~1.950 ocorrências acima da média, sem concentração | 10.619 | 5,90% | **Baixa / A investigar** |
| **Tipagem Geral** | Datas e duração chegam como texto e só podem ser tipadas após o saneamento acima | 180.000 | 100,0% | **Alta** |

**Atributos íntegros:** `id_ocorrencia` (180.000 IDs únicos, padrão `OC` + 8 dígitos, sem duplicatas exatas nem registros iguais com ID diferente), `alimentador` (122 códigos no padrão `ALM-<município>-<nnn>`), `tipo` (5 valores, sem variação de caixa), `data_abertura` e `data_encerramento` (100% no formato `AAAA-MM-DD HH:MM:SS`, sem vazios e nenhum encerramento anterior à abertura) e `duracao_min`, que, sem o sufixo, é **igual** a `data_encerramento − data_abertura` em 100% das linhas.

---

## 2. Diagnóstico Estrutural

### 2.1. Arquivo
Um arquivo com cabeçalho de 8 colunas, separador vírgula, codificação ASCII/UTF-8 sem BOM, quebra de linha LF e nenhum campo entre aspas. Todas as 180.000 linhas têm exatamente 8 campos.

### 2.2. Chave `id_ocorrencia`
* 180.000 IDs distintos para 180.000 linhas.
* Nenhuma duplicata exata e nenhum par de registros idêntico exceto pelo ID. Também não há duas ocorrências com a mesma UC, o mesmo alimentador e a mesma abertura.

### 2.3. Cobertura
* **Período:** 48 meses completos, de 2022-07 a 2026-06.
* **Alimentadores:** 122, com 14 prefixos de município (`REC`, `JAB`, `PAU`, `OLI`, `CAB`, `SAO`, `CAM`, `IGA`, `ABR`, `IPO`, `MOR`, `ILH`, `ITA`, `ARA`), o que bate com os 14 municípios do case.
* **UCs afetadas:** 41.512 das 45.000 UCs com medidor.

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Atributo `duracao_min`
1. **Sufixo `" min"`:** 16.200 valores vêm como texto com unidade (ex.: `"217 min"` em `OC00000010`, `"28 min"` em `OC00000017`). Os demais 163.800 são inteiros puros. Não há outro formato: depois de remover o sufixo, 100% convertem para inteiro.
2. **Coerência com as datas:** sem o sufixo, `duracao_min` é **exatamente** igual a `data_encerramento − data_abertura`, em minutos, em todas as 180.000 linhas. As duas fontes são intercambiáveis.
3. **Distribuição:** mínimo de 5 min, mediana de 73 min, p99 de 749 min e máximo de 2.880 min (48 h, `OC00014815`, `ALM-REC-047`, causa `VEGETACAO`, 2022-11-30). Não há interrupções abaixo de 3 minutos.
4. **Interrupções longas:** 275 ocorrências duram 24 h ou mais, e 226 delas estão no evento de 2025-07 (ver 4.1).

> Um `try_cast(duracao_min AS INT)` direto transforma os 16.200 valores com sufixo em `null`, o que **subestima o DEC** em 9% dos registros sem gerar nenhum erro.

### 3.2. Atributo `causa`
| Valor | Quantidade | Observação |
| :--- | :---: | :--- |
| `CLIMATICA` | 43.692 | 17.352 delas em 2025-07 |
| `NAO IDENTIFICADA` | 26.328 | Causa investigada e não encontrada (valor de negócio) |
| `SOBRECARGA` | 26.328 | |
| `VEGETACAO` | 26.160 | |
| `TERCEIROS` | 26.147 | |
| `FALHA DE EQUIPAMENTO` | 25.945 | |
| `-` | 1.363 | Ausência (ex.: `OC00000040`) |
| vazio (`''`) | 1.356 | Ausência (ex.: `OC00000102`) |
| `N/A` | 1.341 | Ausência (ex.: `OC00000056`) |
| `NULL` (texto) | 1.340 | Ausência (ex.: `OC00000033`) |
| **Ausências (total)** | **5.400** | 3,00% |

* Na Bronze, o vazio vira `null`, enquanto `-`, `N/A` e `NULL` chegam como texto. Um `WHERE causa IS NULL` encontra só 1.356 das 5.400 ausências.
* **Não confundir** a ausência de causa com `NAO IDENTIFICADA`. A primeira é falta de registro, a segunda é um resultado de investigação.

### 3.3. Atributo `tipo`
| Valor | Quantidade | Proporção |
| :--- | :---: | :---: |
| `FALTA DE ENERGIA` | 121.593 | 67,55% |
| `DANO EM EQUIPAMENTO` | 14.868 | 8,26% |
| `OSCILACAO` | 14.562 | 8,09% |
| `SOBRECARGA` | 14.547 | 8,08% |
| `FIO PARTIDO` | 14.430 | 8,02% |

Domínio limpo: 5 valores, sempre em maiúsculas, sem acento e sem espaços. `SOBRECARGA` existe tanto como `tipo` quanto como `causa`, o que é esperado (são dimensões diferentes).

### 3.4. Atributos `data_abertura` e `data_encerramento`
100% no formato `AAAA-MM-DD HH:MM:SS` (segundos sempre `00`), sem vazios, sem mistura de formatos e sem encerramento anterior à abertura. Podem ser convertidos direto para `TIMESTAMP`.

---

## 4. Anomalias de Regra de Negócio

### 4.1. Evento Climático de 2025-07
O volume mensal é muito estável: **média de 3.367 ocorrências/mês** (de 3.227 a 3.451) em 45 dos 48 meses. Julho de 2025 foge completamente do padrão:

| Indicador | Meses normais | 2025-07 |
| :--- | :---: | :---: |
| Ocorrências | ~3.367 | **17.844** |
| Causa `CLIMATICA` | 16,2% | **97,2%** |
| Interrupções sobrepostas na mesma UC | ~1 por mês | **266** |
| Interrupções ≥ 24 h | ~1 por mês | **226** |

**Concentração:** 12.836 das 17.844 ocorrências (72%) estão em 3 alimentadores, `ALM-REC-008` (6.887), `ALM-SAO-004` (3.351) e `ALM-JAB-004` (2.598), 12.471 delas com causa `CLIMATICA`. O evento cobre o mês inteiro (todos os 31 dias, de 541 a 628 ocorrências por dia), e não um único dia de tempestade.

**Consequência para o ranking de alimentadores:** `ALM-REC-008` é o alimentador com mais ocorrências no total (8.211, quase o dobro do 2º colocado), mas **6.887 delas são de 2025-07**. Fora desse mês ele tem 1.324, na mesma faixa de `ALM-SAO-004` (1.313). Um ranking de "piores alimentadores" sem tratar o evento vai apontar `ALM-REC-008` por causa de um único mês.

Não há sinal de erro de carga (IDs únicos, datas e durações coerentes, nenhuma duplicata). O evento é tratado aqui como **dado real e atípico**, e a decisão de como ele entra no DEC/FEC é do time (ver plano de saneamento).

### 4.2. Interrupções Sobrepostas na Mesma UC
329 ocorrências começam antes do fim da ocorrência anterior **da mesma UC**. Em vários casos uma está inteiramente contida na outra:

| UC | Ocorrência 1 | Ocorrência 2 |
| :--- | :--- | :--- |
| `UC141273` | `OC00164034`: 2026-02-17 11:38 → 14:37 | `OC00162909`: 2026-02-17 13:11 → 13:45 |
| `UC110456` | `OC00166500`: 2026-03-27 22:28 → 2026-03-28 15:22 | `OC00167456`: 2026-03-28 10:36 → 11:05 |

Somando `duracao_min` direto, esses intervalos contam o mesmo tempo sem energia duas vezes: são **43.144 minutos** sobrepostos (0,2% do total de 21,4 milhões de minutos). 266 dos 329 casos estão em 2025-07.

### 4.3. Ocorrência Anterior à Ligação da UC
595 ocorrências (219 UCs) foram abertas **antes** da `data_ligacao` da UC no cadastro (ex.: `OC00000117` em 2022-07-10 para `UC122093`, ligada em 2024-07-06). Uma UC não pode ser interrompida antes de existir: ou a data de ligação do cadastro está errada, ou a ocorrência foi associada à UC errada. Como o alimentador da ocorrência bate com o do cadastro em 100% dos casos, a primeira hipótese é mais provável.

### 4.4. Meses 2025-11 e 2026-02
Os dois meses têm ~5.300 ocorrências, cerca de 1.950 acima da média. Diferente de 2025-07, o excesso está **espalhado** por todos os alimentadores e causas, sem concentração (o maior acréscimo em um único alimentador é de ~40). Fica registrado como ponto a investigar, sem tratamento proposto.

---

## 5. Plano Recomendado de Saneamento (Silver)

Recomenda-se aplicar o seguinte pipeline sobre `venergy.bronze.ocorrencias_rede`, em ordem:

1. **Tipar as datas:** `data_abertura` e `data_encerramento` → `TIMESTAMP` (formato único, sem tratamento prévio).
2. **Tipar `duracao_min`:** remover o sufixo `" min"` (`regexp_replace(duracao_min, ' min$', '')`) **antes** de converter para inteiro. Validar que nenhum valor fica nulo e que a duração é igual a `data_encerramento − data_abertura` em 100% das linhas.
3. **Normalizar ausências em `causa`:** `''`, `-`, `N/A` e `NULL` → `null` (ou para a categoria explícita `NAO INFORMADA`, a decidir com o time). Manter `NAO IDENTIFICADA` como valor próprio.
4. **Marcar o evento de 2025-07:** `flag_evento_climatico_2025_07` para as ocorrências do mês nos 3 alimentadores afetados, permitindo calcular DEC/FEC com e sem o evento.
5. **Unir intervalos sobrepostos por UC** (ou marcá-los com `flag_sobreposicao`) antes de somar tempo de interrupção, para não contar o mesmo período duas vezes no DEC.
6. **Marcar ocorrências anteriores à ligação** (`flag_antes_da_ligacao`) depois do cruzamento com o cadastro saneado, sem descartá-las até a auditoria do cadastro confirmar a causa.
7. **Tipagem final:** `duracao_min` como inteiro; `alimentador`, `tipo` e `causa` como texto normalizado; colunas derivadas `ano_mes` e `municipio` (pelo prefixo do alimentador ou pelo cadastro) para facilitar a Gold.

---

## 6. Pontos que Dependem de Outras Tabelas

* **`unidades_consumidoras`:**
  * Todos os `id_uc` existem no cadastro, e o `alimentador` da ocorrência é **igual** ao alimentador da UC no cadastro em 100% das linhas. O prefixo do alimentador também bate com o município da UC em 100% dos casos.
  * Nenhuma ocorrência envolve as 200 UCs `TESTE…` do cadastro.
  * O cálculo de DEC/FEC precisa do **total de UCs por alimentador** (denominador), que vem do cadastro. Esse total depende de remover antes as UCs de teste, as linhas duplicadas e o cabeçalho repetido do cadastro.
  * As 595 ocorrências anteriores à ligação (4.3) dependem da auditoria de `data_ligacao`.
* **DEC/FEC (Gold):** decisões a registrar no dicionário de dados:
  * se o evento de 2025-07 entra no indicador ou é expurgado (a regulação da ANEEL prevê expurgos para situações de emergência, mas o case avisa que os valores aqui são simplificados e servem para comparar alimentadores e períodos entre si);
  * se as interrupções sobrepostas são unidas por UC;
  * que não há interrupções abaixo de 3 minutos nesta base, então nenhum corte por duração mínima altera os indicadores.
