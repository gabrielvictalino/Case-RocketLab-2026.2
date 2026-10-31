# Relatório de Auditoria e Tratamento de Dados (`faturas.csv`)

**Projeto:** V-Energy — Case RocketLab Visagio 2026.2.

**Escopo:** exploração, decisões, transformação Bronze → Silver, validação e publicação de faturas. Cadastro e leituras foram consultados como referências de chaves.

**Data de consolidação:** 23/10/2026, fuso America/Fortaleza.

**Revisão documental:** 29/10/2026, fuso America/Fortaleza. Registro da publicação executada pelo autor no Databricks e da cópia operacional com revisões em schema separado.

**Base de código:** commit `8381720b2bed81befcc95ba02ba9dc1b9cf75b8d` — ingestão Bronze unificada.

**Evidência de execução:** [publicacao.html](evidencias/faturas-2026-10-29/publicacao.html), anexo do autor com código e outputs históricos preservados, com 92 células e 42 células Python. A publicação de 29/10/2026 foi concluída entre 19h18min36s e 19h22min46s, no fuso America/Fortaleza.

**Versão operacional:** [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb), versão operacional sem outputs históricos, com revisões em `v-energy.silver_revisoes`. A versão anterior às correções de 31/10/2026 foi executada com `false` e `true` em 30/10/2026; os anexos estão no registro de evidências operacionais.

**Situação:** os dois destinos de `v-energy.silver` foram publicados e conferidos na execução anexada. A adoção de `silver_revisoes` está implementada na cópia operacional; a revisão documental não move nem recria tabelas existentes.

Os resultados deste relatório provêm das execuções no Databricks registradas no notebook e das tabelas CSV de resultados exportadas. Não se trata de uma nova execução independente sobre o CSV integral. Valores e contagens são um retrato da extração auditada, não constantes para impor a futuras entregas.

---

## 1. Panorama Geral e Sumário Executivo

### 1.1. Volumetria e saídas

| Universo | Registros | Soma de `valor_total` |
| :--- | ---: | ---: |
| Bronze de faturas | 2.184.623 | Não somar cabeçalhos como negócio |
| Cabeçalhos internos completos | 2 | Não aplicável |
| Faturas de negócio | 2.184.621 | R$ 676.675.147,58 |
| Com correspondência cadastral | 2.152.336 | R$ 666.482.773,76 |
| Sem correspondência cadastral | 32.285 | R$ 10.192.373,82 |

### 1.2. Principais ocorrências e decisões

| Tema | Ocorrência | Registros | Proporção sobre negócio | Tratamento adotado |
| :--- | :--- | ---: | ---: | :--- |
| Estrutura | Cabeçalhos completos no corpo da tabela | 2 | Não aplicável | Separar do negócio; preservar na Bronze |
| Chave | Duplicata exata nas onze colunas | 0 | 0,00% | Não aplicar deduplicação |
| Chave | `id_fatura` repetido | 0 | 0,00% | Exigir unicidade na validação |
| Grão | Mais de uma fatura por UC/competência | 42, em 21 pares | 0,0019% | Preservar e sinalizar; não escolher uma cobrança |
| Emissão | Duas datas distintas possíveis com hífen | 20.416 | 0,93% | Convenção MDY documentada, com ambiguidade original preservada |
| Emissão | Fora da competência após aplicar a convenção | 11.306 | 0,52% | Preservar e sinalizar |
| Pagamento | Nulo real | 113.835 | 5,21% | NULL com motivo de ausência |
| Pagamento | Sentinela `9999-12-31` | 61.333 | 2,81% | NULL com motivo de sentinela |
| Referência | UC não encontrada no cadastro disponível | 32.285 | 1,48% | Separar na tabela de pendências |
| Referência | Par UC/competência não encontrado em leituras | 32.285 | 1,48% | Sinalizar; nesta extração coincide com ausência cadastral |

As categorias se sobrepõem. As 42 faturas dos pares repetidos e as 32.285 sem leitura já pertencem ao grupo de 32.285 sem cadastro. Não somar essas contagens como rejeições independentes. Nulo de pagamento em fatura aberta, atraso e emissão fora da competência não foram classificados automaticamente como erros a excluir.

---

## 2. Fontes, Versões e Método

### 2.1. Fontes efetivamente lidas

| Fonte Delta | Versão utilizada | Registros |
| :--- | ---: | ---: |
| `v-energy.bronze.tb_faturas` | 0 | 2.184.623 |
| `v-energy.bronze.tb_unidades_consumidoras` | 0 | 46.461 |
| `v-energy.bronze.tb_leituras` | 0 | 2.182.468 |

Cada leitura fixa uma versão Delta, evitando que consultas posteriores à mesma fonte utilizem estados diferentes durante a execução. Isso não comprova, isoladamente, que as três tabelas correspondam à mesma extração de origem.

A Bronze desta implementação recebe a história completa por substituição. Não foi aplicada a regra de selecionar apenas o maior timestamp de ingestão nem deduplicação para compensar supostos lotes em append. O guia CineData foi usado como apoio de método; suas regras de filmes e sua estratégia de append não foram transferidas automaticamente ao V-Energy.

### 2.2. Sequência da análise

1. Inspecionar schema, versão, volume e amostra.
2. Separar cabeçalhos e avaliar completude, domínios e repetições.
3. Avaliar pagamentos e formatos de emissão.
4. Comparar cenários de datas antes de escolher a convenção.
5. Tipar e reconciliar dinheiro por registro.
6. Verificar referências sem multiplicar faturas.
7. Construir e validar a candidata em memória.
8. Conferir tabelas de revisão e publicar os destinos aprovados.

---

## 3. Diagnóstico Estrutural, Chaves e Completude

### 3.1. Estrutura da Bronze

As onze colunas de negócio são `id_fatura`, `id_uc`, `mes_referencia`, `data_emissao`, `valor_energia`, `tributos`, `bandeira_tarifaria`, `valor_total`, `data_vencimento`, `data_pagamento` e `status`.

Todas chegam como `STRING`. A Bronze acrescenta `source_file`, também texto, e `ingestion_datetime`, como `TIMESTAMP`. A presente reconstrução partiu da tabela Bronze; a leitura estrutural independente do CSV completo não foi repetida nesta etapa.

### 3.2. Cabeçalhos internos

Foram identificadas duas linhas em que os onze campos são exatamente iguais aos respectivos nomes das colunas. A condição usa o conjunto completo, não um único identificador isolado. Essas linhas são separadas em `df_cabecalhos_internos`; o original continua na Bronze. Não foi criada uma tabela permanente de cabeçalhos nesta implementação.

```text
2.184.623 linhas Bronze = 2 cabeçalhos internos + 2.184.621 faturas
```

### 3.3. Chaves e grão

- `id_fatura` é único e preenchido em todas as 2.184.621 faturas.
- Não há duplicata exata nas onze colunas de negócio.
- A principal exige `id_fatura` no padrão `^FT[0-9]{9}$`. O diagnóstico contou 32.285 identificadores `FTX`, preservados nas pendências cadastrais. Os IDs de UC seguem `UC` seguido de números.
- Existem 21 pares UC/competência repetidos, com 42 faturas de IDs distintos.

**Decisão:** manter o grão de uma linha por `id_fatura`. Não impor unicidade por UC/mês nem selecionar arbitrariamente maior ID, maior valor ou última linha. Nenhuma linha foi descartada pelo prefixo; um ID fora do contrato bloqueia sua entrada na principal, enquanto as faturas sem cadastro são preservadas nas pendências.

### 3.4. Completude e categorias

Nas onze colunas, somente `data_pagamento` apresentou nulos reais: 113.835. Não foram observados valores vazios ou somente espaços, espaços nas extremidades ou o texto literal `null`.

| `status` | Faturas |
| :--- | ---: |
| PAGA | 2.009.453 |
| EM ABERTO | 175.168 |

| `bandeira_tarifaria` | Faturas |
| :--- | ---: |
| Verde | 1.546.130 |
| Amarela | 273.630 |
| Vermelha P1 | 228.042 |
| Vermelha P2 | 136.819 |

Não foi aplicada normalização de caixa ou espaços às colunas de negócio, pois essas variações não foram observadas. Os domínios acima são verificados no contrato da candidata.

---

## 4. Datas: Diagnóstico e Decisão de Interpretação

### 4.1. Representações da emissão

| Representação bruta | Máscara testada | Faturas |
| :--- | :--- | ---: |
| ISO, ano no início | `yyyy-MM-dd` | 2.001.260 |
| Barras, ano no fim | `dd/MM/yyyy` | 61.291 |
| Pontos, ano no fim | `dd.MM.yyyy` | 61.252 |
| Hífen, ano no fim | `MM-dd-yyyy` e `dd-MM-yyyy` | 60.818 |
| **Total** | | **2.184.621** |

As competências passaram na verificação de formato `AAAA-MM`. Nenhuma emissão ficou sem uma interpretação pelas máscaras testadas. Para barras e pontos, DMY é uma convenção do projeto; validade de calendário não confirma sozinha o significado original.

### 4.2. Ambiguidade com hífen e ano no fim

| Resultado das duas máscaras | Faturas |
| :--- | ---: |
| Somente MDY válido | 38.615 |
| Somente DMY válido | 0 |
| Mesma data em MDY e DMY | 1.787 |
| Duas datas distintas | 20.416 |

Exemplos observados:

- `FT000000056`, texto `03-10-2023`: MDY produz 10/03/2023, compatível com vencimento em 22/03/2023; DMY produz 03/10/2023, posterior ao vencimento.
- `FT000000143`, texto `06-04-2026`: MDY produz 04/06/2026 e DMY produz 06/04/2026; ambas são anteriores ao vencimento e ao pagamento informados.

### 4.3. Comparação dos cenários

Os cenários mudam a interpretação de todo o grupo com hífen e ano no fim. Nas demais representações, mantêm ISO ou a convenção DMY de barras/pontos.

| Indicador | Hífen como MDY | Hífen como DMY |
| :--- | ---: | ---: |
| Registros analisados | 2.184.621 | 2.184.621 |
| Emissões não interpretadas | 0 | 38.615 |
| Emissões fora da competência, entre as interpretadas | 11.306 | 31.269 |
| Emissões após vencimento | 0 | 11.905 |
| Pagamentos anteriores à emissão | 0 | 10.464 |
| Cronologia compatível | 2.184.621 | 2.134.101 |
| Registros que exigem investigação no cenário | 0 | 50.520 |

Os indicadores de problema se sobrepõem e não devem ser somados. Cada candidata precisa respeitar vencimento e pagamento simultaneamente. Entre as 20.416 ambíguas, 11.905 admitem somente MDY pela cronologia e 8.511 admitem ambas as ordens.

**Decisão adotada:** interpretar hífen com ano no fim como MDY, documentando a convenção e preservando o texto bruto, `metodo_interpretacao_emissao` e `flag_emissao_original_ambigua`. A evidência fundamenta a escolha operacional; não demonstra a origem verdadeira das 8.511 datas compatíveis nas duas ordens.

As 11.306 emissões fora da competência são preservadas e sinalizadas. A contagem não deve ser confundida com 11.179 citados na auditoria de referência anterior: aquele indicador considerava todas as interpretações válidas; o indicador atual usa a data escolhida pela convenção.

### 4.4. Vencimento, pagamento e status

| Situação | Faturas | Tratamento |
| :--- | ---: | :--- |
| EM ABERTO, pagamento nulo | 113.835 | DATE nula, motivo `CAMPO_NULO` |
| EM ABERTO, pagamento `9999-12-31` | 61.333 | DATE nula, motivo `SENTINELA_9999_12_31` |
| PAGA, pagamento ISO válido | 2.009.453 | DATE preservada |

Não foram observados pagamentos com outro formato ou calendário inválido, vencimentos não interpretados, PAGA sem data real ou EM ABERTO com data real.

- Vencimentos interpretados: 15/07/2022 a 12/07/2026.
- Pagamentos reais interpretados: 11/07/2022 a 06/08/2026.
- Pagamentos posteriores ao vencimento: 1.675.636, aproximadamente 83,39% das faturas PAGA.

Atraso foi preservado como ocorrência de negócio. Não se calculou a posição atual de inadimplência nem se inventou a data oficial da extração.

---

## 5. Valores Monetários e Conciliação

### 5.1. Formatos reconhecidos

Energia e tributos usam decimal com ponto em todas as 2.184.621 faturas. O total apresenta:

| Forma de `valor_total` | Faturas | Soma interpretada |
| :--- | ---: | ---: |
| Decimal com ponto | 1.987.999 | R$ 615.579.684,65 |
| Reais com vírgula, sem agrupamento de milhares | 188.571 | R$ 31.728.807,46 |
| Reais com vírgula e agrupamento de milhares | 8.051 | R$ 29.366.655,47 |

**Decisão:** reconhecer a gramática antes de remover símbolos ou separadores e converter para `DECIMAL(18,2)`. Não usar ponto flutuante, preenchimento com zero ou correção arbitrária de sinais.

### 5.2. Limites observados e totais

| Campo | Menor valor | Maior valor | Soma |
| :--- | ---: | ---: | ---: |
| `valor_energia` | R$ 4,78 | R$ 35.810,60 | R$ 507.506.363,30 |
| `tributos` | R$ 1,59 | R$ 11.936,87 | R$ 169.168.784,28 |
| `valor_total` | R$ 6,37 | R$ 47.747,47 | R$ 676.675.147,58 |

Não houve falha de interpretação, zero ou negativo nos três campos. Todas as 2.184.621 faturas satisfazem exatamente `valor_energia + tributos = valor_total`; a tabela de divergências ficou vazia.

Valores altos foram preservados sem teto estatístico de exclusão. A conciliação confirma coerência aritmética interna; não valida tarifas, alíquotas, legitimidade da cobrança ou caixa efetivamente recebido.

---

## 6. Integridade Referencial e Cardinalidade

### 6.1. Cadastro de unidades consumidoras

O cadastro consultado contém 46.461 linhas. Foram observadas chaves repetidas, ausência de nulos/vazios/espaços nos IDs e 201 valores fora do padrão, incluindo uma ocorrência literal de `id_uc`.

O notebook usou somente uma projeção de chaves distintas e um left join. Não selecionou atributos cadastrais conflitantes e não deduplicou a entidade cadastral para fins de enriquecimento.

| Correspondência | Faturas | UCs distintas | Energia | Tributos | Total |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Encontrada | 2.152.336 | 45.000 | R$ 499.862.082,73 | R$ 166.620.691,03 | R$ 666.482.773,76 |
| Não encontrada | 32.285 | 31.705 | R$ 7.644.280,57 | R$ 2.548.093,25 | R$ 10.192.373,82 |

A parcela sem cadastro representa aproximadamente 1,48% das faturas e 1,51% do total monetário. Ela foi preservada em uma saída própria. Ausência no cadastro disponível não comprova inexistência no sistema oficial, fraude ou invalidade de cada cobrança.

Todos os 21 pares UC/mês repetidos pertencem ao grupo sem cadastro. As 42 faturas somam R$ 20.341,61, já incluídos no total da saída de pendências. Não houve uma segunda exclusão por multiplicidade.

### 6.2. Referência com leituras

| Arquivo de leituras | Registros |
| :--- | ---: |
| `leituras_2022.csv` | 271.744 |
| `leituras_2023.csv` | 544.546 |
| `leituras_2024.csv` | 545.652 |
| `leituras_2025.csv` | 546.908 |
| `leituras_2026.csv` | 273.618 |
| **Total** | **2.182.468** |

Não foram encontrados cabeçalhos internos completos, IDs de UC ausentes/fora do padrão ou competências ausentes/inválidas nos critérios testados. Existem 2.152.336 pares UC/competência; 30.061 têm mais de uma leitura, com máximo de três registros por par.

A referência foi reduzida a uma linha por par antes do join. A existência de várias leituras não foi confundida com várias faturas nem utilizada para multiplicar valores financeiros.

| Referência cadastral | Referência UC/mês em leituras | Faturas | Total |
| :--- | :--- | ---: | ---: |
| Encontrada | Encontrada | 2.152.336 | R$ 666.482.773,76 |
| Não encontrada | Não encontrada | 32.285 | R$ 10.192.373,82 |
| Encontrada | Não encontrada | 0 | R$ 0,00 |

O cruzamento manteve 2.184.621 faturas antes e depois. A referência comprova presença de chave na Bronze de leituras, não correção do consumo nem conclusão da Silver de medição. Não foi criada uma regra universal de exclusão por ausência de leitura; a separação implementada é cadastral.

---

## 7. Transformações e Rastreabilidade da Silver

### 7.1. Campos de negócio

| Campos | Tipo final | Tratamento |
| :--- | :--- | :--- |
| `id_fatura`, `id_uc` | STRING | Preservar; verificar padrão e unicidade da fatura |
| `mes_referencia` | STRING | Validar `AAAA-MM`; não substituir por mês da emissão/pagamento |
| `data_emissao` | DATE | ISO ou convenção DMY/MDY conforme representação |
| `data_vencimento` | DATE | Interpretar formato ISO |
| `data_pagamento` | DATE | ISO real; ausência/sentinela vira NULL com motivo |
| `valor_energia`, `tributos`, `valor_total` | DECIMAL(18,2) | Gramáticas explícitas e conciliação exata |
| `status`, `bandeira_tarifaria` | STRING | Preservar grafias observadas e validar domínios |

### 7.2. Evidências e indicadores

A saída possui 25 colunas de primeiro nível. Além das onze de negócio:

- `dados_originais`: STRUCT com as onze colunas brutas.
- `source_file` e `ingestion_datetime`: metadados de origem preservados.
- `metodo_interpretacao_emissao`: identifica ISO ou a convenção aplicada.
- `motivo_ausencia_pagamento`: distingue campo nulo e sentinela.
- `flag_emissao_original_ambigua`, `flag_emissao_fora_competencia`, `flag_pagamento_atrasado`, `flag_uc_sem_cadastro`, `flag_sem_leitura_uc_mes` e `flag_multiplas_faturas_uc_mes`: indicadores de qualidade e contexto.
- `versoes_bronze`: STRUCT com as versões de faturas, cadastro e leituras.
- `versao_regras`: `FATURAS_CANDIDATA_V1`, valor preservado no resultado publicado.
- `situacao_referencia_cadastral`: `CADASTRO_ENCONTRADO` ou `PENDENTE_CADASTRO`.

Na candidata completa, os indicadores somaram respectivamente 20.416, 11.306, 1.675.636, 32.285, 32.285 e 42. Essas contagens descrevem a candidata reunida, não somente a tabela principal depois da separação.

Os métodos possíveis de emissão são `ISO_ANO_MES_DIA`, `CONVENCAO_DMY_BARRAS`, `CONVENCAO_DMY_PONTOS` e `CONVENCAO_MDY_HIFEN`. A indicação de ambiguidade permanece mesmo após escolher uma data pela convenção.

---

## 8. Validações Executadas

| Verificação | Evidência registrada |
| :--- | :--- |
| Tipos, chaves e regras por registro | Mensagem de aprovação; IDs únicos e campos obrigatórios verificados |
| Cronologia da emissão escolhida | Nenhuma emissão após vencimento ou pagamento anterior à emissão no cenário adotado |
| Originais e metadados | `exceptAll` em ambas as direções contra a Bronze de negócio, sem diferenças |
| Valores tipados | Comparação completa das onze colunas com os diagnósticos monetários e de datas, sem diferenças |
| Separação das saídas | Reunião integralmente igual à candidata; IDs sem interseção |
| Conservação financeira | Quantidades e somas iguais por competência e status |
| Tabelas de revisão persistidas | Schema e conteúdo completo iguais aos DataFrames esperados |
| Destinos definitivos | Schema e conteúdo completo iguais às referências de revisão utilizadas |

As mensagens de aprovação, os outputs e os CSVs exportados são evidências da execução. Contagens e somas isoladas não foram tratadas como prova suficiente de preservação: também houve comparação de registros com multiplicidade. A comparação das datas tipadas confirma a aplicação da convenção escolhida, não sua veracidade externa.

O schema pode declarar `nullable = true` sem haver nulos reais nos campos obrigatórios. A obrigatoriedade foi avaliada nos registros, não inferida somente da declaração do schema.

### 8.1. Correção posterior do bloqueio de pagamentos — issue #27

A revisão do código identificou que uma fatura `EM ABERTO` com pagamento não interpretável poderia receber `data_pagamento = NULL` e `motivo_ausencia_pagamento = NULL` sem acionar as regras de status/pagamento. O diagnóstico mostrava o problema, mas sua contagem não bloqueava automaticamente a candidata. Não houve ocorrência desse caso na extração auditada.

Foi acrescentada à Seção 10 a regra `pagamento_nao_interpretado`: a combinação de pagamento tipado nulo e motivo nulo passa a ser falha de qualidade. Nulo original continua com motivo `CAMPO_NULO`, e sentinela com `SENTINELA_9999_12_31`; datas válidas continuam tipadas. As regras existentes para `PAGA` sem pagamento e `EM ABERTO` com pagamento permanecem aplicáveis.

A execução completa de 29/10/2026 inclui a regra `pagamento_nao_interpretado` e registrou aprovação da Seção 10 antes da escrita. A evidência está nas células 72–76 do anexo preservado. A [issue #27](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/27) registra a correção. A aprovação nesta extração não dispensa a validação em novas cargas.

---

## 9. Revisão Intermediária e Publicação Definitiva

### 9.1. Migração inicial e execução atual

A migração de 23/10/2026 criou as revisões `_revisao_v1`, ambas na versão 0,
e publicou a principal na versão 1 e as pendências na versão 0. Esse é o
estado histórico anterior à rodada aqui consolidada.

Em 29/10/2026 o autor executou o notebook completo com
`confirmar_publicacao=true`, entre 19h18min36s e 19h22min46s, no fuso
America/Fortaleza. As 42 células Python executaram em sequência, sem erros
ou `Command skipped`. A revisão deste relatório leu o arquivo exportado;
não executou uma nova carga nem consultou o catálogo ao vivo.

### 9.2. Revisões criadas e conferidas

A candidata foi calculada a partir das três fontes Bronze na versão 0,
persistida em cache e validada. A célula 86 criou estas duas revisões:

| Revisão em `v-energy.silver` | Versão Delta | Faturas | Total |
| :--- | ---: | ---: | ---: |
| `tb_faturas_revisao_1bb6358d020a4ca1b1148d09c87c2fc7` | 0 | 2.152.336 | R$ 666.482.773,76 |
| `tb_faturas_pendentes_cadastro_revisao_1bb6358d020a4ca1b1148d09c87c2fc7` | 0 | 32.285 | R$ 10.192.373,82 |

A célula 87 comparou nomes, ordem e tipos das colunas e o conteúdo completo
contra os DataFrames da mesma execução, com `exceptAll` nos dois sentidos.
Os originais, indicadores e metadados técnicos participaram da conferência.
O procedimento cria suas próprias revisões: uma nova ingestão não é
comparada com carimbos técnicos de revisões antigas.

### 9.3. Resultado publicado em 29/10/2026

| Destino definitivo | Versão Delta | Faturas | Energia | Tributos | Total |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `v-energy.silver.tb_faturas` | 2 | 2.152.336 | R$ 499.862.082,73 | R$ 166.620.691,03 | R$ 666.482.773,76 |
| `v-energy.silver.tb_faturas_pendentes_cadastro` | 1 | 32.285 | R$ 7.644.280,57 | R$ 2.548.093,25 | R$ 10.192.373,82 |
| **Conjunto preservado** | — | **2.184.621** | **R$ 507.506.363,30** | **R$ 169.168.784,28** | **R$ 676.675.147,58** |

A célula 90 registrou `CREATE OR REPLACE TABLE AS SELECT` nos dois destinos.
A célula 91 aprovou seus schemas e conteúdos completos nas versões publicadas.
A célula 92 apresentou a reconciliação e concluiu com
`OK: publicação definitiva concluída e conferida.`. Não há evidência de
publicação parcial nessa rodada. Cada tabela tem seu próprio histórico Delta;
as versões 2 e 1 não precisam ser iguais.

### 9.4. Vínculo entre conferência e publicação — issue #28

O plano registra a fonte, a versão, o snapshot conferido e o estado anterior
do destino. A escrita exige validações e conferências concluídas na sessão,
revalida a identidade e a versão das fontes e verifica os destinos antes
da primeira escrita e imediatamente antes de cada substituição.

As revisões desta rodada estavam na versão 0 por serem novas. O código
publica a versão efetivamente conferida, sem exigir versão 0. A proteção
da [issue #28](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/28)
continua aplicável. As duas gravações são transações separadas; uma falha
entre elas pode deixar resultado parcial e exige investigação.

### 9.5. Schema separado na versão operacional

O anexo de execução mantém o código e os outputs históricos e continua registrando
revisões em `silver`. A cópia `bronze-to-silver-faturas.ipynb`
define `SCHEMA_REVISOES = "silver_revisoes"`: as futuras revisões ficam em
`v-energy.silver_revisoes` e os destinos finais permanecem em `v-energy.silver`.
Com o parâmetro `false`, nenhum dos schemas ou tabelas é gravado.

Os outputs de 30/10/2026 foram retirados da cópia operacional e preservados apenas nas evidências estáticas. A versão anterior às correções de 31/10/2026 foi executada com `false` e `true` em 30/10/2026, incluindo publicação a partir de `silver_revisoes`. As tabelas acima registram a execução histórica de 29/10/2026; as novas evidências e versões Delta estão no registro operacional. O versionamento não move, apaga ou republica as tabelas
já existentes. O procedimento está em [Operação e revisões](operacao_faturas.md).

---

## 10. Correspondência com as Seções do Notebook

| Seção | Papel no processo |
| :--- | :--- |
| 1 | Configuração, versão Delta, schema e volume da origem |
| 2 | Cabeçalhos, completude, categorias e repetições |
| 3 | Pagamentos, sentinelas e coerência com status |
| 4 | Formatos de emissão e candidatas de data |
| 5 | Cenários cronológicos e fundamento da convenção MDY |
| 6 | Tipagem monetária e conciliação por fatura |
| 7 | Correspondência cadastral e sobreposição das ocorrências |
| 8 | Correspondência com pares UC/competência em leituras |
| 9 | Tipagem, preservação, indicadores e separação em memória |
| 10 | Validação da candidata e reconciliação das saídas |
| 11 | Inspeção dos destinos definitivos e comparação de contrato |
| 12 | Criação das revisões da execução e conferência da persistência |
| 13 | Publicação definitiva baseada nas revisões e conferência posterior |

As explorações e seus resultados são mantidos para apresentação e discussão das decisões. Não é necessário reexecutar o notebook para acrescentar os textos explicativos.

---

## 11. Limites e Condições para Uso Analítico

1. **Convenções de datas:** MDY/DMY são decisões documentadas do projeto. Não houve confirmação formal da origem de cada data ambígua.
2. **Referências Bronze:** os cruzamentos atestam presença de chaves. Não concluem tratamento cadastral, qualidade de consumo ou todas as relações com medidores.
3. **Cobranças múltiplas:** faltam informações de reemissão/cancelamento para esclarecer o significado das 42 faturas. Elas foram preservadas nas pendências cadastrais, sem escolha arbitrária.
4. **Cobertura financeira:** análises da principal devem divulgar que R$ 10.192.373,82 foram segregados por falta cadastral. Não representar essa parcela como receita zero nem como receita homologada.
5. **Semântica financeira:** não há validação externa de tarifas ou alíquotas, nem suporte suficiente para inventar kWh faturado, tarifa unitária ou posição atual de inadimplência.
6. **CSV integral:** a preservação comprovada nesta reconstrução é Bronze de negócio → saídas Silver. Não repetir como nova evidência uma comparação CSV/Bronze que não foi reexecutada aqui.
7. **Atomicidade:** Delta é atômico por tabela. As duas saídas não formam uma transação conjunta; uma execução parcial exige investigação. O consumo automatizado precisa depender da conclusão bem-sucedida do fluxo.
8. **Rotina futura:** cada execução calcula e valida a candidata a partir de versões fixadas da Bronze, cria revisões próprias e publica os snapshots conferidos. A cópia operacional isola as revisões em `silver_revisoes` e teve essa configuração validada no Databricks em 30/10/2026. A operação exige uma execução publicadora por vez.
9. **Escopo de entrega:** a publicação de faturas não comprova conclusão das outras entidades Silver, da Gold, do portal ou de um Workflow integrado. Não se afirmou execução desses componentes.

---

## 12. Conclusão

A reconstrução de faturas foi explorada, justificada, validada e publicada para a extração analisada. O conjunto de negócio foi preservado sem deduplicação arbitrária, com tipagem explícita, rastreabilidade e conciliação exata por registro e por agrupamentos.

A principal possui 2.152.336 faturas com correspondência cadastral; 32.285 permanecem identificadas na tabela de pendências. A convenção de datas e os limites de interpretação continuam documentados. O notebook completo e seus outputs são preservados como evidência do processo.

O versionamento deste relatório e da correção não representa uma nova execução da carga nem uma nova publicação dos destinos Delta.

### Referências de evidência

- [publicacao.html](evidencias/faturas-2026-10-29/publicacao.html): anexo preservado com as saídas da publicação de 29/10/2026.
- [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb): versão com revisões em schema separado e publicação confirmada por marcador Delta.
- [Operação e revisões](operacao_faturas.md): destinos, parâmetro e limites da execução.
- CSVs de resultados exportados das Seções 2–13 e disponibilizados durante a revisão. Os nomes se repetem entre etapas; a associação é feita pelo conteúdo e pela seção correspondente.
- Enunciado “Case Final - RocketLab Visagio 2026.2”: responsabilidades Silver, integridade referencial e documentação de suposições.
- Commit-base `8381720b2bed81befcc95ba02ba9dc1b9cf75b8d`: `data-engineering/Landing_to_Bronze.ipynb` e `docs/auditoria_dados/decisoes_landing_to_bronze.md`.
- Auditorias existentes de cadastro, medidores e leituras consultadas como referências do projeto; seus nomes antigos de catálogo não substituem os objetos `v-energy` efetivamente utilizados nesta execução.

## Atualização operacional — 30/10/2026

As execuções com `false` e `true` foram conferidas no código Python da versão operacional no commit `d88ebeb`. A publicação com `true` criou revisões em `silver_revisoes` e publicou `silver.tb_faturas` na versão Delta **3** e `silver.tb_faturas_pendentes_cadastro` na versão **2**. As contagens e os valores foram mantidos. Tabelas referentes a 29/10/2026 neste documento permanecem como histórico.

Consulte o [registro das novas evidências](evidencias_operacionais_faturas.md), com anexos originais, horários, hashes e limites da validação. Os anexos conservam os nomes anteriores à renomeação.


## Correções de publicação — 31/10/2026

O notebook operacional agora inicia com widget salvo em `false`, sem outputs.
Bloqueia divergências de schema, valida IDs das pendências e confirma o par
de snapshots via marcador Delta. Evidências HTML registram somente as execuções
anteriores. O novo código ainda precisa ser executado em catálogo de teste.
Consulte [operação de faturas](operacao_faturas.md).
