# Relatório de Auditoria e Qualidade de Dados (`inspecoes.xlsx`)

**Escopo da Análise:** Auditoria estrutural, tipológica, semântica e estatística da base de inspeções de consumo de energia.  
**Volume Total:** $1.389$ registros distribuídos em $3$ abas (`ago-set`, `dez`, `out-nov`).  
**Período Coberto nos Dados:** $01/08/2025$ a $31/12/2025$.

---

## 1. Sumário Executivo de Anomalias

Abaixo estão consolidadas todas as inconformidades identificadas na base bruta, classificadas pelo seu grau de criticidade para processos de *Business Intelligence* (BI), *Analytics* e carga em banco de dados.

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção ($\%$) | Criticidade |
| :--- | :--- | :---: | :---: | :---: |
| **`data`** | Mistura de $4$ formatos distintos na aba `dez`, incluindo padrão norte-americano (`MM-DD-YYYY`) | $133$ | $9,6\%$ | **Crítica** |
| **Tipagem Geral** | Colunas de data (`data`) e numéricas (`kwh_recuperado`) armazenadas integralmente como texto (`string`) | $1.389$ | $100,0\%$ | **Alta** |
| **Particionamento (`aba`)** | Registros de agosto a novembro alocados incorretamente na aba `dez` | $107$ | $7,7\%$ | **Alta** |
| **`kwh_recuperado`** | Inconsistência de separador decimal: uso de vírgula (`,`) em vez de ponto (`.`) | $125$ | $9,0\%$ | **Alta** |
| **`resultado`** | Quebra de padronização semântica e de caixa (*case sensitivity*): $8$ variações para apenas $2$ status | $164$ | $11,8\%$ | **Média** |
| **`inspetor`** | Espaços em branco (*leading/trailing whitespace*) gerando $107$ categorias falsas para $40$ inspetores reais | $83$ | $6,0\%$ | **Média** |
| **`tipo_irregularidade`** | Dupla representação de ausência de valor: células nulas (`NaN`) misturadas com hífen (`"-"`) | $77$ | $5,5\%$ | **Média** |
| **`kwh_recuperado`** | *Outliers* extremos de recuperação (acima de $Q_3 + 3 \times \text{IQR}$, atingindo até $15.609,40\text{ kWh}$) | $58$ | $4,2\%$ | **Baixa / Alerta** |
| **Ordenação / `id_inspecao`** | Abas fora de ordem cronológica e IDs sequenciais sem correlação com a data de realização | $1.389$ | $100,0\%$ | **Baixa** |

---

## 2. Diagnóstico Estrutural e de Particionamento

### 2.1. Ordem Física das Abas
As planilhas dentro do arquivo `inspecoes.xlsx` estão ordenadas na sequência `['ago-set', 'dez', 'out-nov']`, posicionando o mês de dezembro antes do bimestre outubro-novembro.

### 2.2. Vazamento Temporal entre Abas (*Data Leakage* de Partição)
Enquanto as abas `ago-set` ($511$ linhas) e `out-nov` ($495$ linhas) respeitam estritamente seus recortes de competência, a aba `dez` ($383$ linhas) contém apenas **$276$ registros reais de dezembro**. Os demais **$107$ registros ($27,9\%$ da aba)** pertencem a meses anteriores:

* **Agosto/2025:** $24$ registros (ex.: `IN0000010` com data `14.08.2025`, linha $2$ da aba `dez`).
* **Setembro/2025:** $23$ registros (ex.: `IN0000076` com data `09-09-2025`, linha $15$ da aba `dez`).
* **Outubro/2025:** $34$ registros (ex.: `IN0000040` com data `02/10/2025`, linha $10$ da aba `dez`).
* **Novembro/2025:** $26$ registros (ex.: `IN0000038` com data `21/11/2025`, linha $9$ da aba `dez`).

**Impacto Analítico:** Qualquer consolidação mensal que utilize o nome da aba como referência de competência subestimará o volume de agosto a novembro em $107$ inspeções e inflará artificialmente o mês de dezembro em $+38,8\%$.

### 2.3. Desacoplamento entre `id_inspecao` e Cronologia
A chave primária `id_inspecao` é única, contínua e íntegra (de `IN0000000` a `IN0001388`, sem duplicatas ou lacunas). Entretanto, a numeração sequencial não reflete a ordem temporal dos eventos:
* `IN0000002` $\rightarrow$ `2025-09-17`
* `IN0000004` $\rightarrow$ `2025-11-06`
* `IN0000005` $\rightarrow$ `2025-08-10`

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Atributo `data` (Crítico)
Todos os $1.389$ registros estão armazenados como texto (`string`) em vez de tipo nativo `Date`. Nas abas `ago-set` e `out-nov`, $100\%$ das datas seguem o formato ISO (`YYYY-MM-DD`). Na aba `dez`, coexistem **$4$ padrões de formatação**:

| Formato Encontrado (Aba `dez`) | Padrão | Quantidade | Distribuição por Mês Real | Exemplos (`id_inspecao` : valor) |
| :--- | :--- | :---: | :--- | :--- |
| `YYYY-MM-DD` | ISO 8601 | $250$ | Dez ($250$) | `IN0000015` : `"2025-12-31"` |
| `DD/MM/YYYY` | Brasileiro (Barras) | $43$ | Ago ($5$), Set ($10$), Out ($9$), Nov ($8$), Dez ($11$) | `IN0000038` : `"21/11/2025"` |
| `DD.MM.YYYY` | Europeu/BR (Pontos) | $44$ | Ago ($8$), Set ($6$), Out ($10$), Nov ($9$), Dez ($11$) | `IN0000010` : `"14.08.2025"` |
| **`MM-DD-YYYY`** | **Americano (Hífens)** | **$46$** | **Ago ($11$), Set ($7$), Out ($15$), Nov ($9$), Dez ($4$)** | `IN0000085` : `"08-26-2025"` |

> **Alerta de Inversão de Data (`MM-DD-YYYY`):** Todas as $46$ datas separadas por hífen com o ano no final seguem o padrão norte-americano (o primeiro grupo numérico varia exclusivamente entre `08` e `12`, e o segundo entre `01` e `31`). Se um conversor assumir o formato brasileiro `DD-MM-YYYY`, datas ambíguas como `"09-01-2025"` (`IN0000025`), `"08-03-2025"` (`IN0000058`) e `"11-04-2025"` (`IN0000263`) serão corrompidas silenciosamente para janeiro, março e abril, enquanto registros como `"08-26-2025"` (`IN0000085`) resultarão em falha de execução ou valor nulo (`NaT`).

---

### 3.2. Atributo `inspetor`
O quadro real de fiscais é composto por exatamente **$40$ códigos padronizados** (`INSP-001` a `INSP-040`). Contudo, uma consulta de valores distintos (`DISTINCT`) retorna **$107$ categorias** devido à inserção de espaços em branco (*whitespace*) em **$83$ registros ($6,0\%$ da base)**:

* **Espaços à esquerda (*leading*):** $31$ ocorrências (ex.: `"  INSP-001"` em `IN0000042`; `" INSP-003"` em `IN0000012`).
* **Espaços à direita (*trailing*):** $19$ ocorrências (ex.: `"INSP-028  "` em `IN0000025`; `"INSP-020 "` em `IN0001311`).
* **Espaços em ambos os lados:** $33$ ocorrências (ex.: `"  INSP-003  "` em `IN0001173`; `" INSP-035 "` em `IN0000016`).
* **Incidência por aba:** $40$ em `ago-set`, $26$ em `out-nov` e $17$ em `dez`.

---

### 3.3. Atributo `resultado`
Embora represente uma variável binária de desfecho da vistoria, o campo apresenta **$8$ variações textuais** decorrentes da falta de validação de entrada (*dropdown*) e mistura de capitalização:

| Domínio Padronizado | Valor Bruto na Planilha | `ago-set` | `out-nov` | `dez` | Total |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **IRREGULARIDADE CONFIRMADA** ($871$) | `IRREGULARIDADE CONFIRMADA` *(padrão)* | $279$ | $285$ | $213$ | **$777$** |
| | `CONFIRMADA` *(termo truncado)* | $11$ | $13$ | $11$ | **$35$** |
| | `Irregularidade Confirmada` *(Title Case)* | $16$ | $9$ | $7$ | **$32$** |
| | `irregularidade confirmada` *(minúsculas)* | $12$ | $8$ | $7$ | **$27$** |
| **SEM IRREGULARIDADE** ($518$) | `SEM IRREGULARIDADE` *(padrão)* | $175$ | $154$ | $119$ | **$448$** |
| | `sem irregularidade` *(minúsculas)* | $10$ | $10$ | $13$ | **$33$** |
| | `NADA CONSTA` *(sinônimo fora do padrão)* | $6$ | $10$ | $6$ | **$22$** |
| | `Sem Irregularidade` *(Title Case)* | $2$ | $6$ | $7$ | **$15$** |

---

### 3.4. Atributo `tipo_irregularidade`
A integridade referencial cruzada com `resultado` está preservada ($100\%$ das $871$ irregularidades confirmadas possuem um tipo válido atribuído, e $100\%$ das $518$ inspeções normais não possuem fraude associada). As anomalias restringem-se à representação de valores ausentes e grafia:

1. **Dupla representação de Nulos:** Entre os $518$ casos sem irregularidade, **$441$ células estão vazias (`NULL`/`NaN`)** e **$77$ contêm o texto `"-"`** ($31$ em `ago-set`, $30$ em `out-nov` e $16$ em `dez`, como em `IN0000014` e `IN0000008`). Em ferramentas de BI, o caractere `"-"` é contabilizado como uma categoria válida de fraude se não for convertido para `NULL`.
2. **Padronização Ortográfica:** A categoria `"LIGACAO CLANDESTINA"` ($164$ registros) está registrada sem sinais diacríticos (cedilha e til), divergindo da norma culta em relatórios de apresentação.

---

### 3.5. Atributo `kwh_recuperado`
A integridade lógica com o desfecho da inspeção é consistente (todos os $518$ casos sem irregularidade possuem valor igual a zero, e todos os $871$ casos confirmados possuem recuperação estritamente positiva, com mínimo de $203,30\text{ kWh}$). Os problemas são de tipagem e formatação numérica:

1. **Tipagem como Texto (`string`):** Todos os $1.389$ números estão gravados como texto, impedindo agregações diretas (`SUM`, `AVG`) em planilhas ou consultas SQL sem conversão explícita.
2. **Conflito de Separador Decimal:**
   * **$1.264$ registros ($91,0\%$)** utilizam ponto decimal (`.`), como `"838.10"` (`IN0000000`).
   * **$125$ registros ($9,0\%$)** utilizam vírgula decimal (`,`), sendo $45$ em `ago-set`, $44$ em `out-nov` e $36$ em `dez` (ex.: `"0,00"` em `IN0000006`, `"1313,70"` em `IN0000009` e `"10105,70"` em `IN0001376`).

---

## 4. Anomalias Estatísticas e Regras de Negócio

### 4.1. *Outliers* Extremos em `kwh_recuperado`
Considerando apenas as $871$ inspeções com irregularidade confirmada, as métricas de posição e dispersão são:
* **Média:** $1.691,29\text{ kWh}$ | **Desvio-Padrão:** $1.860,68\text{ kWh}$
* **Primeiro Quartil ($Q_1$):** $762,15\text{ kWh}$
* **Mediana ($Q_2$):** $1.072,70\text{ kWh}$
* **Terceiro Quartil ($Q_3$):** $1.735,90\text{ kWh}$
* **Amplitude Interquartil ($\text{IQR} = Q_3 - Q_1$):** $973,75\text{ kWh}$

Aplicando os critérios clássicos de detecção de valores atípicos:
* **Limite de *Outlier* Moderado ($Q_3 + 1,5 \times \text{IQR} = 3.196,53\text{ kWh}$):** $100$ registros ($11,5\%$ das fraudes) excedem esse patamar.
* **Limite de *Outlier* Extremo ($Q_3 + 3,0 \times \text{IQR} = 4.657,15\text{ kWh}$):** $58$ registros ($6,7\%$ das fraudes) excedem esse limite.
* **Acima de $10.000\text{ kWh}$:** $11$ registros apresentam volumes compatíveis com unidades comerciais/industriais de médio porte ou acúmulos plurianuais severos, destacando-se:
  1. `IN0000605` (`2025-11-29`, `INSP-028`, `DESVIO ANTES DO MEDIDOR`): **$15.609,40\text{ kWh}$**
  2. `IN0001223` (`2025-12-10`, `INSP-022`, `LIGACAO CLANDESTINA`): **$15.312,00\text{ kWh}$**
  3. `IN0000523` (`2025-09-10`, `INSP-037`, `MEDIDOR ADULTERADO`): **$14.996,60\text{ kWh}$**

### 4.2. Execução de Inspeções em Domingos e Feriados Nacionais
A distribuição temporal das vistorias é uniforme ao longo dos $7$ dias da semana, sem redução nos finais de semana ($197$ inspeções aos sábados e $179$ aos domingos). Além disso, há volume normal de trabalho registrado em feriados nacionais:
* **$07/09/2025$ (Independência do Brasil - Domingo):** $8$ inspeções.
* **$12/10/2025$ (Nossa Sra. Aparecida - Domingo):** $8$ inspeções.
* **$02/11/2025$ (Finados - Domingo):** $12$ inspeções.
* **$15/11/2025$ (Proclamação da República - Sábado):** $10$ inspeções.
* **$20/11/2025$ (Dia da Consciência Negra - Quinta-feira):** $12$ inspeções.
* **$25/12/2025$ (Natal - Quinta-feira):** $9$ inspeções (ex.: `IN0000783`, `IN0000836`).

> **Nota de Negócio:** Caso as equipes de campo não atuem em regime de plantão ininterrupto em feriados como o dia de Natal, esse comportamento aponta para falha no carimbo de data do sistema coletor ou natureza sintética da base.

---

## 5. Plano Recomendado de Saneamento (Regras de ETL)

Para higienizar a base antes do consumo analítico, recomenda-se aplicar o seguinte pipeline de transformação em ordem sequencial:

1. **Unificação das Abas:** Concatenar `ago-set`, `out-nov` e `dez` em uma tabela única, descartando o nome da aba de origem como variável temporal e reordenando os registros por data ou `id_inspecao`.
2. **Saneamento de `inspetor`:** Aplicar função de remoção de espaços nas extremidades (`TRIM` / `.str.strip()`), reduzindo as $107$ variações para os $40$ códigos canônicos.
3. **Normalização de `resultado`:** Aplicar conversão para maiúsculas (`UPPER`) seguida de remoção de espaços (`TRIM`) e mapeamento de domínio (`"CONFIRMADA"` $\rightarrow$ `"IRREGULARIDADE CONFIRMADA"` e `"NADA CONSTA"` $\rightarrow$ `"SEM IRREGULARIDADE"`).
4. **Padronização de Nulos em `tipo_irregularidade`:** Substituir todas as ocorrências de `"-"` por `NULL` (`NaN`) ou por uma etiqueta explícita de negócio (ex.: `"NÃO APLICÁVEL"`).
5. **Conversão de `kwh_recuperado`:** Substituir o caractere `","` por `"."` em toda a coluna e converter o tipo de dado para ponto flutuante (`FLOAT` / `DECIMAL(10,2)`).
6. **Parsing Determinístico de `data`:** Avaliar a expressão regular de cada string antes da conversão para `DATE`:
   * Se casar com `^\d{4}-\d{2}-\d{2}$` $\rightarrow$ converter via máscara `%Y-%m-%d`.
   * Se casar com `^\d{2}/\d{2}/\d{4}$` $\rightarrow$ converter via máscara `%d/%m/%Y`.
   * Se casar com `^\d{2}\.\d{2}\.\d{4}$` $\rightarrow$ converter via máscara `%d.%m.%Y`.
   * Se casar com `^\d{2}-\d{2}-\d{4}$` $\rightarrow$ converter **obrigatoriamente** via máscara americana `%m-%d-%Y`.