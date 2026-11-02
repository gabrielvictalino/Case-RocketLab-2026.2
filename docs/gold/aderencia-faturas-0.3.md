# Aderência da Gold de faturas à #101 — 0.3.0-provisional

Referência: `dev` em `efbaa13b83eb22970fccc64e66c3a24df53ae3d6`, integrada à
`feat/gold-faturas` por merge sem reescrever histórico. O HEAD remoto inicial da
#67 era `90c3b69d47dad5e9b49d9fccbdacc9d51d4ab241`. A integração local não apresentou
conflitos. Esta revisão não executou produtores ou mutações no Databricks.

| Requisito | Implementação | Evidência local | Dependência ou bloqueio remanescente |
| --- | --- | --- | --- |
| R1, saídas comerciais, grão, chaves e ordem | `gold_contrato_faturas.py` carrega os dois YAMLs; valida PK, enums, nulabilidade, precisão/escala antes dos casts; exporta dois CSVs com cabeçalho canônico | `test_contrato_gold`, exportação integral da fixture e `--verificar` | Aprovação de negócio dos dados reais e coerência com a dimensão cadastral do lote |
| R2, consumo original/analítico | Original da Silver separado; leitura utilizável igual ao original; medianas da própria UC por fase da GD e fallback histórico; auxiliar com métodos, medianas e doadores | Troca de medidor, fallback, ausência de doadores e igualdade testados em Spark real | Aceitar explicitamente o significado de original após normalização/correção de sinal da Silver; sem doadores ou sem leitura obrigatória, bloquear e recuperar fonte |
| R2, sem fatura e múltiplas | Parte das leituras; junta só fatura elegível; todas as múltiplas segregadas; zeros/nulos contratuais preservam consumo | Casos sem emissão e com múltiplas em `test_contrato_gold`; reconciliação financeira integral mantida | Recuperar leitura se houver competência com fatura de UC conhecida e original indisponível; não preencher com zero |
| R2, vencimento/enums/pagamento | `data_vencimento` preservada, bandeiras e `EM ABERTO` normalizados; PAGA recebe total nominal e ABERTA zero | Testes de PAGA, ABERTA, VERDE e sem fatura; gates atuais do importador | A convenção não comprova caixa efetivo, apesar da descrição provisória do contrato; homologar com responsável financeiro |
| R2, volume faturado e tarifas | Complemento Delta por `id_fatura`, com `volume_faturado_kwh`, `tarifa_base`, `adicional_bandeira` e `proveniencia` obrigatórios para fatura elegível | Fixtures com complemento; ausência de cada campo bloqueia; escala excedida rejeitada | **Bloqueio real:** esses três campos não existem na Silver de faturas. Responsável comercial deve fornecer volume faturado e tarifas homologadas, vigências e origem; não há nome físico comprovado. O widget vazio bloqueia publicação antes de escrever |
| R3, grupo temporal | GD desde mês da conexão; senão, primeira inspeção confirmada; senão, demais. Snapshots de GD e inspeções obrigatórios | Testes antes/no mês de conexão, antes/no mês da inspeção e precedência da GD | Comprovar disponibilidade e coerência das fontes: `v-energy.silver.tb_geracao_distribuida` e nome legado parametrizável `venergy.silver.inspecoes`; exportar os mesmos dados ao lote |
| R4, outros domínios | Montador recebe as dez tabelas externas, sem fabricá-las; gates relacionais continuam no importador | Suíte atual de 50 testes do importador e fixture completa aprovada | Os respectivos produtores devem fornecer dimensões, GD, fila, inspeções, medição, continuidade e atendimento reais compatíveis; esta PR não os substitui |
| R5, quatro efeitos | Fornece volume/receita e soma Decimal dos produtos de tarifa e bandeira, arredondados uma vez por grão. Decomposição auxiliar rotulada como distinta da canônica | Teste de soma antes do arredondamento e reconciliação por grão com `exceptAll`; docs da P20 consultadas | Três métricas do complemento são pré-condição; a fórmula canônica e seus casos de borda pertencem à P20, ainda indicada como pendência no consumidor. Não duplicada na Gold |
| R6, referência | `data_referencia` explícita e ISO vira `reference_date`; competência posterior bloqueia; montador/importador validam referência ≥ primeiro dia de `period.end` | Datas vazias/inválidas e lote com referência anterior rejeitados; notebook com 24 competências simulado | Responsável pela extração deve confirmar a data oficial do retrato; ingestão de 22/10 é evidência operacional, sem equivalência automática com extração. Job permanece PAUSED |
| R7, manifesto | Reutiliza `contracts/manifesto.py`, versão 0.3.0; recibo comercial separado; montador exige exatamente 12 exportações com período/referência/proveniência compatíveis | `test_lote_ci_gold`: lote completo, falta de tabela, mistura synthetic/real, PK, escala e hash inválidos | Coordenador deve reunir dez exportações dos outros domínios, com dados compatíveis com os snapshots comerciais. Não existe evidência de lote real completo |
| R8, homologação | Fluxo de montagem + `importador --verificar` mantém FKs, gates, índices e rollback do importador da dev | CLI real sobre lote de 12 fixtures, incluindo os dois CSVs reexportados: OK, retorno 0; hash alterado: retorno 1; analytics e operations.cargas preservados | Repetir no lote real completo em banco de teste, após resolver fontes; aprovação de fixtures não homologa a Gold real |
| Review 1, consistência Silver | Marcador lido uma vez; valida par, identidade comum, revisões e versões; lê fonte/versionAsOf; metadados registram snapshots efetivos | Migração de fatura pendente durante republicação simulada não perde receita; marcador inválido recusado; versões 3 e 7 | Exercitar o protocolo com Delta/UC e a retenção real de pelo menos 7 dias após retirada do marcador |
| Review 2, política de data | Referência preserva o retrato; agendamento pausado e parâmetro explícito | Notebook em validar sem escrita e publicação bloqueada sem complemento; datas ISO testadas | Oficializar referência de cada nova extração antes de ativar qualquer agendamento |
| Review 3, interrupção/recuperação | Revisões exclusivas, reconciliação e confirmação persistente por marcador; mantém compensação nas candidatas; manutenção com aposentadoria persistente e 7 dias | Morte entre escritas, antes do marcador e resposta perdida após confirmação simuladas; consumidor recupera conjunto anterior pelo marcador; limpeza protege atuais/recentes | Validar Delta real, ACL de escritor único, falhas de comunicação e retenção. Leitores de nomes fixos legados precisam migrar; não recebem atomicidade conjunta |
| Review 4/10, CI e documentação | Job Gold no detector e needs do CI; lint, formato e suíte; workflow separado removido. `.github/` descrito nesta PR e no guia | Scripts reais do detector/agregador executados com fixtures; failure/cancelled/skip indevido rejeitados; demais jobs preservados | CI remoto precisa concluir no novo commit; proteções administrativas não foram alteradas |
| Review 5, identificadores | Comparação normalizada e guards de schemas proibidos e fonte/destino, antes das escritas | `v-energy.Silver`, `BRONZE`, `Default` e identificadores equivalentes em capitalizações diferentes bloqueados | Nenhum bloqueio local; testar os identificadores físicos do workspace na homologação |
| Review 6, arquivos entregues | Parser estrito e releitura com schema; `exceptAll` bidirecional no conjunto entregue e no CSV comercial final; hashes/totais e recibos por último | Parte duplicada e troca de valores com total igual recusadas; fixture exportada aceita no importador | Protocolo de commit, FUSE, timestamps e visibilidade de recibo/rename no Volume precisam de teste Databricks. Hipótese de órfãos não foi reproduzida lá |
| Review 7, recomputação | Persistência seletiva da união, saídas reutilizadas e consumo, com liberação em finally; conferências integrais mantidas | Teste de liberação em falha e preservação do cache do chamador; suíte Spark | Ganho esperado, sem benchmark de produção nesta revisão |
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
