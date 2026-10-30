# Textos para apresentação do notebook de faturas

**Evidência de execução:** [bronze-to-silver-faturas-evidencia-2026-10-29.ipynb](../../data-engineering/bronze-to-silver-faturas-evidencia-2026-10-29.ipynb), anexo com código e outputs históricos preservados, com publicação concluída em 29/10/2026.

**Versão operacional:** [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb), cópia sem outputs e com revisões em `silver_revisoes`; ainda não executada no Databricks.

**Objetivo deste arquivo:** apoiar a apresentação das etapas e dos resultados. Os números pertencem à extração auditada, sem impor contagens fixas a futuras cargas.

**Execução:** a leitura deste documento não exige reexecutar o notebook. Antes de uma execução, confira os destinos e o parâmetro: `true` permite gravar revisões e substituir as duas tabelas finais de `v-energy.silver`. O padrão para uma nova configuração é `false`, e um widget existente pode conservar `true`.

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

**Resultado observado.** O diagnóstico contou 32.285 IDs `FTX`, fora do contrato da principal e preservados nas pendências. A principal passou na validação `^FT[0-9]{9}$`. O cadastro Bronze versão 0 contém 46.461 linhas e apresenta IDs repetidos, sem espaços nas extremidades. Há 201 valores cadastrais fora do padrão, incluindo a string `id_uc`. Encontramos 2.152.336 faturas com cadastro, em 45.000 UCs, e 32.285 sem cadastro, em 31.705 UCs. As 42 faturas dos pares UC/mês repetidos estão integralmente no grupo sem cadastro.

**Decisão.** Cruzar com chaves distintas para não multiplicar valores financeiros. Isso não escolhe atributos cadastrais conflitantes nem conclui a Silver do cadastro. Separar as faturas sem referência em uma saída de pendências, com preservação e reconciliação; não inferir fraude nem excluir pelo prefixo do ID. Os R$ 20.341,61 dos pares repetidos já estão incluídos nos R$ 10.192.373,82 sem cadastro e não devem ser contados novamente.

## 8. Correspondência com leituras

**Objetivo.** Investigar a presença do par UC/competência em medição e sua relação com a ausência cadastral. O cruzamento utiliza somente chaves, sem incorporar consumo ainda não tratado.

**Resultado observado.** A Bronze de leituras versão 0 contém 2.182.468 registros, sem cabeçalhos internos completos e sem chaves ausentes ou fora dos padrões testados. São 2.152.336 pares UC/mês; 30.061 têm mais de uma leitura, chegando a três. Todas as 2.152.336 faturas com cadastro encontram o par em leituras. As 32.285 sem cadastro também não encontram esse par. O cruzamento manteve as 2.184.621 faturas.

**Decisão.** Usar uma linha por par de referência, evitando multiplicação das faturas. Manter um indicador de ausência de leitura. A existência do par não homologa o consumo, e sua ausência não foi transformada em regra universal de exclusão. O tratamento da Silver de leituras permanece fora deste notebook.

## 9. Construção da candidata Silver em memória

**Objetivo.** Aplicar as decisões fundamentadas na exploração e produzir uma representação tipada sem perder o conteúdo de origem.

**Implementação.** A candidata é persistida e materializada antes das ações repetidas. Diagnóstico e tipagem compartilham as funções de interpretação de datas. Datas são convertidas para `DATE`; energia, tributos e total para `DECIMAL(18,2)`. As onze colunas brutas ficam no `STRUCT dados_originais`. São preservados arquivo e timestamp de ingestão e registradas as versões Bronze de faturas, cadastro e leituras. O método de interpretação da emissão e o motivo de ausência de pagamento ficam explícitos.

**Resultado observado.** A candidata tem 25 colunas de primeiro nível. Preserva as 2.184.621 faturas e sinaliza ambiguidade original, emissão fora da competência, atraso, ausência cadastral, ausência de leitura e multiplicidade UC/mês. A separação produz 2.152.336 faturas com cadastro e 32.285 pendentes. A escolha de uma data por convenção não apaga a ambiguidade original.

## 10. Validação da candidata e conservação dos dados

**Objetivo.** Verificar a aplicação das regras e a conservação dos registros antes de qualquer publicação definitiva.

**Verificações executadas.** Tipos, unicidade e formato de chaves, obrigatoriedade, domínios, cronologia da data escolhida, coerência entre status e pagamento e conciliação monetária. Os originais e metadados recuperados da candidata foram comparados à Bronze de negócio com `exceptAll` nas duas direções. Os valores tipados foram comparados aos diagnósticos anteriores; as duas saídas foram reunidas e comparadas integralmente à candidata, sem sobreposição de IDs. Quantidades e somas também foram reconciliadas por competência e status.

**Resultado observado.** As verificações executadas passaram. Isso demonstra preservação e aplicação do contrato escolhido para esta extração; não substitui confirmação externa das convenções nem valida as demais entidades. Os marcadores em memória registram o andamento da sessão e não são, isoladamente, evidência durável de auditoria.

**Bloqueio de pagamentos — issue #27.** A regra `pagamento_nao_interpretado` bloqueia pagamento tipado nulo sem motivo reconhecido. Nulo original e sentinela continuam com seus motivos. A execução de 29/10/2026 inclui essa regra e registrou aprovação das validações antes da publicação.

## 11. Inspeção dos destinos definitivos

**Objetivo.** Identificar os destinos existentes e comparar seus nomes e tipos
de colunas com a candidata, antes de preparar a escrita. A inspeção não substitui
a comparação posterior dos dados publicados.

**Resultado observado.** Os dois destinos já existiam e tinham contratos
compatíveis. A seção fez somente consultas.

## 12. Revisões da execução e conferência da persistência

**Objetivo.** Criar revisões exclusivas da candidata atual e conferir integralmente
o que foi salvo. Com `false`, a seção ignora a escrita; com `true`, cria as revisões.

**Resultado observado em 29/10/2026.** As revisões com sufixo
`1bb6358d020a4ca1b1148d09c87c2fc7` foram criadas em `v-energy.silver`, ambas na
versão 0. Schemas e conteúdos completos corresponderam aos DataFrames esperados,
incluindo originais e metadados. São 2.152.336 faturas com cadastro e 32.285 pendentes.

**Versão operacional.** A cópia separada grava novas revisões em
`v-energy.silver_revisoes`; seus outputs estão vazios porque essa configuração
ainda não foi executada no Databricks. O anexo comprovado mantém o código e os outputs históricos.

## 13. Publicação definitiva e conferência dos destinos

**Objetivo.** Publicar exatamente os snapshots conferidos e verificar os resultados
nas versões Delta registradas pela escrita. O plano não exige que a fonte seja
sempre a versão 0: exige correspondência com o registro de conferência.

**Execução registrada.** O Run All com `true`, em 29/10/2026, terminou sem erros.
As pendências foram publicadas na versão 1, com 32.285 faturas e
R$ 10.192.373,82; a principal foi publicada na versão 2, com 2.152.336 faturas e
R$ 666.482.773,76. Schemas e conteúdos completos dos destinos corresponderam
às revisões conferidas.

**Conclusão e limite operacional.** Foram preservadas 2.184.621 faturas e
R$ 676.675.147,58 entre as duas saídas. A última célula registrou
`OK: publicação definitiva concluída e conferida.`. Cada gravação é uma
transação Delta separada; esse sucesso não transforma as duas escritas em
uma transação conjunta nem comprova a execução da Gold.

O [guia de operação](../auditoria_dados/operacao_faturas.md) explica os dois
notebooks, os destinos e a organização das revisões.
