# Dicionário da Gold de faturas — GOLD_FATURAS_V2

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
| `cobertura_volume_pct` | decimal(5,2), % | 100 × contas com volume positivo / contas elegíveis, duas casas |
| `versao_regras_gold` | string | GOLD_FATURAS_V2 |

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
| `versao_regras_gold` | string | GOLD_FATURAS_V2 |

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

## Integração comercial — contrato 0.3.0-provisional (#101)

As seções `tb_*` acima descrevem **saídas auxiliares lógicas**, mantidas para
reconciliação e investigação. O marcador Gold aponta para as tabelas físicas de
cada revisão; consultar nomes fixos legados não acompanha esta publicação.
As saídas comerciais são `uc_consumo_faturamento_mensal` e
`receita_volume_mensal`, com colunas, ordem, tipos e escalas carregados dos YAMLs
em `contracts/tabelas/`. O adaptador fica em
[`gold_contrato_faturas.py`](../../data-engineering/silver_to_gold/gold_contrato_faturas.py).
Acrescenta o gate de volume igual ao analítico no importador; auxiliares não substituem o contrato.

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
- A fase muda no mês de conexão. Uma UC sem conexão tem uma única fase. A mediana
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
  elegíveis. Subtrair a bandeira evita contá-la duas vezes nos componentes da R5.
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
  continua sujeito aos gates, inclusive volume igual ao analítico. O importador
  também verifica essa igualdade para toda linha com fatura.
- Os componentes da R5 somam produtos decimais antes de arredondar por grão.
  Não se fixa `k₀ = 4/3`: resíduos e composição podem mudar o fator e o mix.
  Volume implícito pela conta não substitui o volume canônico.

A homologação no Databricks, disponibilidade/coerência das fontes (incluindo
inspeções), referência oficial e lote completo de 12 tabelas seguem necessárias.

### R3: grupo temporal

O adaptador exige snapshots de `tb_geracao_distribuida` (`id_uc`, `data_conexao`)
e de inspeções (`id_uc`, `data`, `resultado`). O padrão de inspeções é
`venergy.silver.inspecoes`, nome do produtor versionado em
`notebooks/02_bronze_to_silver_inspecoes.ipynb`; sua disponibilidade e eventual
migração de catálogo precisam ser confirmadas no workspace. Não cria nem publica
essas fontes. A precedência é GD desde o mês da conexão; senão, irregularidade
confirmada desde o mês da primeira inspeção com esse resultado; senão, demais.
Flags cadastrais atuais não são projetadas para trás.

O lote de 12 tabelas deve conter **os mesmos dados de GD e inspeções** usados
nesta classificação, além de uma `dim_uc` compatível com os recortes. O importador
audita R3 e as FKs. Snapshots independentes de domínios diferentes não constituem
uma extração global atômica: a coordenação do lote precisa comprovar sua coerência.

### R5: quatro efeitos e P20

A decomposição de `tb_variacao_receita` permanece auxiliar: volume utilizável,
preço efetivo e receita sem volume. Não equivale a volume, reajuste, bandeira e
mix do contrato. `contracts/README.md` e `docs/backend-pendencias.md` atribuem a
fórmula canônica à P20; os consumidores atuais usam `receita_volume_mensal`
(importador, views e portal). Esta PR fornece nessa tabela volume faturado,
receita, arrecadação convencional e componentes de tarifa/bandeira com o complemento derivado ou explícito validado, sem duplicar o cálculo dos quatro efeitos.
Os componentes somam produtos Decimal antes de arredondar uma vez por grão a
duas casas (`round` Spark, empate afastando de zero); validam-se os resultados
com `exceptAll` nos dois sentidos. A P20 permanece responsável pelo cálculo dos quatro efeitos no consumidor.

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
permanece `PAUSED`; cada novo retrato exige atualizar explicitamente a referência.

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

A execução persiste seletivamente a união Silver, saídas reutilizadas e consumo
contratual em `MEMORY_AND_DISK`; reaproveita-os em validação, display, publicação
e exportação, com liberação em `finally` via context managers. Não remove
`exceptAll`. A redução de recomputações é esperada; não há benchmark de tempo,
memória ou ganho medido em 2,2 milhões de linhas nesta revisão.

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
