# Relatório de Auditoria e Qualidade de Dados (`leituras_*.csv`)

**Escopo da Análise:** Auditoria estrutural, tipológica, semântica e de regras de negócio da base de leituras de medidores, feita sobre o bruto (todas as colunas lidas como texto, sem nenhuma conversão).
**Volume Total:** 2.182.468 registros distribuídos em 5 arquivos CSV particionados por ano.
**Período Coberto nos Dados:** `mes_referencia` de 2022-07 a 2026-06.
**Destino na Bronze:** `venergy.bronze.leituras` (conteúdo preservado, mais `source_file` e `ingestion_datetime`).

---

## 1. Sumário Executivo de Anomalias

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção (%) | Criticidade |
| :--- | :--- | :---: | :---: | :---: |
| **`consumo_kwh`** | Consumo negativo no mês da troca de medidor (leitura anterior do medidor antigo menos leitura atual do medidor novo) | 6.327 | 0,29% | **Crítica** |
| **`data_leitura`** | Mistura de 4 formatos, incluindo padrão americano `MM-DD-AAAA` com hífen | 261.935 (87.144 com hífen) | 12,0% (4,0%) | **Crítica** |
| **Chave / registros** | Duplicatas exatas (mesma linha repetida, incluindo `id_leitura`) | 21.523 | 0,99% | **Alta** |
| **`id_leitura` / `id_medidor`** | Leituras clonadas `LTX…` com medidor inexistente (`MD9…`) copiando uma leitura legítima | 8.609 | 0,39% | **Alta** |
| **`leitura_anterior`** | 4 representações de ausência: vazio, `N/A`, `NULL` e sentinela `-1` | 32.735 | 1,50% | **Alta** |
| **`consumo_kwh`** | Consumo negativo sem leitura anterior (causa não verificável na própria linha) | 115 | 0,01% | **Alta** |
| **`consumo_kwh`** | Sinal invertido (consumo = −(atual − anterior)) | 1.349 | 0,06% | **Alta** |
| **`consumo_kwh`** | Consumo negativo com módulo diferente de `atual − anterior` em ±1 kWh | 359 | 0,02% | **Média** |
| **`consumo_kwh`** | Formato numérico inconsistente: valores negativos com sufixo decimal (`-297.0`) | 1.739 | 0,08% | **Média** |
| **`consumo_kwh`** | Diferença de exatamente 1 kWh em relação a `leitura_atual − leitura_anterior` | 526.697 | 24,1% | **Baixa / Aceitável** |
| **Tipagem Geral** | Datas e números chegam como texto e só podem ser tipados após o saneamento acima | 2.182.468 | 100,0% | **Alta** |

**Atributos íntegros:** `mes_referencia` (100% `AAAA-MM`, sempre coerente com o ano do arquivo), `tipo_leitura` (apenas `REAL` e `ESTIMADA`, sem variação de caixa), `id_uc` (45.000 UCs, todas existentes no cadastro), nenhuma data vazia, nenhum consumo zero, nenhum espaço em branco nas extremidades de qualquer coluna e nenhum `id_leitura` repetido com conteúdo diferente.

---

## 2. Diagnóstico Estrutural

### 2.1. Arquivos e Partições
Os 5 arquivos têm o mesmo cabeçalho de 9 colunas, separador vírgula, codificação ASCII/UTF-8 e nenhum campo entre aspas. Todos os registros de cada arquivo pertencem ao ano do nome do arquivo (`mes_referencia` coerente em 100% das linhas), então não há vazamento entre partições.

| Arquivo | Linhas | Período |
| :--- | :---: | :---: |
| `leituras_2022.csv` | 271.744 | 2022-07 a 2022-12 |
| `leituras_2023.csv` | 544.546 | 2023-01 a 2023-12 |
| `leituras_2024.csv` | 545.652 | 2024-01 a 2024-12 |
| `leituras_2025.csv` | 546.908 | 2025-01 a 2025-12 |
| `leituras_2026.csv` | 273.618 | 2026-01 a 2026-06 |
| **Total** | **2.182.468** | 2022-07 a 2026-06 |

### 2.2. Chave `id_leitura` e Duplicatas Exatas
* **IDs distintos:** 2.160.945 para 2.182.468 linhas.
* **Duplicatas exatas:** 21.523 linhas são cópias idênticas (todas as 9 colunas) de outra linha. Cada grupo tem exatamente 2 cópias e as duas estão sempre no mesmo arquivo (ex.: `LT000000177`, UC `UC100003`, 2025-04; `LT000000389`, UC `UC100008`, 2022-12).
* Não existe `id_leitura` repetido com conteúdo diferente: toda repetição de ID é uma duplicata exata.

### 2.3. Leituras Clonadas (`LTX…`)
Há dois padrões de ID na base:

| Padrão `id_leitura` | Padrão `id_medidor` | Linhas | Medidor existe em `medidores`? |
| :--- | :--- | :---: | :---: |
| `LT` + 9 dígitos | `MD` + 6 dígitos (`MD5…`) | 2.173.859 | Sim (100%) |
| `LTX` + 7 dígitos | `MD` + 7 dígitos (`MD9…`) | 8.609 | **Não (0%)** |

As **8.609** leituras `LTX` têm, **todas**, uma gêmea legítima `LT` com a mesma UC, o mesmo `mes_referencia`, a mesma data, o mesmo tipo e os mesmos valores (`leitura_anterior`, `leitura_atual`, `consumo_kwh`). Só mudam o `id_leitura` e o `id_medidor`, que aponta para um medidor inexistente:

| Clone | Medidor do clone | Original | Medidor do original | Mês | Anterior → Atual | Consumo |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `LTX0000000` | `MD9434132` | `LT001861529` | `MD5…` | 2025-09 | 85341 → 85445 | 104 |
| `LTX0000001` | `MD9887759` | `LT000312669` | `MD5…` | 2024-08 | 35665 → 35733 | 68 |
| `LTX0000002` | `MD9935731` | `LT000888377` | `MD5…` | 2023-06 | 11764 → 11841 | 77 |

Nenhuma leitura `LT` tem medidor inexistente, e nenhuma leitura usa um medidor cadastrado em outra UC.

> **Invariante confirmada:** depois de remover as 21.523 duplicatas exatas e os 8.609 clones `LTX`, restam **2.152.336** leituras, exatamente **uma por par (`id_uc`, `mes_referencia`)**. Esse par pode ser usado como chave natural na Silver.

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Atributo `data_leitura` (Crítico)
Todas as datas estão preenchidas, mas coexistem **4 formatos**:

| Formato | Padrão | Quantidade | Exemplos (`id_leitura` : valor, mês de referência) |
| :--- | :--- | :---: | :--- |
| `AAAA-MM-DD` | ISO 8601 | 1.920.533 | `LT000000000` : `"2022-07-25"` (2022-07) |
| `DD.MM.AAAA` | Europeu/BR (pontos) | 87.618 | `LT000000024` : `"19.07.2024"` (2024-07) |
| `DD/MM/AAAA` | Brasileiro (barras) | 87.173 | `LT000000002` : `"10/09/2022"` (2022-09) |
| **`MM-DD-AAAA`** | **Americano (hífens)** | **87.144** | `LT000000023` : `"06-25-2024"` (2024-06) |

**Prova do formato de cada separador** (contagem de campos com valor maior que 12, que só pode ser dia):

| Separador | Linhas | 1º campo > 12 | 2º campo > 12 | Conclusão |
| :---: | :---: | :---: | :---: | :--- |
| hífen (`-`) | 87.144 | **0** | 49.781 | 1º campo é sempre mês → `MM-DD-AAAA` |
| barra (`/`) | 87.173 | 49.854 | **0** | 2º campo é sempre mês → `DD/MM/AAAA` |
| ponto (`.`) | 87.618 | 50.025 | **0** | 2º campo é sempre mês → `DD.MM.AAAA` |

Com essa interpretação, **100% das datas convertem** e o mês de **todas** as 2.182.468 datas coincide com `mes_referencia`.

> **Alerta de Inversão de Data (`MM-DD-AAAA`):** se um conversor assumir o formato brasileiro `DD-MM-AAAA` para as datas com hífen, **49.781** registros falham (ex.: `"06-25-2024"` em `LT000000023`, `"04-13-2025"` em `LT000000081`) e **34.194** são corrompidos **silenciosamente** para outro mês, como `"07-05-2022"` (`LT000000096`, referência 2022-07), que viraria 7 de maio, e `"05-08-2025"` (`LT000000130`, referência 2025-05), que viraria 5 de agosto. As outras 3.169 datas com hífen têm dia igual ao mês e não mudam.

### 3.2. Atributo `leitura_anterior`
A ausência da leitura anterior aparece de **4 formas diferentes**:

| Representação | Quantidade | Exemplo (`id_leitura` : anterior → atual, consumo) |
| :--- | :---: | :--- |
| `N/A` | 8.269 | `LT000000123` : `N/A` → 88508, 181 |
| vazio (`''`) | 8.218 | `LT000000067` : `''` → 34350, 1168 |
| `NULL` (texto) | 8.180 | `LT000000227` : `NULL` → 23311, 88 |
| `-1` (sentinela numérica) | 8.068 | `LT000000077` : `-1` → 42372, 953 |
| **Total** | **32.735** | |

* Na Bronze, o leitor CSV do Spark converte o vazio em `null`. `N/A` e `NULL` chegam como texto e `-1` chega como um número válido, então **`try_cast` sozinho não basta**: o `-1` passaria como leitura real e geraria `atual − (−1) = atual + 1` como consumo.
* Mesmo sem a leitura anterior, `consumo_kwh` está preenchido em todas as 32.735 linhas (32.620 positivas e 115 negativas). O consumo do mês **não se perde**, só a conferência `atual − anterior` fica impossível.
* Não há outros valores não numéricos nem negativos além do `-1`, e não há casas decimais em `leitura_anterior` nem em `leitura_atual`.

### 3.3. Atributo `consumo_kwh`
1. **Consumo negativo:** 8.150 linhas (0,37%), classificadas pela regra da célula 9 do notebook:

   | Causa provável | Linhas | Exemplo (`id_leitura` : anterior → atual, consumo) |
   | :--- | :---: | :--- |
   | Troca de medidor (anterior > atual) | 6.327 | `LT000000759` : 79980 → 80, `-79900` |
   | Sinal invertido (consumo = −(atual − anterior)) | 1.349 | `LT000001341` : 23205 → 23501, `-296.0` |
   | Outro: sinal invertido com diferença de ±1 kWh | 359 | `LT000000016` : 12670 → 12968, `-297.0` |
   | Sem leitura anterior | 115 | `LT000035655` : `N/A` → 82, `-43086` |

   As 115 linhas "sem leitura anterior" se dividem em **84 trocas de medidor** cuja leitura anterior está ausente (a UC tem medidor retirado no mesmo mês) e **31** com o mesmo padrão `-N.0` do item 2. Como a leitura anterior está ausente, a causa não pode ser confirmada pela própria linha, então essas 115 linhas não entram na correção de sinal (ver plano de saneamento).

2. **Formato numérico inconsistente:** 1.739 valores trazem sufixo decimal (`-297.0`, `-148.0`). Correspondem exatamente às 1.349 linhas de sinal invertido, às 359 da categoria "outro" e a 31 das 115 "sem leitura anterior". Nenhum valor positivo nem de troca tem decimal. O padrão indica que esses registros passaram por uma conversão diferente na origem. A parte decimal é sempre `.0`, então a conversão para inteiro não perde informação.

3. **Diferença em relação a `leitura_atual − leitura_anterior`** (linhas com leitura anterior numérica e não negativa):
   * **Exata:** 1.616.562 positivas + 4.766 trocas.
   * **Diferença de exatamente 1 kWh:** 526.697 linhas (525.136 positivas + 1.561 trocas), distribuídas de forma proporcional entre `REAL` (429.657) e `ESTIMADA` (95.479).
   * **Diferença maior que 1 kWh:** nenhuma.

   A diferença de ±1 kWh é compatível com arredondamento de leituras fracionárias e é considerada aceitável.

4. **Sem consumo zero.** O consumo positivo tem mediana de 169 kWh, p99 de 5.756 kWh e máximo de 64.009 kWh (UC industrial).

### 3.4. Atributo `id_medidor`
* 59.868 medidores distintos. Os 8.609 `MD9…` (um por clone `LTX`) não existem no cadastro.
* Todo `id_medidor` com prefixo `MD5…` existe em `medidores.csv` e pertence à mesma UC da leitura.

### 3.5. Atributo `tipo_leitura`
| Valor | Quantidade | Proporção |
| :--- | :---: | :---: |
| `REAL` | 1.786.380 | 81,85% |
| `ESTIMADA` | 396.088 | 18,15% |

Domínio limpo: só 2 valores, sempre em maiúsculas, sem espaços.

### 3.6. Atributo `mes_referencia`
100% no formato `AAAA-MM`, sempre coerente com o ano do arquivo e com o mês da `data_leitura` (depois do parsing correto). Período de 2022-07 a 2026-06.

---

## 4. Anomalias de Regra de Negócio

### 4.1. Troca de Medidor
No mês em que o medidor é trocado, a leitura é registrada no **medidor novo**, mas `leitura_anterior` continua sendo a última leitura do **medidor antigo**. Como o medidor novo começa do zero, `consumo_kwh = atual − anterior` fica muito negativo.

**Exemplo real (UC `UC100015`):** o medidor `MD500015` foi retirado em 2025-10-24 e o `MD545821` (instalado em 24/10/2025) assumiu.

| `id_leitura` | Medidor | Mês | Anterior | Atual | Consumo |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `LT000000757` | `MD500015` (retirado) | 2025-08 | 79883 | 79925 | 41 |
| `LT000000758` | `MD500015` (retirado) | 2025-09 | 79925 | 79980 | 55 |
| **`LT000000759`** | **`MD545821` (novo)** | **2025-10** | **79980** | **80** | **-79900** |
| `LT000000760` | `MD545821` (novo) | 2025-11 | 80 | 195 | 115 |
| `LT000000761` | `MD545821` (novo) | 2025-12 | 195 | 303 | 108 |

**Evidências:**
* As trocas se concentram entre **2025-09 e 2026-03** (de 875 a 924 por mês) e não ocorrem fora desse intervalo.
* As **6.367** retiradas de medidor registradas em `medidores.csv` (status `RETIRADO`, `data_retirada` de 2025-09-05 a 2026-03-25) têm, **todas**, uma leitura de consumo negativo na mesma UC e no mesmo mês, e todas as trocas caem no mês da retirada.
* Em 100% dos casos a leitura do mês da troca já está associada ao medidor novo (`ATIVO`).
* A fatura do mês da troca **não reflete** o valor negativo: o `valor_energia` desse mês fica entre 0,43× e 1,64× a mediana da própria UC (p1 a p99), sem nenhum caso acima de 3×.
* Das 6.327 linhas de troca, 78 são duplicatas exatas e 34 são clones `LTX`. Restam **6.215 trocas legítimas**, além das 84 com leitura anterior ausente.

> **Alerta: não usar `abs()` no consumo negativo.** O valor absoluto de uma troca é a leitura acumulada do medidor antigo (mediana de 55.831 kWh, máximo de 2.098.259 kWh), e não o consumo do mês. Nos últimos 12 meses (2025-07 a 2026-06), depois de remover duplicatas e clones, o volume correto é de **216,4 milhões de kWh** (positivos + negativos de leitura crescente com o sinal corrigido, sem os meses de troca). Com `abs()` ele passa a **599,3 milhões de kWh**, uma inflação de **≈ +177%** (o volume quase triplica).

### 4.2. Sinal Invertido
1.349 leituras têm `consumo_kwh` exatamente igual a `−(atual − anterior)`, com leituras do medidor crescentes. Só o sinal está errado, e o consumo correto é `-consumo_kwh`.

Outras 359 leituras têm o mesmo padrão, mas o módulo difere de `atual − anterior` em ±1 kWh. Como a regra de correção não confirma essas linhas, elas não recebem inversão automática.

---

## 5. Plano Recomendado de Saneamento (Silver)

Recomenda-se aplicar o seguinte pipeline sobre `venergy.bronze.leituras`, em ordem:

1. **Remover duplicatas exatas:** `DISTINCT` sobre as 9 colunas de negócio (−21.523 linhas).
2. **Descartar clones `LTX`:** manter apenas as leituras cujo `id_medidor` existe em `medidores` (−8.609 linhas). Depois dos passos 1 e 2, validar a unicidade do par (`id_uc`, `mes_referencia`): o esperado é 2.152.336 linhas.
3. **Normalizar ausências em `leitura_anterior`:** `''`, `N/A`, `NULL` e `-1` → `null`, **antes** de converter para número.
4. **Parsing determinístico de `data_leitura`** pela expressão regular de cada string:
   * `^\d{4}-\d{2}-\d{2}$` → `yyyy-MM-dd`
   * `^\d{2}/\d{2}/\d{4}$` → `dd/MM/yyyy`
   * `^\d{2}\.\d{2}\.\d{4}$` → `dd.MM.yyyy`
   * `^\d{2}-\d{2}-\d{4}$` → **obrigatoriamente** `MM-dd-yyyy`

   Como validação, o mês da data convertida deve coincidir com `mes_referencia` em 100% das linhas.
5. **Tipar `consumo_kwh` e corrigir o sinal:** converter `-N.0` para inteiro. **Só a categoria "sinal invertido"** (1.349 linhas: `leitura_anterior` numérica, `leitura_anterior ≤ leitura_atual` e `consumo_kwh = −(atual − anterior)`) recebe **inversão de sinal**.
   * As **115 leituras "sem leitura anterior"** com consumo negativo **não** têm o sinal invertido. Elas são marcadas com `flag_sem_leitura_anterior` e recebem o mesmo tratamento das trocas de medidor (passo 6).
   * As **359 da categoria "outro"** (módulo com ±1 kWh de diferença) também não são invertidas automaticamente. Ficam marcadas para decisão do time.
6. **Mês da troca de medidor:** não usar o valor registrado. Marcar com `flag_troca_medidor` (consumo negativo e `leitura_anterior > leitura_atual`) e, junto com as 115 do passo 5, **decidir com o time** entre:
   * estimar o kWh a partir do `valor_energia` da fatura do mês (que foi cobrada normalmente); ou
   * imputar pela média de consumo da própria UC.

   Em nenhum caso usar `abs()`.
7. **Manter a diferença de ±1 kWh** entre `consumo_kwh` e `atual − anterior`, documentada como arredondamento. `consumo_kwh` é a fonte de verdade do consumo.
8. **Tipagem final:** `leitura_anterior`, `leitura_atual` e `consumo_kwh` como inteiros, `data_leitura` como `DATE`, `mes_referencia` mantido como `AAAA-MM` (ou convertido para o primeiro dia do mês).

---

## 6. Pontos que Dependem de Outras Tabelas

* **`medidores`:** é a fonte para descartar os clones `LTX` (medidor inexistente) e para confirmar trocas (`status = RETIRADO` e `data_retirada`). Cuidados no cruzamento, a detalhar na auditoria dessa tabela:
  * 13.649 medidores `ATIVO` usam `9999-12-31` como sentinela em `data_retirada`, e os demais `ATIVO` deixam o campo vazio;
  * `data_instalacao` mistura formatos (ex.: `2011-12-20` e `12/01/2019`).
* **`faturas`:** não há coluna de kWh, só valores em R$. A tarifa implícita (`valor_energia / consumo_kwh`) é estável por classe (mediana de R$ 0,57/kWh para residencial, R$ 0,51/kWh para industrial e R$ 0,60/kWh para as demais), o que permite estimar o kWh dos meses de troca. Todas as leituras têm fatura correspondente, mas há 22 pares (UC, mês) com mais de uma fatura, que precisam ser tratados antes desse cruzamento.
* **`unidades_consumidoras`:** as 45.000 UCs das leituras existem no cadastro. Para qualquer análise por classe, a coluna `classe` tem variação de caixa e acento (`Residencial`, `RESIDENCIAL`, `residencial`, `Poder Publico`, `Poder Público`) e uma linha com o valor literal `classe` (cabeçalho repetido).
* **Consumos extremos:** nenhuma leitura positiva passa de 10× a mediana da própria UC, e nenhuma tem tarifa implícita abaixo de 10% da mediana da classe. O maior consumo positivo é de 64.009 kWh, numa UC industrial, e o maior em UC residencial é de 1.601 kWh.
