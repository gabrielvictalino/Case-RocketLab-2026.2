# Aderência da Gold de faturas à #101 — 0.3.0-provisional

Referência: `dev` em `efbaa13b83eb22970fccc64e66c3a24df53ae3d6`, integrada à
`feat/gold-faturas` por merge sem reescrever histórico. O HEAD remoto inicial da
#67 era `90c3b69d47dad5e9b49d9fccbdacc9d51d4ab241`. A integração local não apresentou
conflitos. Esta revisão não executou produtores ou mutações no Databricks.

| Requisito | Implementação | Evidência local | Dependência ou bloqueio remanescente |
| --- | --- | --- | --- |
| R1, saídas comerciais, grão, chaves e ordem | `gold_contrato_faturas.py` carrega os dois YAMLs; valida PK, enums, nulabilidade, precisão/escala antes dos casts; exporta dois CSVs com cabeçalho canônico | `test_contrato_gold`, exportação integral da fixture e `--verificar` | Aprovação de negócio dos dados reais e coerência com a dimensão cadastral do lote |
| R2, consumo original/analítico | Original da Silver separado; leitura utilizável igual ao original; medianas da própria UC por fase da GD e fallback histórico; auxiliar com métodos, medianas e doadores | Troca de medidor, fallback, ausência de doadores e igualdade testados em Spark real | Aceitar explicitamente o significado de original após normalização/correção de sinal da Silver; sem doadores, bloquear com contagem; trocas também pelo mês de retirada do medidor |
| R2, sem fatura e múltiplas | Parte das leituras; junta só fatura elegível; todas as múltiplas segregadas; zeros/nulos contratuais preservam consumo | Casos sem emissão e com múltiplas em `test_contrato_gold`; reconciliação financeira integral mantida | Fatura sem leitura segregada com FATURA_SEM_LEITURA; não preencher original com zero |
| R2, vencimento/enums/pagamento | `data_vencimento` preservada, bandeiras e `EM ABERTO` normalizados; PAGA recebe total nominal e ABERTA zero | Testes de PAGA, ABERTA, VERDE e sem fatura; gates atuais do importador | A convenção não comprova caixa efetivo, apesar da descrição provisória do contrato; homologar com responsável financeiro |
| R2, volume faturado e tarifas | Complemento Delta por `id_fatura`, com `tarifa_base`, `adicional_bandeira` e `proveniencia` obrigatórios para fatura elegível | Fixtures com complemento; ausência de cada campo bloqueia; escala excedida rejeitada | Decisão 6587742059: complemento derivado no widget vazio; volume analítico e tarifa líquida da bandeira por subgrupo/mês; falta de doador bloqueia |
| R3, grupo temporal | GD desde mês da conexão; senão, primeira inspeção confirmada; senão, demais. Snapshots de GD e inspeções obrigatórios | Testes antes/no mês de conexão, antes/no mês da inspeção e precedência da GD | Comprovar disponibilidade e coerência das fontes: `v-energy.silver.tb_geracao_distribuida` e `v-energy.silver.tb_inspecoes`, produzida por `data-engineering/bronze_to_silver/bronze-to-silver-inspecoes.ipynb` (#116), com nome parametrizável; confirmar publicação no workspace e exportar os mesmos dados ao lote |
| R4, outros domínios | Montador recebe as dez tabelas externas, sem fabricá-las; gates relacionais continuam no importador | Suíte atual de 50 testes do importador e fixture completa aprovada | Os respectivos produtores devem fornecer dimensões, GD, fila, inspeções, medição, continuidade e atendimento reais compatíveis; esta PR não os substitui |
| R5, quatro efeitos | Fornece volume/receita e soma Decimal dos produtos de tarifa e bandeira, arredondados uma vez por grão. Sem decomposição auxiliar; os quatro efeitos são calculados no consumidor pela R5 | Teste de soma antes do arredondamento e reconciliação por grão com `exceptAll`; docs da P20 consultadas | Volume analítico e tarifas são pré-condições; a fórmula e seus casos de borda ficam no consumidor (`backend/app/core/decomposicao.py`), sem duplicação na Gold |
| R6, referência | `data_referencia` explícita e ISO vira `reference_date`; competência posterior bloqueia; montador/importador validam referência ≥ primeiro dia de `period.end` | Datas vazias/inválidas e lote com referência anterior rejeitados; notebook com 24 competências simulado | Responsável pela extração deve confirmar a data oficial do retrato; ingestão de 22/10 é evidência operacional, sem equivalência automática com extração. Job sem cron, com referência explícita |
| R7, manifesto | Reutiliza `contracts/manifesto.py`, versão 0.3.0; recibo comercial separado; montador exige exatamente 12 exportações com período/referência/proveniência compatíveis | `test_lote_ci_gold`: lote completo, falta de tabela, mistura synthetic/real, PK, escala e hash inválidos | Coordenador deve reunir dez exportações dos outros domínios, com dados compatíveis com os snapshots comerciais. Não existe evidência de lote real completo |
| R8, homologação | Fluxo de montagem + `importador --verificar` mantém FKs, gates, índices e rollback do importador da dev | CLI real sobre lote de 12 fixtures, incluindo os dois CSVs reexportados: OK, retorno 0; hash alterado: retorno 1; analytics e operations.cargas preservados | Repetir no lote real completo em banco de teste, após resolver fontes; aprovação de fixtures não homologa a Gold real |
| Review 1, consistência Silver | Marcador lido uma vez; valida par, identidade comum, revisões e versões; lê fonte/versionAsOf; metadados registram snapshots efetivos | Migração de fatura pendente durante republicação simulada não perde receita; marcador inválido recusado; versões 3 e 7 | Exercitar o protocolo com Delta/UC e a retenção real de pelo menos 7 dias após retirada do marcador |
| Review 2, política de data | Referência preserva o retrato; sem agendamento recorrente e com parâmetro explícito | Notebook em validar sem escrita com complemento derivado; datas ISO testadas | Oficializar referência de cada nova extração antes de ativar qualquer agendamento |
| Review 3, interrupção/recuperação | Revisões exclusivas, reconciliação e confirmação persistente por marcador; mantém compensação nas candidatas; manutenção com aposentadoria persistente e 7 dias | Morte entre escritas, antes do marcador e resposta perdida após confirmação simuladas; consumidor recupera conjunto anterior pelo marcador; limpeza protege atuais/recentes | Validar Delta real, ACL de escritor único, falhas de comunicação e retenção. Leitores de nomes fixos legados precisam migrar; não recebem atomicidade conjunta |
| Review 4/10, CI e documentação | Job Gold no detector e needs do CI; lint, formato e suíte; workflow separado removido. `.github/` descrito nesta PR e no guia | Scripts reais do detector/agregador executados com fixtures; failure/cancelled/skip indevido rejeitados; demais jobs preservados | CI remoto precisa concluir no novo commit; proteções administrativas não foram alteradas |
| Review 5, identificadores | Comparação normalizada e guards de schemas proibidos e fonte/destino, antes das escritas | `v-energy.Silver`, `BRONZE`, `Default` e identificadores equivalentes em capitalizações diferentes bloqueados | Nenhum bloqueio local; testar os identificadores físicos do workspace na homologação |
| Review 6, arquivos entregues | Parser estrito e releitura com schema; `exceptAll` bidirecional no conjunto entregue e no CSV comercial final; hashes/totais e recibos por último | Parte duplicada e troca de valores com total igual recusadas; fixture exportada aceita no importador | Protocolo de commit, FUSE, timestamps e visibilidade de recibo/rename no Volume precisam de teste Databricks. Hipótese de órfãos não foi reproduzida lá |
| Review 7, recomputação / Serverless | Snapshots por versão Delta sem cache; reutilização da validação comum por par de DataFrames; conferências integrais mantidas | Notebook local recusa chamadas a cache/persist e acesso a is_cached | Tempo de execução sem cache requer medição no Serverless real |
| Review 8/9, tipo e helpers | Cobertura `decimal(5,2)` em código/docs/teste; regex de competência e deslocamento mensal centralizados | Assert de schema e testes de virada de ano; suíte financeira existente preservada | Nenhum bloqueio local |

## Verificações executadas em 02/11/2026

- Bundle: YAML e caminhos de sincronização conferidos localmente, incluindo `contracts/`;
  nenhuma validação/deploy com CLI Databricks foi executada.
- Ruff 0.17.3: `check` e `format --check` nos caminhos Gold; `git diff --check`.
- Suíte Gold: **38 testes aprovados**, com Spark real e simulações de catálogo, marcadores,
  interrupção, retenção, arquivos, lote, notebook e CI.
- Suíte da raiz via unittest: 19 testes, incluindo fluxo Git e Silver de faturas.
- `uv run pytest importador -q`: **50 aprovados**, com PostgreSQL 17 e Redis 7
  locais via Testcontainers.
- Experimento local completo: leu os dois CSVs comerciais de `contracts/samples`
  em DataFrames tipados, exportou-os pelo novo exportador, montou as 12 tabelas
  com `synthetic=true` e executou a CLI real `importador --verificar` em banco
  de teste. Retornou `OK`, versão `0.3.0-provisional`, período
  `2022-07..2026-06`, referência sintética `2026-07-01`, **14.364 linhas de UC/mês**
  e **1.277 linhas comerciais agregadas**. Após adulterar o hash de receita,
  a CLI rejeitou o lote com retorno 1. Contagem de cargas, soma financeira
  analítica e quantidade de UCs permaneceram iguais antes/depois nos dois casos.

A execução real anterior em `validar`, relatada pelo usuário, continua registrada
no [dicionário](faturas.md). Ela não exercitou este protocolo nem o contrato da
#101. Nesta revisão não houve publicação, teste de recuperação, deploy ou
homologação no Databricks. Os testes locais não substituem os ensaios de runtime
e as decisões de negócio identificadas na matriz.

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

## Validação da decisão 6587742059

39 cenários Gold com Spark 4.0.1: os 7 testes contratuais foram reexecutados
após os ajustes finais e passaram; os outros 32 passaram na suíte completa.
19 testes da raiz e 51 do importador passaram (PostgreSQL 17 e Redis 7 via
Testcontainers), incluindo o novo gate de volume analítico. Ruff 0.17.3
(check e format --check) e git diff --check aprovados. O notebook em validar
foi exercitado com 24 competências sintéticas, snapshots simulados e derivação
do complemento, sem escrita.

A tentativa de acesso à API SQL Databricks retornou HTTP 401 com a credencial
configurada. Não houve execução do notebook, publicação, deploy ou ativação
de agendamento no Databricks nesta implementação; a homologação real segue pendente.

## Revisão 5746693852

Corrigidos os seis pontos funcionais/documentais e as limpezas de hash da Gold,
validações comuns, domínio de bandeiras e tipos contratuais. Ver a seção de
correções no dicionário de faturas para a política sem cron e o protocolo de recibos.

Validação local: 43 testes Gold aprovados com Spark 4.0.1, 19 testes da raiz,
Ruff check/format e git diff --check. Os dois testes contratuais afetados pelos
ajustes finais foram reexecutados e passaram, incluindo CSV comercial com aspas
e quebras de linha e complemento sem volume. O notebook em validar foi testado
com 24 competências sintéticas e snapshots simulados. Nenhuma implantação,
publicação ou execução Databricks foi feita nesta correção.

## Reviews 5753211198 e 5754871341 — 03/11/2026

Os nove ajustes foram implementados: snapshots sem cache para Serverless,
doadores com tarifa negativa excluídos e contados na proveniência, espaços
preservados nos dois writers CSV, retirada da decomposição auxiliar, retenção
com identificadores normalizados inclusive no MERGE, volume agregado vazio igual
a zero, fase `SEM_GD` e definições de domínio alinhadas nos guias e no glossário.
A R5 continua no consumidor sobre as tabelas comerciais e o consumo analítico.

Validação local com Spark 4.0.1: 45 cenários Gold verificados entre a execução
completa e a reexecução dirigida dos cenários ajustados, incluindo notebook em
`validar` com histórico curto e rejeição de APIs de cache, além da condição real
do MERGE executada no Spark. Os 19 testes da raiz, Ruff 0.17.3 check/format,
compilação das células do notebook, sintaxe do script de configuração GitHub e
git diff --check passaram. A branch incorpora `dev` em `5b9d30e`, preservando
as seções do portal e os demais domínios nos conflitos de documentação.

A consulta autenticada a `/api/2.0/sql/warehouses` retornou HTTP 401 com a
credencial configurada. A execução real em `validar` no Databricks permanece
pendente; não houve deploy ou publicação de dados no workspace.
