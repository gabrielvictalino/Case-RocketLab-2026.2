# Relatório de Auditoria e Qualidade de Dados (`faturas.csv`)

**Escopo da Análise:** Auditoria estrutural, semântica e estatística da base de faturas, com verificação de formatos, chaves, datas, valores, consistência interna e correspondência com o cadastro local de unidades consumidoras.  
**Volume Total:** 2.184.623 registros após o cabeçalho inicial, dos quais **2.184.621 são registros de negócio** e 2 são repetições internas do cabeçalho; 11 colunas de origem.  
**Período Coberto nos Dados:** Competências de **julho/2022 a junho/2026**, com 48 meses consecutivos.   

A análise percorreu o arquivo integralmente, sem amostragem. Para as estatísticas de negócio, foram excluídas apenas as duas linhas idênticas ao cabeçalho. As contagens temporais seguem as máscaras declaradas na seção 3.2. Nenhuma fonte, notebook ou tabela foi alterada. O confronto com `unidades_consumidoras.csv` utiliza somente `id_uc`; não constitui auditoria completa desse cadastro nem execução do pipeline no Databricks.

---

## 1. Sumário Executivo de Anomalias

As criticidades abaixo expressam o impacto potencial na conversão para a Silver e no consumo analítico: **Crítica** indica interpretação não determinística; **Alta**, risco relevante de perda ou associação incorreta; **Média**, validação ou padronização necessária. Alertas estatísticos e comportamentos de pagamento são separados de erros comprovados.

| Categoria / Atributo | Anomalia Identificada | Registros Afetados | Proporção (%) | Criticidade |
| :--- | :--- | ---: | ---: | :---: |
| **Estrutura** | Cabeçalho completo repetido dentro dos dados | 2 | 0,0001%¹ | **Alta** |
| **`data_emissao`** | Representações fora do padrão ISO, incluindo datas ambíguas | 183.361 | 8,39% | **Alta** |
| **`data_emissao`** | Duas interpretações de calendário distintas e válidas | 20.416 | 0,93% | **Crítica** |
| **`valor_total`** | Notação monetária brasileira misturada com ponto decimal | 196.622 | 9,00% | **Alta** |
| **`data_pagamento`** | Sentinela `9999-12-31` em faturas EM ABERTO | 61.333 | 2,81% | **Alta** |
| **`id_uc`** | UC sem correspondência no cadastro local disponível | 32.285 | 1,48% | **Alta** |
| **UC × competência** | 21 pares com duas faturas de IDs distintos; requer regra de negócio | 42 | 0,0019% | **Média** |
| **Emissão × competência** | Emissão fora do mês de referência em todas as interpretações válidas | 11.179 | 0,51% | **Média — validar regra** |
| **`valor_total`** | Valor acima de Q3 + 3 × IQR | 161.136 | 7,38% | **Alerta estatístico** |

¹ Somente a linha de cabeçalhos usa 2.184.623 como denominador. As demais usam **2.184.621 registros de negócio**. As categorias se sobrepõem: as contagens não devem ser somadas como quantidade de faturas distintas com problema. Os 42 registros dos pares repetidos também estão entre as faturas sem correspondência cadastral.

**Controles sem divergência:** nenhuma duplicata exata; nenhum `id_fatura` repetido; todos os registros de negócio têm 11 campos; todas as competências e vencimentos são válidos; os três campos monetários foram interpretados sem falhas, e **2.184.621 faturas conciliam exatamente energia + tributos = total**. Pagamentos vazios são compatíveis com o status EM ABERTO e não foram classificados isoladamente como defeito.

---

## 2. Diagnóstico Estrutural e de Particionamento

### 2.1. Organização Física e Contrato de Leitura

| Propriedade | Resultado Verificado |
| :--- | :--- |
| Fonte | `C:\Users\gabri\Case-RocketLab-2026.2\base_dados_1\faturas.csv` |
| Tamanho | 206.897.892 bytes |
| Codificação | UTF-8 sem BOM |
| Delimitador | Ponto e vírgula (`;`) |
| Cabeçalho | 11 nomes, na ordem original |
| Registros após o cabeçalho inicial | 2.184.623 |
| Registros de negócio | 2.184.621 |
| Registros com largura incompatível / vazios | 0 / 0 |
| Campos com espaços nas extremidades / caracteres NUL | 0 / 0 |
| Particionamento físico observado | Arquivo CSV único; sem abas ou partições físicas auditadas |

**Colunas:** `id_fatura`, `id_uc`, `mes_referencia`, `data_emissao`, `valor_energia`, `tributos`, `bandeira_tarifaria`, `valor_total`, `data_vencimento`, `data_pagamento` e `status`.

> **Contrato da Bronze:** As 11 colunas como STRING preservam a representação original do CSV. Isso não é, por si só, um defeito de tipagem. A carga integral mais recente deve continuar usando substituição completa, com um único `ingestion_datetime` UTC por execução e `source_file_path`. Os saneamentos abaixo pertencem à Silver; o volume bruto da Bronze continua incluindo os dois cabeçalhos internos.

### 2.2. Cabeçalhos Internos e Cobertura Temporal

Há duas repetições exatas do cabeçalho nos **registros lógicos 1.005.328 e 1.749.118**, contando o cabeçalho inicial como registro 1. A referência é ao registro interpretado pelo leitor CSV, não necessariamente à linha física em um editor. A opção de leitura `header=true` não deve ser tomada como garantia de remoção de cabeçalhos internos.

As 48 competências entre `2022-07` e `2026-06` estão presentes sem lacunas mensais. O volume mensal varia de **45.301 a 45.692 faturas**. Essa cobertura não comprova que cada UC deveria receber uma fatura em cada mês; faltam regras de vigência e elegibilidade para medir completude individual.

O arquivo apresenta **60.737 transições entre registros de negócio em que a competência diminui**. Portanto, a posição no arquivo não define o mês da fatura. Não foi constatado erro de particionamento: filtros e agrupamentos temporais devem usar a competência interpretada, e não a ordenação física ou o ID.

### 2.3. Identificadores, Granularidade e Duplicação

| Verificação | Resultado |
| :--- | ---: |
| `id_fatura` distintos | 2.184.621 |
| Grupos de `id_fatura` repetido ou conflitante | 0 |
| Grupos de duplicatas exatas nas 11 colunas | 0 |
| `id_uc` distintos nas faturas | 76.705 |
| Pares UC × competência com mais de uma fatura | 21 |
| Registros participantes desses pares | 42 |
| Maior multiplicidade por UC × competência | 2 |

`id_fatura` é uma chave candidata única nesta extração. Já `(id_uc, mes_referencia)` **não é chave única observada**. Os 21 pares têm valores totais diferentes e IDs distintos, todos do grupo FTX. Isso não autoriza escolher uma das faturas nem somá-las como faturamento definitivo sem esclarecer se representam reemissão, ajuste ou cobranças independentes.

---

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Atributos `id_fatura` e `id_uc`

Todos os IDs das faturas são não vazios e seguem `FT + dígitos` ou `FTX + dígitos`. Todos os `id_uc` das faturas seguem `UC + dígitos`.

| Grupo de IDs | Faturas | UCs Distintas | Correspondência no Cadastro Disponível |
| :--- | ---: | ---: | :--- |
| FT | 2.152.336 | 45.000 | Todas as 45.000 UCs encontradas |
| FTX | 32.285 | 31.705 | Nenhuma das 31.705 UCs encontrada |

**Cruzamento referencial:** 32.285 faturas, referentes a **31.705 UCs**, não encontram `id_uc` em `unidades_consumidoras.csv`. Elas somam **R$ 10.192.373,82**, equivalentes a 1,51% do valor total bruto, e abrangem competências de todo o período. O resultado foi igual por comparação literal e por comparação após TRIM/UPPER dos IDs cadastrais.

| Exemplo de Fatura | UC sem Correspondência | Competência | Registro Lógico |
| :--- | :--- | :--- | ---: |
| `FTX0000000` | `UC9969129` | 2026-01 | 2.152.340 |
| `FTX0000001` | `UC9156745` | 2023-06 | 2.152.341 |
| `FTX0000002` | `UC9707518` | 2024-04 | 2.152.342 |

O cadastro de apoio contém **46.460 registros após excluir 1 cabeçalho interno**, 45.200 IDs brutos distintos e 45.000 IDs distintos válidos após TRIM/UPPER. Há 200 registros com ID fora do padrão UC + dígitos e 1.260 ocorrências excedentes de IDs brutos repetidos. Por isso, o confronto usa um conjunto de chaves distintas, evitando multiplicar faturas em um JOIN.

> **Impacto:** Um INNER JOIN eliminaria 32.285 faturas; um JOIN direto contra cadastro com IDs repetidos pode multiplicar registros. A ausência de correspondência é comprovada **em relação ao arquivo local disponível**; não comprova que a UC inexista no sistema oficial. A presença do prefixo FTX identifica esse grupo nesta extração, mas não justifica uma regra permanente de exclusão por prefixo.

---

### 3.2. Atributos `mes_referencia` e `data_emissao`

Todas as competências são meses válidos em `YYYY-MM`. **Convenções da análise:** barras e pontos foram interpretados como dia/mês/ano; ano no início como ISO; hífen com ano no fim foi testado nas duas ordens, MM-DD e DD-MM. O uso de DMY para barras e pontos é uma hipótese explícita de leitura, não uma convenção formalmente confirmada pela origem. As contagens de ambiguidades, intervalos e cruzamentos abaixo valem segundo essas máscaras; uma confirmação de convenção diferente exige reprocessamento. A emissão apresenta as seguintes representações:

| Representação / Situação | Registros | Proporção | Exemplo Bruto |
| :--- | ---: | ---: | :--- |
| ISO `YYYY-MM-DD` | 2.001.260 | 91,61% | `2022-07-27` |
| `DD.MM.YYYY` | 61.252 | 2,80% | `12.05.2025` |
| `DD/MM/YYYY` | 61.291 | 2,81% | `14/04/2026` |
| Hífen, ano no fim: somente MM-DD válido | 38.615 | 1,77% | `07-19-2025` |
| Hífen, ano no fim: MM-DD e DD-MM coincidem | 1.787 | 0,08% | `08-08-2022` |
| Hífen, ano no fim: duas datas distintas válidas | 20.416 | 0,93% | `03-10-2023` |
| **Total** | **2.184.621** | **100,00%** | |

Segundo as máscaras adotadas, não há emissão vazia ou sem nenhuma interpretação válida. Entretanto, **20.416 datas permanecem ambíguas**: `03-10-2023`, em `FT000000056` (registro 58), pode significar 10 de março ou 3 de outubro. A existência de 38.615 datas inequivocamente americanas sustenta a hipótese de origem MM-DD, mas não prova a convenção de todos os registros com hífen.

**Emissão × competência:** 2.153.225 registros têm interpretação única segundo essas máscaras e emissão no mesmo mês da competência; 20.217 ambíguos possuem uma das interpretações nesse mês; 11.179 ficam fora do mês em todas as interpretações testadas. Ajustar a data para fazê-la caber na competência seria uma inferência, não uma correção comprovada.

Entre as **2.164.205 emissões com interpretação única segundo essas máscaras**, o intervalo é **03/07/2022 a 30/06/2026**. Esse intervalo não resolve as 20.416 datas ambíguas, que foram mantidas separadas.

---

### 3.3. Atributos `data_vencimento`, `data_pagamento` e `status`

Todos os vencimentos são datas válidas em ISO, entre **15/07/2022 e 12/07/2026**. O pagamento possui duas representações de ausência:

| Status | Situação do Pagamento | Registros | Proporção do Total |
| :--- | :--- | ---: | ---: |
| PAGA | Data ISO válida, entre 11/07/2022 e 06/08/2026 | 2.009.453 | 91,98% |
| EM ABERTO | Campo vazio | 113.835 | 5,21% |
| EM ABERTO | Sentinela `9999-12-31` | 61.333 | 2,81% |
| **Total** | | **2.184.621** | **100,00%** |

Há **175.168 faturas EM ABERTO** (8,02%), e todas têm pagamento vazio ou sentinela. Todas as PAGA possuem data real de pagamento; não há combinação de EM ABERTO com data real nem PAGA sem data real.

Embora `9999-12-31` seja uma data válida no calendário, neste contexto funciona como marcador de ausência e pode distorcer máximos, intervalos e cálculos de atraso. Recomenda-se convertê-la para NULL na Silver, preservando o valor bruto e um indicador do motivo. A convenção deve ser documentada com o responsável pela origem; não se trata de pagamento futuro comprovado.

---

### 3.4. Atributos `valor_energia`, `tributos` e `valor_total`

Os três campos são totalmente preenchidos e todos os valores são estritamente positivos. Energia e tributos usam ponto decimal e duas casas em todos os registros. O total mistura três representações:

| Representação em `valor_total` | Registros | Proporção | Exemplo Bruto |
| :--- | ---: | ---: | :--- |
| Ponto decimal, sem símbolo | 1.987.999 | 91,00% | `102.57` |
| R$ e vírgula decimal, sem milhar | 188.571 | 8,63% | `R$ 225,53` |
| R$, ponto de milhar e vírgula decimal | 8.051 | 0,37% | `R$ 1.056,83` |
| **Total** | **2.184.621** | **100,00%** | |

Os **196.622 totais em notação brasileira** exigem uma máscara própria. Substituir separadores indiscriminadamente, por exemplo remover todos os pontos de toda a coluna, alteraria valores como `102.57`. A auditoria aplicou gramáticas explícitas e conversão exata para centavos; uma segunda implementação com Decimal reconferiu cada valor e os totais, sem divergências.

**Conciliação por fatura:** 2.184.621 de 2.184.621 satisfazem `valor_energia + tributos = valor_total`, com diferença exatamente zero em centavos. Não foram encontrados valores não interpretáveis, zeros ou negativos. Isso comprova coerência aritmética interna, sem validar preços cobrados, alíquotas legais ou a legitimidade da cobrança.

---

### 3.5. Atributo `bandeira_tarifaria`

| Categoria Observada | Registros | Proporção |
| :--- | ---: | ---: |
| Verde | 1.546.130 | 70,77% |
| Amarela | 273.630 | 12,53% |
| Vermelha P1 | 228.042 | 10,44% |
| Vermelha P2 | 136.819 | 6,26% |
| **Total** | **2.184.621** | **100,00%** |

Não há vazios, espaços nas extremidades ou variações de caixa nessas categorias. São os quatro valores observados, sem validação contra calendário oficial de bandeiras ou contrato tarifário. O rótulo, isoladamente, não permite reconstruir a composição da cobrança.

---

## 4. Anomalias Estatísticas e Regras de Negócio

### 4.1. Distribuição Monetária e Valores Atípicos

Universo: **2.184.621 faturas**, incluindo as sem correspondência cadastral. Quartis calculados por interpolação linear na posição `p × (n − 1)`; desvio-padrão amostral (n − 1). Os valores abaixo estão em reais, arredondados apenas na apresentação.

| Métrica | Energia | Tributos | Total |
| :--- | ---: | ---: | ---: |
| Mínimo | R$ 4,78 | R$ 1,59 | R$ 6,37 |
| Primeiro quartil (Q1) | R$ 63,17 | R$ 21,06 | R$ 84,23 |
| Mediana (Q2) | R$ 97,06 | R$ 32,35 | R$ 129,41 |
| Terceiro quartil (Q3) | R$ 155,15 | R$ 51,72 | R$ 206,87 |
| Máximo | R$ 35.810,60 | R$ 11.936,87 | R$ 47.747,47 |
| Média | R$ 232,31 | R$ 77,44 | R$ 309,74 |
| Desvio-padrão amostral | R$ 856,48 | R$ 285,49 | R$ 1.141,98 |
| IQR = Q3 − Q1 | R$ 91,98 | R$ 30,66 | R$ 122,64 |

| Atributo | Limite Q3 + 1,5 × IQR | Acima do Limite | Limite Q3 + 3 × IQR | Acima do Limite |
| :--- | ---: | ---: | ---: | ---: |
| `valor_energia` | R$ 293,12 | 235.383 (10,77%) | R$ 431,09 | 161.136 (7,38%) |
| `tributos` | R$ 97,71 | 235.366 (10,77%) | R$ 143,70 | 161.128 (7,38%) |
| `valor_total` | R$ 390,83 | 235.383 (10,77%) | R$ 574,79 | 161.136 (7,38%) |

Os limites são superiores e usam comparação estrita (valor > limite), sem arredondamento antes da classificação. A contagem acima de 3 × IQR está contida na contagem acima de 1,5 × IQR. Esses alertas não equivalem a faturas inválidas.

| Fatura de Maior Valor | UC | Competência | Valor Total |
| :--- | :--- | :--- | ---: |
| `FT001837726` | `UC138427` | 2024-10 | R$ 47.747,47 |
| `FT001837729` | `UC138427` | 2025-01 | R$ 46.997,31 |
| `FT000609616` | `UC112744` | 2025-02 | R$ 44.441,36 |

O máximo de **R$ 47.747,47** concilia energia e tributos. A concentração de 7,38% acima do limite extremo recomenda segmentar a análise por perfil de UC e contrato antes de estabelecer regras automáticas. Não há evidência suficiente nesta fonte para atribuir esses valores a fraude, erro, porte comercial ou acúmulo de competências.

### 4.2. Prazos de Pagamento e Consistência Cronológica

| Verificação | Resultado | Interpretação |
| :--- | ---: | :--- |
| PAGA com pagamento após vencimento | 1.675.636 (83,39% das PAGA) | Comportamento observado; não é defeito de formato |
| EM ABERTO com vencimento anterior a 20/10/2026 | 175.168 (100% das EM ABERTO) | Comparação condicional à atualidade do status da extração |
| Pagamento anterior à emissão em todas as interpretações | 0 | Nenhuma contradição inequívoca encontrada |
| Emissão posterior ao vencimento em todas as interpretações | 0 | Nenhuma contradição inequívoca encontrada |
| Pagamento anterior à emissão em ao menos uma interpretação ambígua | 10.464 | Risco de interpretação; não é ocorrência confirmada |
| Emissão posterior ao vencimento em ao menos uma interpretação ambígua | 11.905 | Risco de interpretação; não é ocorrência confirmada |

Os cruzamentos cronológicos seguem as máscaras da seção 3.2. Pagamentos vazios e sentinelas foram excluídos das comparações que exigem data real. Não foi usado o ano 9999 para calcular atraso. Como não há data comprovada de extração nem histórico de mudanças de status, as faturas EM ABERTO não permitem afirmar o contas a receber atual em 20/10/2026.

### 4.3. Multiplicidade por UC e Competência

Os 21 pares repetidos envolvem 42 faturas, sem repetição de ID ou de linha completa. Exemplos:

| UC | Competência | IDs das Duas Faturas | Menor / Maior Total |
| :--- | :--- | :--- | ---: |
| `UC9131189` | 2023-10 | `FTX0000502`, `FTX0010268` | R$ 122,40 / R$ 131,27 |
| `UC9201920` | 2023-10 | `FTX0001488`, `FTX0015186` | R$ 72,44 / R$ 104,01 |
| `UC9236557` | 2022-07 | `FTX0016727`, `FTX0026324` | R$ 42,00 / R$ 52,49 |

Todos esses pares também não encontram UC no cadastro fornecido. Portanto, a resolução deve considerar a origem e a finalidade das faturas, sem deduplicação automática por UC/mês. Uma regra de unicidade dessa combinação exige confirmação do negócio.

### 4.4. Reconciliação dos Totais e Limites Analíticos

| Agregado Bruto | Valor |
| :--- | ---: |
| Soma de `valor_energia` | R$ 507.506.363,30 |
| Soma de `tributos` | R$ 169.168.784,28 |
| Soma de `valor_total` | R$ 676.675.147,58 |
| Diferença: total − energia − tributos | R$ 0,00 |
| Total das faturas PAGA | R$ 639.472.892,40 |
| Total das faturas EM ABERTO | R$ 37.202.255,18 |

As somas mensais e por status fecham com o total bruto. São valores do arquivo, incluindo faturas sem correspondência cadastral e os pares UC/mês em análise; **não são indicadores finais homologados**. O valor de faturas PAGA não comprova caixa efetivamente recebido, descontos, juros ou pagamentos parciais.

O arquivo não contém kWh faturado, tarifa unitária explícita, pagamento parcial ou motivo de reemissão. Consequentemente, não permite homologar tarifa, consumo faturado ou explicar a causa dos valores extremos. Um cruzamento futuro com leituras pode produzir um **preço efetivo calculado**, com as limitações de alinhamento temporal e de volume declaradas.

---

## 5. Plano Recomendado de Saneamento (Regras de ETL)

As regras seguintes são propostas para a **Silver** e não foram implementadas no projeto nesta auditoria. A ordem preserva a rastreabilidade antes de introduzir tipos e critérios de negócio.

1. **Preservação da Bronze:** Manter as 11 colunas como STRING, inclusive os cabeçalhos internos e valores brutos; carga completa com overwrite, um `ingestion_datetime` UTC fixo por execução e `source_file_path`. Essa coluna registra a ingestão, não a emissão, a competência ou a extração oficial da origem.
2. **Remoção Controlada de Cabeçalhos na Silver:** Identificar linhas em que **os 11 campos correspondem exatamente ao cabeçalho**, separá-las com motivo de rejeição e excluí-las apenas do universo de negócio. Para esta fonte, a contagem esperada passa de 2.184.623 para 2.184.621. Não filtrar por um único valor isolado, como `id_fatura = 'id_fatura'`.
3. **Validação de Chaves e Granularidade:** Exigir `id_fatura` não vazio e único; validar o padrão dos IDs sem criar exclusão por prefixo FT/FTX. Encaminhar os 21 pares UC/mês à análise de negócio; não escolher arbitrariamente a maior fatura, a última linha ou a de maior ID.
4. **Integridade com o Cadastro:** Construir uma referência de chaves distintas e controlar cardinalidade antes do JOIN. Reter as 32.285 faturas sem correspondência com indicador de pendência e trilha de reconciliação; evitar perda silenciosa em INNER JOIN. A consolidação dos atributos de UCs duplicadas no cadastro depende de uma regra própria de precedência, fora desta análise de IDs.
5. **Conversão Monetária Determinística:** Usar `DECIMAL(18,2)` para energia, tributos e total. Para strings que casem com `^[0-9]+\.[0-9]{2}$`, interpretar o ponto como decimal. Para `^R\$ [0-9]+,[0-9]{2}$` ou `^R\$ [0-9]{1,3}(\.[0-9]{3})+,[0-9]{2}$`, remover o símbolo e o separador de milhar, e converter a vírgula decimal. Outras representações devem gerar rejeição explícita, não NULL silencioso ou zero. Conferir `total = energia + tributos` em centavos/DECIMAL.
6. **Parsing de Competência e Datas:** Validar calendário após reconhecer a máscara: `YYYY-MM` para competência; `YYYY-MM-DD`, `DD/MM/YYYY` e `DD.MM.YYYY` para as datas correspondentes. Confirmar com a origem a convenção DMY assumida para barras e pontos antes de homologar a transformação. Para hífen com ano no fim, testar MM-DD e DD-MM: aceitar uma única data válida ou duas interpretações coincidentes; manter as 20.416 datas com interpretações distintas como pendência, junto do texto bruto. Se a origem confirmar formalmente a convenção americana para esse grupo, versionar a regra e reprocessar. Não resolver apenas pela proximidade da competência.
7. **Nulos de Pagamento e Domínios:** Converter vazio e `9999-12-31` para NULL em `data_pagamento`, preservando o motivo e o valor bruto. Validar a matriz status/pagamento: PAGA requer data real; EM ABERTO admite ausência. Controlar novos valores de status e bandeira contra um domínio documentado, sem inventar equivalências entre categorias.
8. **Alertas Estatísticos e Temporais:** Publicar indicadores de valores extremos, atraso e emissão fora da competência. Não excluir, limitar valores ou alterar datas automaticamente. Critérios de vencimento, elegibilidade, refaturamento e segmentação precisam de validação do negócio.
9. **Reconciliação e Critérios de Aceite:** Antes de promover a carga, conferir volumes brutos, cabeçalhos segregados, unicidade de ID, contagens de parsing, ambiguidades e pendências cadastrais. Após JOINs, exigir ausência de multiplicação de faturas e reconciliação de quantidades e somas com os registros explicitamente aceitos ou segregados. Sem mudanças na fonte, os indicadores devem reproduzir este relatório; uma divergência futura deve gerar diagnóstico e preservar a última versão válida conforme o contrato de processamento.

