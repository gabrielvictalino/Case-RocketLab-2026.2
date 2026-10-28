# Textos para apresentação do notebook de faturas

**Notebook de referência:** [bronze-to-silver-faturas-corrigido.ipynb](../../data-engineering/bronze_to_silver/bronze-to-silver-faturas-corrigido.ipynb), com 92 células e outputs históricos preservados.

**Objetivo deste arquivo:** fornecer textos para as células Markdown, mantendo os códigos, as explorações e os outputs existentes.

Copiar cada seção abaixo para a célula Markdown correspondente. Os resultados numéricos são evidências da extração executada, não constantes que o código deve impor a futuras cargas. As Seções 11–13 registram a migração inicial já concluída; não representam uma rotina mensal independente das tabelas de revisão.

**Execução:** não é necessário executar código nem clicar em Run All para inserir estes textos. Uma execução completa também executaria a publicação da Seção 13 e poderia substituir os outputs que documentam o histórico.

---

## 1. Configuração e inspeção da origem

**Objetivo.** Identificar a origem das faturas e registrar o estado dos dados usado na exploração. A implementação parte da ingestão Bronze unificada do commit `8381720b2bed81befcc95ba02ba9dc1b9cf75b8d`, no catálogo `v-energy`.

**Decisão.** Ler `bronze.tb_faturas` por uma versão Delta fixa. A Bronze recebe a extração completa por substituição; por isso, não selecionamos automaticamente apenas o maior `ingestion_datetime` nem removemos supostos lotes repetidos. O timestamp de ingestão é metadado técnico, não a data de extração do sistema de origem.

**Resultado observado.** A versão 0 contém 2.184.623 linhas, com onze colunas de negócio como `STRING`, mais `source_file` e `ingestion_datetime`. A amostra inicial serve para conhecer os campos; a avaliação de qualidade usa a base completa nas seções seguintes.

## 2. Diagnóstico de qualidade, cabeçalhos e repetições

**Objetivo.** Separar problemas estruturais de questões de conteúdo e distinguir três situações: cópia exata de uma linha de negócio, repetição de `id_fatura` e múltiplas faturas para a mesma UC/competência.

**Resultado observado.** Foram encontrados dois cabeçalhos internos completos, restando 2.184.621 faturas. Não há duplicatas exatas nas onze colunas nem IDs de fatura repetidos. Existem 21 pares UC/mês com duas faturas cada, totalizando 42 registros. Somente `data_pagamento` apresenta nulos reais: 113.835. Não foram encontrados textos vazios, espaços nas extremidades ou texto literal `null` nas onze colunas.

**Decisão.** Identificar cabeçalho somente quando os onze campos correspondem exatamente aos respectivos nomes. Preservar os cabeçalhos na Bronze e em um DataFrame de inspeção. Não aplicar deduplicação por UC/mês, porque IDs diferentes não comprovam cópias. Manter status e bandeiras nas grafias observadas, pois não foi demonstrada necessidade de normalização de caixa ou espaços.

## 3. Pagamentos ausentes e coerência com o status

**Objetivo.** Distinguir ausência legítima, sentinela, formato não reconhecido e data de calendário inválida. A classificação é cruzada com o status antes de escolher o tratamento.

**Resultado observado.** As 175.168 faturas `EM ABERTO` se dividem em 113.835 pagamentos nulos e 61.333 sentinelas `9999-12-31`. As 2.009.453 faturas `PAGA` têm data ISO válida. Não foram observados conflitos de status/pagamento, formatos inválidos ou vencimentos não interpretados. Há 1.675.636 pagamentos posteriores ao vencimento.

**Decisão.** Representar pagamento nulo e sentinela como `NULL` na coluna tipada, preservando o motivo e o valor bruto. Preservar o atraso como fato e sinalizá-lo. Não preencher pagamento com vencimento, zero ou data atual. O status representa o conteúdo da extração; sem sua data oficial, não equivale à posição atual de inadimplência.

## 4. Representações e ambiguidades da emissão

**Objetivo.** Reconhecer as representações de `data_emissao` e testar quais máscaras produzem datas válidas, sem escolher uma interpretação apenas para fazê-la coincidir com a competência.

**Resultado observado.** Há 2.001.260 valores ISO, 61.291 com barras, 61.252 com pontos e 60.818 com hífen e ano no fim. No último grupo, 38.615 admitem somente MDY, 1.787 produzem a mesma data em MDY e DMY e 20.416 produzem duas datas distintas. Nenhum valor ficou sem interpretação pelas máscaras testadas e nenhuma competência apresentou formato inválido.

**Decisão.** Separar validade de calendário de certeza sobre o significado da origem. DMY para barras e pontos é uma convenção documentada do projeto. Para hífen com ano no fim, manter as duas candidatas durante o diagnóstico e avaliar sua cronologia na seção seguinte. Um parsing bem-sucedido, sozinho, não confirma o significado verdadeiro da data.

## 5. Comparação dos cenários MDY e DMY

**Objetivo.** Medir o efeito de cada convenção sobre emissão, competência, vencimento e pagamento. A mesma data candidata deve respeitar simultaneamente as comparações cronológicas.

**Resultado observado.** MDY interpreta todas as 2.184.621 emissões e não produz emissão após vencimento nem pagamento anterior à emissão. DMY deixa 38.615 emissões sem interpretação, produz 11.905 emissões após vencimento e 10.464 pagamentos anteriores à emissão. Entre as 20.416 datas ambíguas, somente MDY respeita a cronologia em 11.905; ambas as ordens são compatíveis em 8.511.

**Decisão.** Adotar MDY para hífen com ano no fim como convenção fundamentada do projeto, preservando texto original, método e indicador de ambiguidade. Com essa convenção, 11.306 emissões ficam fora da competência e são preservadas com indicador. Coincidir com a competência não é critério de escolha. As 8.511 datas compatíveis nas duas ordens continuam sendo uma limitação de conhecimento da origem, embora recebam uma interpretação operacional explícita.

## 6. Valores monetários e conciliação por fatura

**Objetivo.** Reconhecer os formatos monetários, converter com precisão decimal e verificar `valor_energia + tributos = valor_total` em cada fatura, além das somas globais.

**Resultado observado.** Energia e tributos usam decimal com ponto em todas as faturas. O total apresenta 1.987.999 valores com ponto, 188.571 em reais sem agrupamento de milhares e 8.051 em reais com agrupamento. Não houve falha de interpretação, zero ou negativo nos três campos. Todas as 2.184.621 faturas conciliam exatamente.

**Decisão.** Converter pelas gramáticas verificadas para `DECIMAL(18,2)`, sem limpeza indiscriminada, conversão para ponto flutuante ou preenchimento de falhas com zero. Preservar valores altos sem teto arbitrário: o maior total observado foi R$ 47.747,47. As somas são R$ 507.506.363,30 de energia, R$ 169.168.784,28 de tributos e R$ 676.675.147,58 de total. A conciliação prova coerência aritmética, não a legitimidade da cobrança ou a correção de tarifas.

## 7. Identificadores e correspondência cadastral

**Objetivo.** Verificar os identificadores e a presença das UCs faturadas no cadastro disponível, preservando a cardinalidade das faturas.

**Resultado observado.** Todos os IDs das faturas seguem os padrões testados. O cadastro Bronze versão 0 contém 46.461 linhas e apresenta IDs repetidos, sem espaços nas extremidades. Há 201 valores cadastrais fora do padrão, incluindo a string `id_uc`. Encontramos 2.152.336 faturas com cadastro, em 45.000 UCs, e 32.285 sem cadastro, em 31.705 UCs. As 42 faturas dos pares UC/mês repetidos estão integralmente no grupo sem cadastro.

**Decisão.** Cruzar com chaves distintas para não multiplicar valores financeiros. Isso não escolhe atributos cadastrais conflitantes nem conclui a Silver do cadastro. Separar as faturas sem referência em uma saída de pendências, com preservação e reconciliação; não inferir fraude nem excluir pelo prefixo do ID. Os R$ 20.341,61 dos pares repetidos já estão incluídos nos R$ 10.192.373,82 sem cadastro e não devem ser contados novamente.

## 8. Correspondência com leituras

**Objetivo.** Investigar a presença do par UC/competência em medição e sua relação com a ausência cadastral. O cruzamento utiliza somente chaves, sem incorporar consumo ainda não tratado.

**Resultado observado.** A Bronze de leituras versão 0 contém 2.182.468 registros, sem cabeçalhos internos completos e sem chaves ausentes ou fora dos padrões testados. São 2.152.336 pares UC/mês; 30.061 têm mais de uma leitura, chegando a três. Todas as 2.152.336 faturas com cadastro encontram o par em leituras. As 32.285 sem cadastro também não encontram esse par. O cruzamento manteve as 2.184.621 faturas.

**Decisão.** Usar uma linha por par de referência, evitando multiplicação das faturas. Manter um indicador de ausência de leitura. A existência do par não homologa o consumo, e sua ausência não foi transformada em regra universal de exclusão. O tratamento da Silver de leituras permanece fora deste notebook.

## 9. Construção da candidata Silver em memória

**Objetivo.** Aplicar as decisões fundamentadas na exploração e produzir uma representação tipada sem perder o conteúdo de origem.

**Implementação.** Datas são convertidas para `DATE`; energia, tributos e total para `DECIMAL(18,2)`. As onze colunas brutas ficam no `STRUCT dados_originais`. São preservados arquivo e timestamp de ingestão e registradas as versões Bronze de faturas, cadastro e leituras. O método de interpretação da emissão e o motivo de ausência de pagamento ficam explícitos.

**Resultado observado.** A candidata tem 25 colunas de primeiro nível. Preserva as 2.184.621 faturas e sinaliza ambiguidade original, emissão fora da competência, atraso, ausência cadastral, ausência de leitura e multiplicidade UC/mês. A separação produz 2.152.336 faturas com cadastro e 32.285 pendentes. A escolha de uma data por convenção não apaga a ambiguidade original.

## 10. Validação da candidata e conservação dos dados

**Objetivo.** Verificar a aplicação das regras e a conservação dos registros antes de qualquer publicação definitiva.

**Verificações executadas.** Tipos, unicidade e formato de chaves, obrigatoriedade, domínios, cronologia da data escolhida, coerência entre status e pagamento e conciliação monetária. Os originais e metadados recuperados da candidata foram comparados à Bronze de negócio com `exceptAll` nas duas direções. Os valores tipados foram comparados aos diagnósticos anteriores; as duas saídas foram reunidas e comparadas integralmente à candidata, sem sobreposição de IDs. Quantidades e somas também foram reconciliadas por competência e status.

**Resultado observado.** As verificações executadas passaram. Isso demonstra preservação e aplicação do contrato escolhido para esta extração; não substitui confirmação externa das convenções nem valida as demais entidades. Os marcadores em memória registram o andamento da sessão e não são, isoladamente, evidência durável de auditoria.

**Correção posterior — issue #27.** Foi acrescentada a regra `pagamento_nao_interpretado`: pagamento tipado nulo sem motivo de ausência reconhecido bloqueia a candidata. Nulo original e sentinela continuam com seus motivos; formato desconhecido, vazio e calendário inválido não podem passar como ausência legítima. Os outputs preservados são anteriores a essa inclusão. Para conferir a correção nos dados, execute somente as células da Seção 10 com a candidata e os diagnósticos disponíveis na sessão; não é necessário Run All nem republicar tabelas.

## 11. Inspeção dos destinos antes da migração

**Objetivo.** Conhecer a tabela existente e tornar explícita a alteração de contrato antes de substituí-la.

**Situação inicial registrada.** `silver.tb_faturas` era Delta, versão 0, com 2.184.621 faturas. Os nomes das duas tabelas de revisão estavam disponíveis. A comparação mostrou mudanças de schema, incluindo método de interpretação, versões de origem e referência com leituras, além da retirada das candidatas MDY/DMY e do alerta estatístico antigo da saída final.

**Decisão.** Conferir primeiro duas tabelas de revisão: uma com cadastro e outra com pendências. A comparação de schemas descreve a mudança, mas não prova igualdade de conteúdo. Esta seção é um registro da preparação da migração inicial, não uma necessidade de criar tabelas de revisão em toda carga futura.

## 12. Conferência das tabelas de revisão já persistidas

**Objetivo.** Verificar se a persistência intermediária corresponde integralmente aos DataFrames validados.

**Resultado observado.** `silver.tb_faturas_revisao_v1` e `silver.tb_faturas_pendentes_cadastro_revisao_v1`, ambas na versão 0, tiveram schema e conteúdo completo conferidos. A primeira contém 2.152.336 faturas e R$ 666.482.773,76; a segunda contém 32.285 e R$ 10.192.373,82.

**Decisão operacional.** Como as tabelas já existiam, as células atuais desta seção apenas as leem e conferem. As tentativas anteriores de recriação foram interrompidas; o alias `errorifexists` também não foi aceito nessa implementação Spark Connect. A retomada ocorreu sem apagar ou sobrescrever as revisões. Esta seção registra uma conferência histórica, não a rotina de criação para cada nova extração.

## 13. Publicação definitiva e conferência dos destinos

**Objetivo.** Publicar a separação aprovada e conferir o resultado efetivamente armazenado nos destinos finais.

**Execução registrada.** A publicação usou a versão 0 das tabelas de revisão já conferidas. Primeiro foi criada `silver.tb_faturas_pendentes_cadastro`, versão 0, com 32.285 faturas e R$ 10.192.373,82. Depois, `silver.tb_faturas` foi substituída, passando da versão 0 para a 1, com 2.152.336 faturas e R$ 666.482.773,76. Os schemas e conteúdos completos dos dois destinos corresponderam às referências.

**Proteção posterior — issue #28.** O plano exige que a versão 0 das duas revisões tenha sido efetivamente conferida na Seção 12. Faltas ou divergências bloqueiam a preparação e são verificadas novamente antes da escrita. A preparação reutiliza o snapshot conferido como referência. O caminho válido foi conferido em uma preparação somente leitura no Databricks; onze cenários de publicação foram testados separadamente com catálogo e escritas simulados em memória. Os outputs de publicação preservam a execução histórica e não representam nova gravação após a correção. Para conferir a preparação, execute A e B da Seção 12 e apenas a primeira célula da Seção 13, com as dependências disponíveis na sessão; não use Run All nem execute a célula de gravação para essa conferência.

**Conclusão e limite operacional.** Permaneceram preservadas 2.184.621 faturas e R$ 676.675.147,58 entre as duas saídas. Cada gravação Delta é atômica por tabela; as duas juntas não formam uma transação. Esta seção é a migração inicial baseada em revisões fixas: não deve ser apresentada como rotina de atualização automática a partir de novas versões Bronze. O notebook é mantido completo para documentar o processo e suas decisões.
