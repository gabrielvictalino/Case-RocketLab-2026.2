# Dicionário da Gold de faturas — GOLD_FATURAS_V2

Escopo: faturamento e situação das contas, conforme as seções 3.2, 4.1, 4.2 e
5.2 do case. A modelagem da Gold é decisão do time. A implementação não muda os
tratamentos Silver nem implementa DEC/FEC, GD, inspeções ou atendimento.

[Índice do dicionário da Gold](decisoes_silver_to_gold.md).

## Fontes e decisões

| Fonte padrão | Uso |
| --- | --- |
| `v-energy.silver.tb_faturas` | Faturas com referência cadastral na Silver de faturas |
| `v-energy.silver.tb_faturas_pendentes_cadastro` | Faturas preservadas fora da receita |
| `v-energy.silver.tb_unidades_consumidoras` | Uma linha por UC; município, bairro e classe |
| `v-energy.silver.tb_leituras` | Uma leitura por UC e competência; consumo e flags Silver |

Os padrões seguem a convenção de catálogo `v-energy`, schema `silver` e prefixo
`tb_`. As Silvers de cadastro e leituras precisam ser publicadas nesses destinos
antes da execução com os padrões. Nos ambientes que ainda usam
`workspace.default.silver_unidades_consumidoras` ou `venergy.silver.leituras`,
informe esses nomes nos parâmetros. Todas as referências são configuráveis.
O notebook consome o marcador Silver e registra suas revisões e identidades nos metadados.
Os nomes na tabela acima são destinos lógicos; a leitura financeira usa as revisões do marcador.
Não lê Bronze nem CSV bruto.

- Competência é `mes_referencia`, convertida para o primeiro dia do mês. Receita
  pertence à competência, mesmo quando a emissão ou o pagamento ocorrer em outro mês.
- Receita significa o valor nominal faturado, incluindo tributos. `valor_energia`
  e `tributos` também são preservados separadamente. Pagamento não reduz receita.
- Fatura `PAGA` tem valor nominal pago igual ao total; isso não comprova caixa,
  juros, descontos ou pagamentos parciais. Não chamamos essa soma de arrecadação efetiva.
- A data de referência é explícita e deve representar o retrato de status recebido.
  Emissões ou pagamentos posteriores a ela bloqueiam a carga. Não reconstruímos
  o contas a receber histórico com o status atual. Vencimentos futuros são aceitos.
- `9999-12-31` já deve ter virado NULL na Silver. PAGA sem pagamento, EM ABERTO
  com pagamento, status/bandeira desconhecidos, valores nulos ou negativos,
  total diferente de energia + tributos e datas contraditórias bloqueiam a Gold.
  Zero monetário é admitido se houver conciliação; a Silver atual pode ter regra mais restrita.
- Duplicação de `id_fatura`, de UC no cadastro ou de UC/competência nas leituras
  bloqueia a execução. Não há `dropDuplicates`, escolha arbitrária de linha ou JOIN
  que multiplique o valor faturado.
- Pendência cadastral da Silver permanece segregada. Uma UC considerada válida
  pela Silver de faturas mas ausente no cadastro Silver também é segregada.
  Faturas múltiplas de uma UC no mesmo mês, ainda sem semântica de reemissão/ajuste,
  são preservadas nas exclusões; não somam receita definitiva nem duplicam volume.
- O cadastro disponibilizado é um retrato, sem histórico de mudança de bairro ou
  classe. Os recortes históricos usam esses atributos atuais, sem inventar uma SCD.
- Leituras faltantes ou negativas não eliminam receita. Não usamos `abs()`, o proxy
  auxiliar não estima consumo de troca e não substitui consumo desconhecido por zero.
  O consumo analítico contratual é uma coluna separada, estimada pela mediana documentada abaixo.
  As três flags booleanas de troca, ausência de leitura anterior e sinal não
  confirmado são obrigatórias; sua ausência ou tipo inválido bloqueia a carga.
  Flags de troca, ausência de leitura anterior ou sinal não confirmado impedem o uso
  do consumo. Uma flag existente mas nula também impede o uso. Uma correção de sinal
  já confirmada pela Silver pode ser utilizada.
- O preço médio efetivo é calculado a partir da conta e de uma leitura utilizável;
  não é tarifa homologada. O arquivo de faturas não contém kWh faturado, tarifa base,
  valor isolado da bandeira ou abatimento de GD. `volume_analise_kwh` é um **proxy de
  consumo medido**, nunca um kWh faturado homologado. Não aplicamos o reajuste de
  10,5% a toda a base nem inventamos parcelas de bandeira ou geração solar.

## `tb_faturas`

Grão/chave: **uma fatura / `id_fatura`**. Somente faturas elegíveis à receita.
UC e competência também são únicas após a segregação de multiplicidade. A tabela
serve à lista de contas em aberto e às consultas financeiras da visão 360.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_fatura`, `id_uc` | string | Chaves preservadas da Silver; sem inferência por prefixo FT/FTX |
| `mes_referencia` | string AAAA-MM | Competência original padronizada |
| `competencia` | date | Primeiro dia do mês de referência |
| `municipio`, `bairro`, `classe` | string | Atributos não vazios do cadastro Silver |
| `data_emissao`, `data_vencimento` | date | Datas tipadas pela Silver |
| `data_pagamento` | date, anulável | Data real de pagamento; NULL em conta aberta |
| `valor_energia`, `tributos`, `valor_total` | decimal(18,2), R$ | Valores nominais; total = energia + tributos |
| `bandeira_tarifaria` | string | Verde, Amarela, Vermelha P1 ou Vermelha P2 |
| `status` | string | PAGA ou EM ABERTO |
| `flag_uc_sem_cadastro` | boolean | Indicador herdado; sempre false no detalhe elegível |
| `quantidade_faturas_uc_mes` | long | Contagem antes da segregação; sempre 1 no detalhe elegível |
| `consumo_kwh_silver` | inteiro/decimal, anulável | Valor da leitura, inclusive negativo, para auditoria |
| `volume_analise_kwh` | decimal(18,2), kWh, anulável | Consumo não negativo e sem flags impeditivas; NULL se desconhecido/inutilizável |
| `situacao_volume` | string | SEM_LEITURA, LEITURA_NAO_UTILIZAVEL, ZERO_KWH ou VOLUME_POSITIVO |
| `preco_efetivo_total_rs_kwh` | decimal(28,10), R$/kWh, anulável | Total / volume, somente com volume positivo |
| `valor_fatura_paga` | decimal(18,2), R$ | Total se PAGA; zero se EM ABERTO |
| `valor_em_aberto` | decimal(18,2), R$ | Total se EM ABERTO; zero se PAGA |
| `dias_atraso` | int, dias | Em aberto: max(referência − vencimento, 0); paga: max(pagamento − vencimento, 0) |
| `flag_vencida_em_aberto` | boolean | EM ABERTO e vencimento estritamente anterior à referência |
| `data_referencia` | date | Data informada para o retrato de status; constante por execução |
| `versao_regras_gold` | string | GOLD_FATURAS_V2 |

Quando presentes na Silver, também preservamos sem alteração `source_file`,
`ingestion_datetime`, `metodo_interpretacao_emissao`, `flag_emissao_original_ambigua`,
`flag_emissao_fora_competencia` e `versao_regras`. Não resolvemos novamente datas
ambíguas na Gold. A convenção de emissão continua auditável com esses campos e
com a versão Delta de origem.

## `tb_faturas_excluidas`

Grão/chave: **uma fatura segregada / `id_fatura`**. Não alimenta KPIs de receita.
Contém as colunas de fatura, competência, recortes cadastrais quando disponíveis,
quantidade de faturas UC/mês, auditoria, data de referência e versão de regras.
Não possui as métricas derivadas do cruzamento com leituras.

`motivo_exclusao` segue esta precedência:

| Motivo | Regra |
| --- | --- |
| PENDENTE_CADASTRO_SILVER | `flag_uc_sem_cadastro = true` na Silver |
| UC_AUSENTE_CADASTRO_SILVER | Nenhuma correspondência no cadastro Silver informado |
| MULTIPLAS_FATURAS_UC_MES | Mais de um ID de fatura na mesma UC/competência |
| FATURA_SEM_LEITURA | Fatura elegível nas regras anteriores, mas sem leitura da UC na competência; segregada pelo adaptador comercial |

Detalhe + exclusões reproduzem integralmente os campos de negócio e a multiplicidade
da entrada. Um prefixo FTX não é critério de exclusão. Os totais publicados devem
ser reconciliados com os registros aceitos e com os segregados.

## `tb_faturamento_mensal`

Grão/chave: **competência × município × bairro × classe × data de referência**.
`data_referencia` é única por carga, não uma dimensão adicional de histórico.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `competencia`, `municipio`, `bairro`, `classe`, `data_referencia` | conforme detalhe | Chaves do agregado |
| `quantidade_faturas` | long | Número de contas elegíveis |
| `quantidade_ucs_faturadas` | long | UCs distintas do grupo; não equivale a toda UC ativa |
| `valor_energia`, `tributos`, `valor_total` | decimal(28,2), R$ | Soma exata do detalhe, sem float |
| `valor_faturas_pagas`, `valor_em_aberto` | decimal(28,2), R$ | Somas por situação; juntas fecham com o total |
| `quantidade_em_aberto`, `quantidade_vencidas` | long | Contagem por status e vencimento na referência |
| `valor_vencido` | decimal(28,2), R$ | Soma somente de contas vencidas e abertas |
| `quantidade_com_volume_positivo` | long | Contas com consumo utilizável > 0 |
| `quantidade_sem_volume` | long | Contas com consumo desconhecido/inutilizável; zero medido não entra aqui |
| `volume_analise_kwh` | decimal(28,2), kWh | Soma da parcela utilizável; zero se nenhuma leitura utilizável |
| `receita_com_volume_positivo` | decimal(28,2), R$ | Total das contas com volume positivo utilizável |
| `receita_sem_volume_positivo` | decimal(28,2), R$ | Total das demais, inclusive zero medido; fecha com a receita pareada |
| `cobertura_volume_pct` | decimal(5,2), % | 100 × contas com volume positivo / contas elegíveis, duas casas |
| `versao_regras_gold` | string | GOLD_FATURAS_V2 |

Para recortes de bandeira ou status, consulte `tb_faturas`. Para vários meses,
some valores/contagens; recalcule percentuais a partir das somas. Não some UCs
mensais para obter UCs distintas do período nem tire média simples de tarifas.

### Fórmulas das métricas auxiliares

No grão de `tb_faturamento_mensal`, `COUNT_IF(p)` significa contar as linhas que
satisfazem `p`. `SUM` ignora nulos; as somas monetárias e de volume do agregado
viram zero quando não há parcela válida. Isso não altera o nulo no detalhe.

| Métrica | Fórmula / regra | Limpeza que afeta o resultado |
| --- | --- | --- |
| `quantidade_faturas`, `quantidade_ucs_faturadas` | `COUNT(*)`, `COUNT(DISTINCT id_uc)` do detalhe elegível | Cadastro válido, segregação de multiplicidade e de faturas sem leitura |
| `valor_energia`, `tributos`, `valor_total` | `SUM` da respectiva coluna do detalhe; por fatura, `valor_total = valor_energia + tributos` | Valores decimais e reconciliação Silver; exclusões não compõem receita |
| `valor_faturas_pagas`, `valor_em_aberto` | `SUM(valor_total)` onde `status = PAGA` e `EM ABERTO`, respectivamente; zero no outro status | Sentinela de pagamento nula e status consistente; referência explícita |
| `quantidade_em_aberto`, `quantidade_vencidas` | `COUNT_IF(status = EM ABERTO)`; `COUNT_IF(flag_vencida_em_aberto)` | Vencida exige conta aberta e `data_vencimento < data_referencia`; vencer na referência não conta |
| `valor_vencido` | `SUM(valor_total)` somente nas vencidas em aberto | Mesma regra de vencimento; não inclui conta já paga com atraso |
| `dias_atraso` (detalhe) | Aberta: `max(datediff(data_referencia, data_vencimento), 0)`; paga: `max(datediff(data_pagamento, data_vencimento), 0)` | Datas interpretadas na Silver; não mede atraso histórico de uma conta hoje aberta |
| `volume_analise_kwh` | Detalhe: leitura não negativa e sem flags impeditivas; agregado: `SUM(volume_analise_kwh)` | Troca, ausência de anterior ou sinal não confirmado anulam o proxy; não há imputação nesta métrica |
| `preco_efetivo_total_rs_kwh` (detalhe) | `valor_total / volume_analise_kwh`, somente se volume > 0; senão nulo | Mesmas flags; inclui tributos e não é tarifa base |
| `quantidade_com_volume_positivo`, `quantidade_sem_volume` | `COUNT_IF(volume_analise_kwh > 0)`; `COUNT_IF(volume_analise_kwh IS NULL)` | Zero medido não é desconhecido nem volume positivo |
| `receita_com_volume_positivo`, `receita_sem_volume_positivo` | `SUM(valor_total)` com volume utilizável > 0 e nas demais contas, respectivamente | A segunda inclui zero medido e volume nulo; as parcelas fecham com `valor_total` |
| `cobertura_volume_pct` | `round(100 × quantidade_com_volume_positivo / quantidade_faturas, 2)` | Mede cobertura de contas com volume positivo, não a participação de consumo imputado; agregado só existe com faturas |

Para preço efetivo agregado, use `SUM(receita_com_volume_positivo) /
SUM(volume_analise_kwh)` quando o denominador for positivo. Esse cálculo pareia
receita com o volume observado e não inclui a receita sem volume positivo.

## Decomposição da receita

A Gold não publica `tb_variacao_receita` nem uma decomposição auxiliar baseada
apenas no volume observado. A decomposição canônica segue a R5 de
[`contracts/README.md`](../../contracts/README.md), com quatro efeitos sobre o
consumo analítico associado às faturas, calculados pelo consumidor a partir de
`receita_volume_mensal`. O notebook exibe resumos de faturamento e exclusões;
a validação da carga não exige dois anos de histórico para uma comparação anual.

## Integração comercial — contrato 0.3.0-provisional (#101)

As seções `tb_*` acima descrevem **saídas auxiliares lógicas**, mantidas para
reconciliação e investigação. O marcador Gold aponta para as tabelas físicas de
cada revisão; consultar nomes fixos legados não acompanha esta publicação.
As saídas comerciais são `uc_consumo_faturamento_mensal` e
`receita_volume_mensal`, com colunas, ordem, tipos e escalas carregados dos YAMLs
em `contracts/tabelas/`. O adaptador fica em
[`gold_contrato_faturas.py`](../../data-engineering/silver_to_gold/gold_contrato_faturas.py).
Acrescenta o gate de volume igual ao analítico no importador; auxiliares não substituem o contrato.

### Dicionário de `uc_consumo_faturamento_mensal` (contrato)

**Grão/chave:** `id_uc × competencia`, nas leituras das UCs presentes no cadastro.
Tipos e ordem vêm do [YAML](../../contracts/tabelas/uc_consumo_faturamento_mensal.yaml).
As regras de limpeza e de estimativa são detalhadas em R2 e na decisão da #67 abaixo.

| Coluna | Tipo / unidade | Nulo? | Definição / fórmula |
| --- | --- | :---: | --- |
| `id_uc` | string | não | UC da leitura, presente no cadastro |
| `competencia` | date | não | Primeiro dia do mês de `mes_referencia` |
| `consumo_kwh_original` | decimal(18,2), kWh | não | `consumo_kwh` da Silver, após suas correções de sinal, inclusive negativos preservados |
| `consumo_kwh_analitico` | decimal(18,2), kWh | não | `coalesce(leitura_utilizavel, mediana_fase_kwh, mediana_historica_kwh)`; sem doadores, carga bloqueada |
| `metodo_consumo` | string | não | `LEITURA_UTILIZAVEL`, `MEDIANA_FASE_UC` ou `MEDIANA_HISTORICA_UC`, conforme a primeira parcela disponível acima |
| `tipo_leitura` | string | não | `REAL` ou `ESTIMADA`, preservado da Silver; leitura estimada na origem continua identificada mesmo com método `LEITURA_UTILIZAVEL` |
| `flag_troca_medidor` | boolean | não | Flag Silver ou evidência cadastral de troca no mês da retirada do anterior |
| `id_fatura` | string | sim | ID da fatura elegível; nulo se ausente ou se todas as faturas da UC/mês foram segregadas |
| `volume_faturado_kwh` | decimal(18,2), kWh | não | `consumo_kwh_analitico` com fatura elegível; zero sem fatura |
| `valor_total` | decimal(18,2), R$ | não | Total nominal da fatura elegível; zero sem fatura |
| `valor_arrecadado` | decimal(18,2), R$ | não | `valor_total` se `PAGA`; zero se `ABERTA` ou sem fatura; convenção por status, não medição independente de caixa |
| `tarifa_base` | decimal(18,6), R$/kWh | sim | Mediana exata (`percentile(..., 0.5)`) da tarifa líquida não negativa por subgrupo × competência, convertida para seis casas; ou complemento explícito validado |
| `adicional_bandeira` | decimal(18,6), R$/kWh | sim | Adicional fixo do case por bandeira, ou complemento explícito validado |
| `bandeira` | string | sim | Normalização para `VERDE`, `AMARELA`, `VERMELHA_P1`, `VERMELHA_P2` |
| `status_pagamento` | string | sim | `PAGA` ou `ABERTA` (`EM ABERTO` na Silver) |
| `data_vencimento` | date | sim | Vencimento da fatura elegível |
| `grupo_uc` | string | não | `GD`, `IRREGULARIDADE_CONFIRMADA` ou `DEMAIS`, pela precedência temporal R3 |

Sem fatura, as cinco colunas tarifárias/de cobrança anuláveis (`tarifa_base`,
`adicional_bandeira`, `bandeira`, `status_pagamento`, `data_vencimento`) ficam
nulas juntas. Original, analítico, método, tipo de leitura e grupo permanecem.

### Dicionário de `receita_volume_mensal` (contrato)

**Grão/chave:** `competencia × municipio × bairro × classe × grupo_uc`. O
agregado junta o detalhe contratual ao cadastro por `id_uc`, com atributos
atuais, e segue o [YAML](../../contracts/tabelas/receita_volume_mensal.yaml).
Todas as colunas são obrigatórias. As exclusões de faturas, a imputação de
consumo, o grupo temporal e a derivação da tarifa afetam as somas abaixo.

| Coluna | Tipo / unidade | Definição / fórmula no grão |
| --- | --- | --- |
| `competencia` | date | Primeiro dia do mês |
| `municipio`, `bairro`, `classe` | string | Recortes da Silver de cadastro, coerentes com `dim_uc` |
| `grupo_uc` | string | Grupo temporal do detalhe; não usa as flags atuais do cadastro para todo o histórico |
| `volume_faturado_kwh` | decimal(18,2), kWh | `SUM(detalhe.volume_faturado_kwh)` |
| `receita` | decimal(18,2), R$ | `SUM(detalhe.valor_total)`, com tributos |
| `receita_arrecadada` | decimal(18,2), R$ | `SUM(detalhe.valor_arrecadado)`, sob a mesma convenção por status |
| `componente_tarifa_reais` | decimal(18,2), R$ | `round(SUM(volume_faturado_kwh × coalesce(tarifa_base, 0)), 2)` |
| `componente_bandeira_reais` | decimal(18,2), R$ | `round(SUM(volume_faturado_kwh × coalesce(adicional_bandeira, 0)), 2)` |

Os produtos são somados antes de arredondar, com meio afastando de zero. Os
componentes não precisam fechar com a receita nominal: tributos e composição
são tratados pelo fator e pelo resíduo da R5. Para vários meses ou recortes,
some os valores e recalcule razões; não use média simples de preços.

### Auxiliares de proveniência e cobertura

As três saídas abaixo são publicadas como revisões físicas no mesmo conjunto
das tabelas comerciais. Não fazem parte das 12 tabelas do portal.

| Saída lógica | Grão | Campos / fórmulas auditáveis |
| --- | --- | --- |
| `consumo_proveniencia` | UC × competência | Campos da leitura e flags, `consumo_kwh_original`, `consumo_kwh_analitico`, `metodo_consumo`, `fase_gd`, `data_conexao`, `primeira_inspecao_irregular`, `grupo_uc`; `mediana_fase_kwh = percentile_approx(leitura_utilizavel, 0.5)` por UC/fase, `mediana_historica_kwh` por UC; `doadores_fase` e `doadores_historico` contam leituras utilizáveis nas respectivas janelas |
| `complemento_proveniencia` | fatura elegível | Quando derivado: `id_fatura`, `competencia`, `subgrupo_tarifario`, `tarifa_base`, `adicional_bandeira`, `proveniencia`; `doadores_tarifa` conta tarifas líquidas ≥ 0, `doadores_tarifa_negativa_excluidos` conta as < 0, por subgrupo/mês, somente em faturas com método `LEITURA_UTILIZAVEL` e consumo > 0. Complemento explícito exige ID, tarifas e proveniência, e pode não trazer as contagens |
| `cobertura_volume` | competência × município × bairro × classe × grupo_uc × metodo_consumo × tipo_leitura | Somente linhas com fatura: `quantidade_faturas = COUNT(*)`, `volume_faturado_kwh = SUM(volume_faturado_kwh)`, `receita = SUM(valor_total)` |

Contagens de doadores de tarifa repetem-se em cada fatura do grupo/mês: use uma
linha distinta por subgrupo/competência ao auditá-las. Para medir a participação
de volume imputado, divida a soma de `volume_faturado_kwh` dos métodos de mediana
pelo volume total em `cobertura_volume` e multiplique por 100; com volume total
zero, o percentual é indefinido. Para distinguir medição real de estimativa na
origem, preserve também o recorte `tipo_leitura`. Isso é diferente da cobertura
de contas com volume positivo da auxiliar `tb_faturamento_mensal`.

### R2: consumo e faturamento

A série começa nas leituras das UCs presentes no cadastro. Não gera meses sem
leitura com consumo original inventado. Uma fatura sem leitura é segregada em `faturas_excluidas` com motivo
`FATURA_SEM_LEITURA`; não se fabrica uma leitura nem uma competência comercial.
Leituras sem cadastro não viram UCs fictícias; faturas correspondentes continuam
segregadas e reconciliadas nas auxiliares.

- `consumo_kwh_original` preserva `consumo_kwh` **da Silver**, inclusive negativos.
  A Silver já normalizou formatos e corrigiu sinais comprovados. Este campo não
  reconstrói o valor bruto anterior à Silver; o snapshot e as flags preservam essa
  proveniência. É a mesma referência adotada pela Gold GD. A aceitação de negócio
  dessa interpretação de “original” deve constar da homologação com o time de dados.
- `consumo_kwh_analitico` usa a leitura não negativa sem flags impeditivas, com
  `LEITURA_UTILIZAVEL` e igualdade exata com o original. Quando bloqueada, usa
  `percentile_approx(..., 0.5)` da própria UC na mesma fase da GD
  (`MEDIANA_FASE_UC`); sem doadores na fase, usa o histórico utilizável da UC
  (`MEDIANA_HISTORICA_UC`). Esta é a convenção implementada na Gold GD, não o
  algoritmo do gerador sintético. Sem doadores em toda a UC, a carga é recusada:
  o contrato não admite `INDISPONIVEL` nem analítico nulo.
- A fase muda no mês de conexão. Uma UC sem GD tem a fase `SEM_GD`; UCs com GD usam `ANTES_CONEXAO` e
  `APOS_CONEXAO`. A mediana
  usa o histórico do snapshot inteiro, inclusive meses posteriores à competência:
  é uma estimativa retrospectiva para este estudo, não previsão disponível naquele mês.
- `consumo_proveniencia` é uma auxiliar por UC × competência: guarda método,
  medianas, contagens de doadores, fase, datas de conexão/primeira inspeção e dados
  da leitura. Os metadados da execução guardam fontes e versões Delta.
- Flags nulas continuam impedindo o uso do proxy auxiliar; na saída contratual,
  uma flag desconhecida bloqueia a carga, pois não é um booleano comprovado.
- Competência sem fatura e competência com múltiplas faturas seguem as nulidades
  e zeros de R2, com consumo preservado. Todas as múltiplas ficam nas exclusões.
  `data_vencimento` é preservada; bandeira e pagamento são normalizados para os
  enums dos YAMLs.
- `PAGA` gera `valor_arrecadado = valor_total`; `ABERTA` gera zero, conforme R2.
  **O contrato descreve arrecadação efetiva, mas a fonte fornece status e valor
  nominal. Esta implementação aplica a convenção provisória, sem comprovação
  independente de caixa, descontos, juros ou pagamentos parciais.**

## Decisão de dados — comentário 6587742059 da #67

Implementa a [decisão de 02/11/2026](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/pull/67#issuecomment-6587742059).
O nome e o layout `0.3.0-provisional` são mantidos; as descrições provisórias são
alinhadas ao significado aprovado para o case. Isso não aprova os demais domínios.

- `volume_faturado_kwh` é o consumo analítico associado à fatura elegível, incluindo
  estimativas. Não comprova volume do sistema comercial. Sem fatura, continua zero.
- Original é o valor da Silver, após correções comprovadas de sinal. Leitura utilizável
  mantém o valor; leituras bloqueadas usam mediana da própria UC por fase da GD,
  com fallback histórico. Sem doador, a exportação falha com a contagem no erro.
- O snapshot de `v-energy.silver.tb_medidores` fornece o mês de retirada, equivalente
  a `competencia_troca` da #105. Esse mês também marca troca quando a leitura só
  indica ausência de anterior; não se usa o mês de instalação do medidor seguinte.
- Faturas sem leitura são segregadas com `FATURA_SEM_LEITURA`, como as pendências
  cadastrais; detalhe + exclusões continuam reconciliando integralmente a fonte.
  Problema na medição não exclui uma fatura válida que possui leitura estimável.
- Tarifa base é derivada por subgrupo tarifário × competência: mediana de
  `valor_energia / consumo utilizável positivo - adicional_bandeira`, nas faturas
  elegíveis. Tarifas líquidas negativas não doam e são contadas na proveniência,
  sem excluir as faturas. Subtrair a bandeira evita contá-la duas vezes na R5.
  A mediana é arredondada para seis casas; não é tarifa homologada. Sem doador de
  tarifa no grupo/mês, a carga falha com contagem; não há fallback entre classes.
- Adicionais fixos: Verde 0; Amarela 0,01885; Vermelha P1 0,04463; Vermelha P2
  0,07877 R$/kWh. São característica dos dados do case em todo o período e não
  representam o histórico regulatório da ANEEL.
- `complemento_proveniencia` guarda a regra, subgrupo e contagem de doadores por
  fatura. `consumo_proveniencia` guarda original, método, medianas e doadores.
  `cobertura_volume` discrimina quantidade, volume e receita por método e tipo de
  leitura, no grão comercial: permite somar observado/estimado e calcular a cobertura.
  `LEITURA_UTILIZAVEL` com tipo `ESTIMADA` continua distinguível de leitura `REAL`.
- O complemento é derivado quando o widget está vazio. Um complemento explícito
  fornece somente tarifas e proveniência; o volume é sempre derivado do analítico. O importador
  também verifica essa igualdade para toda linha com fatura.
- Os componentes da R5 somam produtos decimais antes de arredondar por grão.
  Não se fixa `k₀ = 4/3`: resíduos e composição podem mudar o fator e o mix.
  Volume implícito pela conta não substitui o volume canônico.

A homologação no Databricks, disponibilidade/coerência das fontes (incluindo
inspeções), referência oficial e lote completo de 12 tabelas seguem necessárias.

### R3: grupo temporal

O adaptador exige snapshots de `tb_geracao_distribuida` (`id_uc`, `data_conexao`)
e de inspeções (`id_uc`, `data`, `resultado`). O padrão de inspeções é
`v-energy.silver.tb_inspecoes`, padronizada pelo PR #116, cujo produtor é
`data-engineering/bronze_to_silver/bronze-to-silver-inspecoes.ipynb`. Confirme a
publicação da nova Silver no workspace antes de executar a Gold. A Gold não cria
nem publica essas fontes. A precedência é GD desde o mês da conexão; senão, irregularidade
confirmada desde o mês da primeira inspeção com esse resultado; senão, demais.
Flags cadastrais atuais não são projetadas para trás.

O lote de 12 tabelas deve conter **os mesmos dados de GD e inspeções** usados
nesta classificação, além de uma `dim_uc` compatível com os recortes. O importador
audita R3 e as FKs. Snapshots independentes de domínios diferentes não constituem
uma extração global atômica: a coordenação do lote precisa comprovar sua coerência.

### R5: quatro efeitos e P20

A R5 de `contracts/README.md` define a única decomposição da receita: volume,
reajuste, bandeira e mix sobre o consumo analítico. O consumidor aplica essa regra
sobre `receita_volume_mensal`; a Gold fornece volume faturado, receita,
arrecadação convencional e componentes de tarifa/bandeira com complemento
derivado ou explícito validado, sem duplicar o cálculo dos quatro efeitos.
Os componentes somam produtos Decimal antes de arredondar uma vez por grão a
duas casas (`round` Spark, empate afastando de zero); validam-se os resultados
com `exceptAll` nos dois sentidos. O cálculo dos quatro efeitos fica no consumidor, em
`backend/app/core/decomposicao.py`.

Para auditar os quatro efeitos no doc do domínio, considere as somas por
`municipio × bairro × classe × grupo_uc` em cada período: `Q` é
`volume_faturado_kwh`, `R` é `receita`, `T` é `componente_tarifa_reais` e `B`
é `componente_bandeira_reais`. Com `p₀ = R₀/Q₀`, `tᵢ = Tᵢ/Qᵢ`,
`bᵢ = Bᵢ/Qᵢ` e `k₀ = R₀/(T₀+B₀)`:

| Efeito (R$) | Fórmula |
| --- | --- |
| Volume | `(Q₁ − Q₀) × p₀` |
| Reajuste | `Q₁ × (t₁ − t₀) × k₀` |
| Bandeira | `Q₁ × (b₁ − b₀) × k₀` |
| Mix | `(R₁ − R₀) − volume − reajuste − bandeira` |

Se `Q₀ = 0` ou `T₀+B₀ = 0`, volume recebe `R₁−R₀` e os outros efeitos são
zero. Caso contrário, se `Q₁ = 0`, volume é `−R₀`, mix é `R₁` e os demais
são zero. Volume, reajuste e bandeira são arredondados uma vez por subgrão
para centavos com `ROUND_HALF_UP`; mix absorve o resíduo, fechando exatamente
com a variação da receita. Some os efeitos dos subgrãos para obter totais,
sem decompor novamente o agregado. A exclusão de faturas, a imputação do
volume, os doadores de tarifa e a classificação temporal R3 mudam as entradas
dessa decomposição; suas decisões de limpeza estão nas seções anteriores.

## Consistência das fontes e data de referência

A Gold materializa `v-energy.silver.tb_faturas_publicacao` uma única vez. Exige
duas entradas, destinos esperados, execução e instante de confirmação comuns,
revisões exclusivas no schema `silver_revisoes` e versões inteiras não negativas.
Consome `fonte` na `versao_fonte`, inclusive versões diferentes de zero. Marcador
ausente, incompleto ou incoerente aborta sem fallback para tabelas finais.
Cadastro, leituras, GD, inspeções e complemento também são fixados em versões Delta.
A conferência de identidade anterior à publicação verifica as **fontes consumidas**,
não a versão corrente dos destinos finais Silver; uma republicação não invalida
o par anterior. Execução Silver, revisões, identidades e versões ficam no marcador
Gold e nos recibos de exportação.

A retenção Silver começa na primeira observação da revisão fora do marcador e
dura ao menos sete dias. O Job Gold deve concluir dentro dessa janela; nunca
reduzir VACUUM nem manter um leitor aberto sete dias ou mais. Uma revisão removida
indica violação da retenção e exige falha/reinício desde o marcador, não fallback.

`data_referencia` é o retrato de status da extração, usado também como
`reference_date`. Deve ser ISO e não anterior ao primeiro dia da última competência
exportada nem às emissões/pagamentos observados. Não usa data atual ou início do
Job. Reprocessar a mesma extração com os mesmos parâmetros e snapshots preserva
os dados de negócio. O instante técnico da nova tentativa e seus UUIDs mudam.
`ingestion_datetime` prova ingestão, não necessariamente extração oficial. A data
22/10/2026 citada anteriormente é uma referência operacional observada; sua
oficialização continua dependente do responsável pela extração. O agendamento
foi removido do bundle; cada novo retrato exige informar explicitamente a referência.

## Publicação, interrupção e recuperação

O produtor grava tabelas exclusivas
`gold.tb_gold_faturas_<nome_logico>_revisao_<uuid>`, confere schema e conteúdo
integral e repete as reconciliações. O helper `publicar_delta` mantém compensação
`RESTORE`/`DROP` em exceções capturadas, agora aplicada às candidatas. Só depois
uma transação Delta substitui `gold.tb_gold_faturas_publicacao`, com nome lógico,
revisão, versão e metadados comuns. Essa confirmação persistente permite distinguir
um conjunto completo após reinício, sem depender de capturar timeout/cancelamento.

Consumidores devem chamar `ler_publicacao_gold(spark, schema, nomes_esperados)`
ou implementar o mesmo protocolo: materializar o marcador uma vez, validar seu
conjunto e ler cada fonte/versionAsOf. Consultar nomes fixos diretamente pode
observar dados legados ou incoerentes; não há promessa de atomicidade para eles.
O pipeline não atualiza esses nomes. Migre consumidores antes de usar a nova Gold.

No marcador `tb_gold_faturas_publicacao`, `id_execucao` e `metadados` são comuns
ao conjunto; `nome` identifica a saída lógica, `fonte` a tabela física da revisão
e `versao_fonte` a versão Delta a ler. A tabela técnica
`tb_gold_faturas_retencao` guarda `nome` (identificador físico normalizado) e
`aposentada_em` (primeira observação fora do marcador), sem reiniciar o prazo
em uma nova tentativa de manutenção. Nenhuma das duas compõe métricas comerciais.

| Interrupção/falha | Estado recuperável |
| --- | --- |
| Entre escritas ou conferências das revisões | Marcador anterior permanece; candidatas não referidas são ignoradas |
| Antes da confirmação | Mesmo comportamento, sem necessidade de rollback da publicação anterior |
| Confirmação retorna erro depois do commit | O próximo processo lê o marcador para saber qual conjunto foi confirmado; não remove candidatas após tentar confirmar |
| Exportação falha | Revisão Gold confirmada permanece; recibo ausente impede consumir exportação incompleta; reexportar o conjunto confirmado |
| Primeira carga sem marcador | Nenhuma publicação consumível; reiniciar e confirmar um conjunto completo |

Escritor único é pré-condição: `max_concurrent_runs: 1` mais ACL impedindo escritores
externos/manuais simultâneos. Verificação de identidade não substitui lock. O helper
`limpar_revisoes_gold` é manutenção **explícita**, executada sob a mesma exclusividade.
Valida o marcador, registra a primeira observação fora dele em
`tb_gold_faturas_retencao` com MERGE somente de inserção, e remove revisões conhecidas
fora do marcador apenas após sete dias. Não usa idade de criação. Reinícios não
renovam o prazo. UUIDs não são reutilizados nem revisões antigas reativadas.
Sem marcador válido não há limpeza. Se o Job parar antes da primeira confirmação,
confirme uma carga válida antes de manter/limpar as candidatas abandonadas. Não há
limpeza automática no caminho de `validar` ou publicação; o operador agenda a
manutenção somente após homologar permissões/retencão em catálogo de teste.

## Exportação, manifesto e montagem do lote (R6–R8)

A exportação auxiliar continua identificada como `tipo=gold_faturas`, com manifesto
próprio em `auxiliares/`; ele **não** é um manifesto do portal. Os dois CSVs comerciais
ficam em `comercial/`, com nomes e cabeçalhos canônicos e um `comercial.json` contendo
hashes, contagens, totais e proveniência. Esse recibo não se chama `manifest.json`
porque faltam as dez tabelas de outros domínios. Não é carga importável sozinho.

O exportador enumera os arquivos efetivamente entregues, valida cabeçalhos e
larguras de linha, relê com schema explícito e modo `FAILFAST`, e compara o
multiconjunto integral com `exceptAll` em ambos os sentidos. Não confia em
`_committed_*` nem considera o diretório exclusivo prova de integridade. Para as
comerciais, concatena CSVs via parser CSV e confere também o **arquivo final**.
Hashes e totais correspondem aos arquivos entregues; recibos são escritos por último.

[`montar_lote_gold.py`](../../data-engineering/silver_to_gold/montar_lote_gold.py)
recebe plano JSON com as **12 exportações existentes**, exige mesma proveniência
(`synthetic`, período e referência), confere hashes, tipos escalares e PKs, copia
para uma pasta nova e reutiliza `contracts/manifesto.py`. O manifesto final usa
`0.3.0-provisional`; `manifest_for` verifica schema e R6. FKs e gates relacionais
continuam a cargo de `importador --verificar`, sem publicar `analytics`.

| Responsável/domínio de origem | Tabelas a fornecer ao montador |
| --- | --- |
| Comercial, esta PR | `uc_consumo_faturamento_mensal`, `receita_volume_mensal` |
| Cadastro e rede | `dim_uc`, `dim_alimentador` |
| GD | `gd_uc` |
| Perdas/inspeções | `inspecoes_historicas`, `fila_inspecao` |
| Medição | `medidores_historico` |
| Continuidade/rede | `ocorrencias_uc`, `continuidade_alimentador_mensal` |
| Atendimento | `atendimentos`, `atendimentos_historico` |

O coordenador do lote reúne as dez saídas de seus produtores, garante que GD,
inspeções e cadastro correspondam aos snapshots usados aqui e preenche o plano.
Não há evidência nesta PR de exportação real completa desses domínios. Não se
preenchem ausências copiando as samples para um lote real. Fixtures completas usam
`synthetic=true` em todas as entradas e servem somente a testes.

Estrutura do plano (repita a entrada para cada uma das 12 tabelas, com hash real):

```json
{
  "batch_id": "identificador-do-lote",
  "period": {"start": "2022-07", "end": "2026-06"},
  "reference_date": "2026-10-22",
  "synthetic": false,
  "tables": {
    "uc_consumo_faturamento_mensal": {
      "file": "/caminho/comercial/uc_consumo_faturamento_mensal.csv",
      "sha256": "SHA256_DO_ARQUIVO",
      "receipt": "/caminho/comercial/comercial.json",
      "period": {"start": "2022-07", "end": "2026-06"},
      "reference_date": "2026-10-22",
      "synthetic": false
    }
  }
}
```

O exemplo é deliberadamente incompleto: o montador o rejeita até receber todas
as tabelas. Em ambiente de teste:

```bash
python data-engineering/silver_to_gold/montar_lote_gold.py --plano plano.json --destino /tmp/lote-gold
uv run importador --origem /tmp/lote-gold --verificar
```

O segundo comando exige PostgreSQL/Redis de teste configurados. Código 0 com `OK`
comprova os gates para **aquele lote**; não comprova fontes de negócio nem Databricks.

## Desempenho, CI e evidências

As fontes Delta são lidas com `versionAsOf`, incluindo as revisões financeiras
fixadas pelo marcador Silver. Os planos derivados usam esses mesmos snapshots
na validação, exibição, publicação e exportação. O fluxo não acessa `is_cached`
nem usa `cache()`/`persist()`, incompatíveis com Serverless. A validação comum é
reutilizada para o mesmo par de DataFrames, mantendo as conferências `exceptAll`.
Não há benchmark de tempo ou ganho medido em 2,2 milhões de linhas.

`.github/workflows/ci.yml` detecta alterações de dados, contratos, importador e
configuração compartilhada para o job `gold`. Executa Ruff 0.17.3 (`check` e
`format --check`) e a suíte em `data-engineering/tests`. O agregador obrigatório
`CI` inclui `gold` e exige sucesso quando acionado, ou `skipped` quando dispensado;
falha, cancelamento ou skip indevido reprovam. Backend, frontend e `faturas`
(Silver) foram preservados. O workflow separado `gold-faturas.yml` foi removido.
O bundle sincroniza também `../contracts`, necessário para carregar os YAMLs e
VERSION a partir do módulo. Essa configuração foi conferida localmente; CLI e
imports do runtime ainda precisam de validação no workspace.
O nome do bundle continua `venergy-gold-faturas`: só há esta tarefa no bundle,
e renomeá-lo sem migração pode criar outra identidade de deployment. A ampliação
organizacional poderá acompanhar a integração das demais tarefas.

As evidências anteriores fornecidas pelo usuário comprovam 45.000 UCs Silver,
201 em quarentena, 2.152.336 leituras e uma execução anterior da Gold em `validar`
sem escrita: jul/2022–jun/2023 × jul/2025–jun/2026, 32.285 faturas segregadas e
R$ 10.192.373,82. O `double` de cobertura daquela versão foi corrigido para
`decimal(5,2)`. Essas evidências não validam o novo contrato ou protocolo.

As verificações desta revisão são locais, com Spark real, catálogos/falhas
simulados e fixtures sintéticas. O relatório e a matriz de aderência estão em
[aderencia-faturas-0.3.md](aderencia-faturas-0.3.md). Nenhum produtor foi executado,
tabela sobrescrita, Job implantado, agendamento ativado ou carga real publicada
no Databricks durante este trabalho.

Homologação concreta pendente em catálogo/Volume **de teste**, a cargo do operador:
exercitar Delta/UC real, concorrência da Silver durante a leitura, interrupções
entre revisões e antes/depois da confirmação, writer commit com resposta perdida,
ACL de escritor único, snapshots retidos, registro MERGE e limpeza após sete dias;
conferir leitura exata dos CSVs no FUSE do Volume, timestamps e visibilidade de
rename/recibo no runtime. A hipótese de part files órfãos não foi reproduzida no
Databricks; os testes locais comprovam rejeição de conteúdo divergente injetado.
A referência oficial da extração, a disponibilidade de GD/inspeções e os doadores
de tarifa permanecem dependências identificadas acima.

## Correções da revisão 5746693852

O Job não tem agendamento: data_referencia continua sendo a data explícita do
retrato, não o relógio da execução. Uma futura recorrência requer política própria.
As duas saídas usam a mesma leitura enriquecida com trocas de medidor; as
auxiliares continuam usando apenas volume observado utilizável e as comerciais
incluem imputação, com método e cobertura explícitos. As fontes são fixadas por versão Delta, sem cache; a validação comum é
reaproveitada pelo par de DataFrames, e as APIs isoladas continuam validando suas entradas.

O complemento exige id_fatura, tarifa_base, adicional_bandeira e proveniencia.
volume_faturado_kwh recebido em um complemento legado é ignorado: o volume
canônico vem sempre de consumo_kwh_analitico. Bandeiras e adicionais usam um
único domínio no módulo. Datas, textos e booleanos são exigidos nos tipos exatos
antes dos casts; timestamps não são truncados silenciosamente.

Para montar o lote, cada CSV precisa de recibo do produtor (comercial.json ou
manifest.json adjacente, ou caminho receipt na entrada do plano). O montador
confere versão, período, referência, synthetic booleano, nome/caminho e hash da
tabela contra esse recibo, além de conferir a cópia. Um plano real apontando para
contracts/samples é rejeitado pelo manifesto sintético de origem. Recibos são
evidências dos produtores e devem vir de fonte confiável; não são assinaturas
digitais. Produtores dos outros dez domínios precisam fornecer seus recibos.
Os escritores e a releitura Spark usam escape com aspas duplicadas, compatível
com o parser CSV da stdlib e o importador, inclusive aspas, barras e quebras.

## Correções dos reviews 5753211198 e 5754871341

O fluxo usa snapshots Delta sem cache para funcionar em Serverless. Os writers
auxiliar e comercial preservam espaços nas pontas, além de aspas e quebras de
linha. O agregado auxiliar usa zero quando não há volume utilizável, preservando
a contagem de faturas sem volume e a receita. A decomposição auxiliar foi retirada;
a R5 contratual permanece a única fórmula de decomposição.

Uma tarifa líquida negativa não doa para a mediana. A fatura continua elegível e
recebe a tarifa do grupo/mês; a ausência de qualquer doador válido ainda bloqueia
a carga. `complemento_proveniencia` inclui `competencia`, `doadores_tarifa` e
`doadores_tarifa_negativa_excluidos`. Essas contagens se repetem por fatura: o
relatório do notebook as exibe uma vez por subgrupo × competência, sem somar as
repetições. Leituras imputadas não doam tarifa; tarifa zero continua válida.

Na retenção, nomes de tabelas são normalizados na inserção, na comparação do
MERGE e na seleção para remoção, inclusive registros legados com caixa ou aspas
diferentes. Revisões protegidas pelo marcador e pela janela de sete dias continuam
preservadas; duplicatas legadas geram uma única remoção.
