# Relatório de Auditoria e Qualidade de Dados (`medidores.csv`)

**Escopo da Análise:** Auditoria estrutural, tipológica, semântica e de regras de negócio do parque de medidores, feita sobre o bruto (todas as colunas lidas como texto, sem nenhuma conversão).
**Volume Total:** 51.812 registros em um único arquivo CSV.
**Período Coberto nos Dados:** `data_instalacao` de 1997-11-10 a 2026-03-25; `data_retirada` de 2025-09-05 a 2026-03-25.
**Destino na Bronze:** `` `v-energy`.bronze.tb_medidores `` (conteúdo preservado, mais `source_file` e `ingestion_datetime`).

---

## 1. Sumário Executivo de Anomalias

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção (%) | Criticidade |
| :--- | :--- | :---: | :---: | :---: |
| **`data_instalacao`** | Mistura de 4 formatos, incluindo padrão americano `MM-DD-AAAA` com hífen | 3.728 (1.263 com hífen) | 7,20% (2,44%) | **Crítica** |
| **Chave / registros** | Duplicatas exatas (mesma linha repetida, incluindo `id_medidor`) | 513 | 0,99% | **Alta** |
| **Regra 1 medidor ativo por UC** | UCs com 2 medidores `ATIVO`, todas causadas pelas duplicatas exatas | 445 UCs | 0,99% das UCs | **Alta** |
| **`tipo`** | 10 grafias para 3 categorias (caixa, acento, hífen e sufixo `meter`) | 5.354 | 10,33% | **Alta** |
| **`data_retirada`** | Sentinela `9999-12-31` para medidor não retirado, convivendo com vazio | 13.649 | 26,34% | **Média** |
| **`modelo`** | Espaços nas extremidades (81 variações brutas para 9 modelos) | 3.109 | 6,00% | **Média** |
| **`data_ultima_manutencao`** | Coluna 100% vazia | 51.812 | 100,0% | **Baixa** |
| **Tipagem Geral** | Datas chegam como texto e só podem ser tipadas após o saneamento acima | 51.812 | 100,0% | **Alta** |

**Atributos íntegros:** `status` (apenas `ATIVO` e `RETIRADO`, sem variação de caixa), `id_medidor` e `id_uc` (padrão `MD`/`UC` + 6 dígitos em 100% das linhas, sem espaços), coerência total entre `status` e `data_retirada` (nenhum `RETIRADO` sem data e nenhum `ATIVO` com data real), nenhuma retirada anterior à instalação e nenhum `id_medidor` repetido com conteúdo diferente.

---

## 2. Diagnóstico Estrutural

### 2.1. Arquivo
Um arquivo com cabeçalho de 8 colunas, separador vírgula, codificação UTF-8 sem BOM, quebra de linha LF e nenhum campo entre aspas. Todas as 51.812 linhas têm exatamente 8 campos.

### 2.2. Chave `id_medidor` e Duplicatas Exatas
* **IDs distintos:** 51.299 para 51.812 linhas.
* **Duplicatas exatas:** 513 linhas são cópias idênticas (todas as 8 colunas) de outra linha. Cada grupo tem exatamente 2 cópias (ex.: `MD500006` / `UC100006`, `MD500081` / `UC100081`, `MD500196` / `UC100196`).
* Não existe `id_medidor` repetido com conteúdo diferente: toda repetição de ID é uma duplicata exata.
* Das 6.367 linhas `RETIRADO`, 68 são duplicatas. Os medidores retirados únicos são **6.299**.

> **Invariante confirmada:** depois de remover as 513 duplicatas exatas, restam **51.299** medidores e **cada uma das 45.000 UCs tem exatamente 1 medidor `ATIVO`**. As 445 UCs que aparecem com 2 medidores ativos no bruto são todas efeito das duplicatas. O par (`id_uc`, `status = ATIVO`) pode ser usado como chave na Silver.

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Atributo `data_instalacao` (Crítico)
Todas as datas estão preenchidas, mas coexistem **4 formatos**:

| Formato | Padrão | Quantidade | Exemplo (`id_medidor` : valor) |
| :--- | :--- | :---: | :--- |
| `AAAA-MM-DD` | ISO 8601 | 48.084 | `MD500000` : `"2011-12-20"` |
| **`MM-DD-AAAA`** | **Americano (hífens)** | **1.263** | `MD500083` : `"03-16-2020"` |
| `DD/MM/AAAA` | Brasileiro (barras) | 1.249 | `MD500015` : `"12/01/2019"` |
| `DD.MM.AAAA` | Europeu/BR (pontos) | 1.216 | `MD500038` : `"20.04.2007"` |

**Prova do formato de cada separador** (contagem de campos com valor maior que 12, que só pode ser dia):

| Separador | Linhas | 1º campo > 12 | 2º campo > 12 | Conclusão |
| :---: | :---: | :---: | :---: | :--- |
| hífen (`-`) | 1.263 | **0** | 761 | 1º campo é sempre mês → `MM-DD-AAAA` |
| barra (`/`) | 1.249 | 734 | **0** | 2º campo é sempre mês → `DD/MM/AAAA` |
| ponto (`.`) | 1.216 | 730 | **0** | 2º campo é sempre mês → `DD.MM.AAAA` |

É o mesmo padrão encontrado em `data_leitura` (ver `auditoria_leituras.md`), o que indica um mesmo sistema de origem gerando as datas com hífen.

> **Alerta de Inversão de Data (`MM-DD-AAAA`):** se um conversor assumir o formato brasileiro `DD-MM-AAAA` para as datas com hífen, **761** registros falham (ex.: `"03-16-2020"` em `MD500083`, `"09-27-2013"` em `MD500315`) e **469** são corrompidos **silenciosamente** para outra data, como `"04-07-1999"` (`MD500007`), que viraria 4 de julho em vez de 7 de abril, e `"12-10-2020"` (`MD500556`), que viraria 12 de outubro em vez de 10 de dezembro. As outras 33 datas com hífen têm dia igual ao mês e não mudam.

Com a interpretação correta, **100% das datas convertem**, nenhuma instalação é posterior a 2026-03-25 e nenhum medidor é instalado antes da `data_ligacao` da sua UC.

### 3.2. Atributo `data_retirada`
A ausência de retirada aparece de **2 formas**:

| `status` | `data_retirada` | Quantidade | Exemplo |
| :--- | :--- | :---: | :--- |
| `ATIVO` | vazio (`''`) | 31.796 | `MD500000` |
| `ATIVO` | sentinela `9999-12-31` | 13.649 | `MD500005` |
| `RETIRADO` | data real (sempre `AAAA-MM-DD`) | 6.367 | `MD500011` : `"2025-12-17"` |

* Na Bronze, o vazio vira `null` e a sentinela chega como texto. Converter `9999-12-31` direto para `DATE` geraria uma data válida no ano 9999, que quebraria qualquer cálculo de vida útil ou de "medidor ativo em uma data".
* As datas reais vão de **2025-09-05 a 2026-03-25** (ver 4.1).

### 3.3. Atributo `tipo`
Três tecnologias escritas de **10 formas**:

| Categoria | Grafias (quantidade · exemplo) | Total |
| :--- | :--- | :---: |
| `ELETRONICO` | `ELETRONICO` 23.919 · `Eletronico` 1.369 (`MD500026`) · `eletrônico` 1.320 (`MD500010`) | 26.608 |
| `ELETROMECANICO` | `ELETROMECANICO` 14.844 · `ELETRO-MECANICO` 606 (`MD500009`) · `Eletromecanico` 601 (`MD500003`) · `eletromecânico` 596 (`MD500203`) | 16.647 |
| `SMART` | `SMART` 7.695 · `smart meter` 443 (`MD500726`) · `Smart` 419 (`MD500312`) | 8.557 |

Não há valor que não se encaixe em uma das 3 categorias. Um `GROUP BY tipo` sem normalização mostra 10 tecnologias em vez de 3.

### 3.4. Atributo `modelo`
3.109 valores têm espaços antes e/ou depois (ex.: `"  EL-3000 "` em `MD500005`, `" EL-2200 "` em `MD500069`). São **81 variações brutas** para **9 modelos reais**: `CG-500`, `EL-2200`, `EL-3000`, `EM-1200`, `EM-1400`, `IQ-900`, `NX-700`, `SM-4100`, `SM-4500`.

### 3.5. Atributo `data_ultima_manutencao`
Vazia em **100%** das linhas. A coluna não tem informação nesta extração.

### 3.6. Atributo `status`
| Valor | Quantidade | Proporção |
| :--- | :---: | :---: |
| `ATIVO` | 45.445 | 87,71% |
| `RETIRADO` | 6.367 | 12,29% |

Domínio limpo: só 2 valores, sempre em maiúsculas, sem espaços.

---

## 4. Anomalias de Regra de Negócio

### 4.1. Campanha de Troca de Medidores (set/2025 a mar/2026)
As retiradas não estão espalhadas pelo histórico: **todas** as 6.299 retiradas únicas acontecem em um intervalo de 7 meses, num ritmo constante.

| Mês da retirada | Medidores retirados |
| :---: | :---: |
| 2025-09 | 917 |
| 2025-10 | 890 |
| 2025-11 | 905 |
| 2025-12 | 890 |
| 2026-01 | 901 |
| 2026-02 | 873 |
| 2026-03 | 923 |

**Evidências:**
* Em **100%** das retiradas, o medidor substituto da mesma UC foi instalado **no mesmo dia** da retirada. Não há UC sem medidor em nenhum momento.
* Toda troca resulta em medidor **`SMART`**: 5.661 eletromecânicos → smart, 601 eletrônicos → smart e 37 smart → smart.
* Nenhuma UC tem mais de uma troca (38.701 UCs com 1 medidor e 6.299 com 2).
* As trocas são majoritariamente residenciais (5.395 de 6.299, somando as variações de caixa de `classe` no cadastro deduplicado; ver seção 6).
* Cada troca coincide com a leitura de consumo negativo do mês da troca descrita em `auditoria_leituras.md` (seção 4.1).

Do ponto de vista de qualidade, a campanha é coerente (datas, status e leituras batem). Ela fica registrada aqui porque **muda o parque no meio do período de análise**: os últimos 12 meses do case (2025-07 a 2026-06) incluem 6.299 UCs que trocaram de tecnologia de medição.

---

## 5. Plano Recomendado de Saneamento (Silver)

Recomenda-se aplicar o seguinte pipeline sobre `` `v-energy`.bronze.tb_medidores ``, em ordem:

1. **Remover duplicatas exatas:** `DISTINCT` sobre as 8 colunas de negócio (−513 linhas → 51.299). Validar em seguida que cada `id_medidor` é único e que cada UC tem exatamente 1 medidor `ATIVO`.
2. **Normalizar `modelo`:** `trim`. Validar que restam 9 valores distintos.
3. **Normalizar `tipo`** para o domínio `ELETRONICO` / `ELETROMECANICO` / `SMART`: remover acentos, hífen e o sufixo `meter`, converter para maiúsculas. Validar que restam 3 valores e que nenhum fica sem categoria.
4. **Parsing determinístico de `data_instalacao`** pela expressão regular de cada string:
   * `^\d{4}-\d{2}-\d{2}$` → `yyyy-MM-dd`
   * `^\d{2}/\d{2}/\d{4}$` → `dd/MM/yyyy`
   * `^\d{2}\.\d{2}\.\d{4}$` → `dd.MM.yyyy`
   * `^\d{2}-\d{2}-\d{4}$` → **obrigatoriamente** `MM-dd-yyyy`

   Como validação, nenhuma data pode ficar nula e nenhuma instalação pode ser anterior à `data_ligacao` da UC.
5. **Normalizar `data_retirada`:** `''` e `9999-12-31` → `null`, **antes** de converter para `DATE`. Validar que `data_retirada IS NOT NULL` ⇔ `status = 'RETIRADO'`.
6. **`data_ultima_manutencao`:** manter como `DATE` nula ou remover da Silver, registrando o motivo no dicionário de dados.
7. **Tipagem final:** `data_instalacao` e `data_retirada` como `DATE`; demais colunas como texto normalizado.
8. **(Opcional) Flag de troca:** marcar as UCs com troca (`flag_troca_medidor`, `data_troca`, `tipo_anterior`), que serão úteis para cruzar com leituras e faturas.

---

## 6. Pontos que Dependem de Outras Tabelas

* **`leituras`:** é a principal consumidora desta tabela.
  * Todo `id_medidor` `MD5…` das leituras existe aqui e pertence à mesma UC da leitura. Nenhuma leitura cai fora da vida útil do medidor (antes da instalação ou depois da retirada).
  * As 8.609 leituras clonadas `LTX` apontam para **8.569** medidores `MD9…` distintos (40 deles aparecem em 2 clones), e **nenhum** existe aqui. Essa é a regra para descartar os clones.
  * Todos os 51.299 medidores únicos têm ao menos uma leitura.
  * A regra de troca da leitura (consumo negativo no mês da troca) deve usar `data_retirada` **depois** do passo 5, para não confundir com a sentinela.
* **`unidades_consumidoras`:**
  * **Os números desta seção e da 4.1 usam o cadastro tratado:** sem a linha com o cabeçalho repetido (`id_uc` = `"id_uc"`) e deduplicado por `id_uc`. O arquivo tem 46.461 linhas para 45.200 UCs (1.256 UCs repetidas, 1.260 linhas a mais). Entre as repetições, só `cpf_cnpj` muda (em 40 UCs), então `classe`, `alimentador` e `data_ligacao` não dependem de qual linha é mantida. Sem esse tratamento, a conta dá 201 UCs sem medidor (a linha de cabeçalho entra) e 5.543 trocas residenciais em vez de 5.395.
  * Todos os `id_uc` existem no cadastro.
  * **200 UCs do cadastro não têm medidor**: todas têm `id_uc` no formato `TESTE0000`…`TESTE0199`, o que indica registros de teste no cadastro. Tratar na auditoria do cadastro.
  * Em 44.910 das 45.000 UCs, o primeiro medidor foi instalado exatamente na `data_ligacao`. As **90** exceções têm `data_ligacao` implausível no cadastro (ex.: `UC100016` com `1903-01-01`, `UC100329` com `1921-01-01`), não erro em `medidores`.
  * Para análises por classe, a coluna `classe` do cadastro tem variação de caixa e acento.
* **`faturas` e diagnóstico de receita:** a campanha de troca (4.1) concentra 6.299 mudanças de tecnologia de medição nos últimos 12 meses do período. É um ponto a considerar quando o time comparar consumo e receita entre períodos.
