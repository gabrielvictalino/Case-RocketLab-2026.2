# Dicionário da Gold de faturas — GOLD_FATURAS_V1

Escopo: faturamento e situação das contas, conforme as seções 3.2, 4.1, 4.2 e
5.2 do case. A modelagem da Gold é decisão do time. A implementação não muda os
tratamentos Silver nem implementa DEC/FEC, GD, inspeções ou atendimento.

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
O notebook fixa as versões Delta e registra as identidades no manifesto.
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
- Leituras faltantes ou negativas não eliminam receita. Não usamos `abs()`, não
  estimamos consumo de troca e não substituímos consumo desconhecido por zero.
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
| `versao_regras_gold` | string | GOLD_FATURAS_V1 |

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
| `volume_analise_kwh` | decimal(28,2), kWh, anulável | Soma da parcela utilizável; NULL se nenhuma leitura utilizável |
| `receita_com_volume_positivo` | decimal(28,2), R$ | Total das contas com volume positivo utilizável |
| `receita_sem_volume_positivo` | decimal(28,2), R$ | Total das demais, inclusive zero medido; fecha com a receita pareada |
| `cobertura_volume_pct` | decimal, % | 100 × contas com volume positivo / contas elegíveis, duas casas |
| `versao_regras_gold` | string | GOLD_FATURAS_V1 |

Para recortes de bandeira ou status, consulte `tb_faturas`. Para vários meses,
some valores/contagens; recalcule percentuais a partir das somas. Não some UCs
mensais para obter UCs distintas do período nem tire média simples de tarifas.

## `tb_variacao_receita`

Grão/chave: **município × bairro × classe × quatro limites dos períodos**.
O notebook compara os primeiros 12 meses com os últimos 12; a função
`comparar_periodos` aceita quaisquer dois intervalos de igual duração mensal,
inclusive comparação com o mesmo mês do ano anterior. Os limites são inclusivos,
datas do primeiro dia do mês, e todos os meses precisam existir globalmente.
Um segmento pode entrar ou sair; o FULL JOIN preserva esses casos.

| Coluna(s) | Tipo / unidade | Definição |
| --- | --- | --- |
| `municipio`, `bairro`, `classe` | string | Recorte cadastral |
| `inicio_base`, `fim_base`, `inicio_atual`, `fim_atual` | date | Limites dos períodos comparados |
| `receita_base`, `receita_atual` | decimal(28,2), R$ | Soma de todo faturamento elegível em cada período |
| `receita_pareada_base`, `receita_pareada_atual` | decimal(28,2), R$ | Receita com volume positivo utilizável |
| `receita_sem_volume_base`, `receita_sem_volume_atual` | decimal(28,2), R$ | Receita sem volume positivo utilizável |
| `volume_base_kwh`, `volume_atual_kwh` | decimal(28,2), kWh | Soma somente da parcela utilizável; zero é a soma vazia para a álgebra |
| `quantidade_faturas_base`, `quantidade_faturas_atual` | long | Contas por período |
| `quantidade_com_volume_base`, `quantidade_com_volume_atual` | long | Cobertura da receita pareada por período |
| `variacao_receita` | decimal, R$ | Receita atual − base |
| `variacao_receita_pct` | decimal, %, anulável | 100 × variação / receita base; NULL se base zero |
| `efeito_volume` | decimal(28,2), R$ | (Q1 − Q0) × P0, arredondado para centavos |
| `efeito_preco_efetivo` | decimal(28,2), R$ | Variação da receita pareada − efeito volume |
| `efeito_receita_sem_volume` | decimal, R$ | Receita sem volume atual − base |
| `versao_regras_gold` | string | GOLD_FATURAS_V1 |

Q é o volume utilizável e P é a receita pareada / Q. Na entrada de um segmento sem
preço base, usa-se P1 para atribuir a receita pareada de entrada ao volume. Na saída,
usa-se P0. Sem volume em ambos os períodos, os efeitos pareados são zero e toda a
variação fica na parcela sem volume. A cobertura acompanha os resultados, para não
confundir ausência de leitura com queda real de consumo.

A interação preço × quantidade fica no efeito preço. O cálculo do efeito volume
usa decimal e arredonda uma vez por segmento; o preço recebe o resíduo de centavos.
Sempre vale `variação = volume + preço efetivo + receita sem volume`.
O preço efetivo agrega tarifa, bandeira, tributos e mix interno do segmento.
Não identifica isoladamente reajuste homologado, efeito bandeira, GD ou fraude.
Comparações com cobertura diferente exigem investigação antes de atribuir causas.

## Intercâmbio e limites da entrega

CSV e manifesto são exportados por domínio, com todas as colunas na ordem do
schema persistido. O manifesto é próprio de `gold_faturas`, não usa a versão
`0.2.0-provisional` de `contracts/`. Essa versão do portal exige kWh faturado,
tarifa base e adicional de bandeira não comprovados pelas fontes disponíveis.
Esta Gold não preenche esses campos com estimativas ocultas. A adaptação do contrato
e do importador para essas tabelas deve preservar as definições deste dicionário.

A validação local usa dados sintéticos e Spark real. Não há resultados novos dos
2,18 milhões de registros, execução Databricks, publicação de Job ou importação
no PostgreSQL alegados nesta entrega. Consulte o [guia de execução](../../data-engineering/README.md).
