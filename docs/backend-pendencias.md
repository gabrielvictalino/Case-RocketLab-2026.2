# Backend: decisões adotadas e integração pendente

Inspeção em 28/10/2026: a dev remota estava em `6baefc1`; o clone inicial buscava
apenas main e tinha referências antigas. O workspace do PR #61, branch
`chore/33-estrutura-workspace`, SHA `064d4e3`, foi reaproveitado como arquivos,
sem integrar o histórico da branch de origem. A implementação foi iniciada em `feat/base-backend`,
baseada na dev. As branches de dados e a branch de arquitetura foram consultadas;
não foi encontrado contrato Gold aprovado/versionado nessas referências.

## Decisões consolidadas

| Assunto | Divergência | Decisão desta entrega |
|---|---|---|
| Agente | Proposta antiga admitia serviço/container próprio | Pacote Python integrado, duas engines, conforme ADR 0001 |
| Rotas de ordens | Análise anterior sugeria PATCH genérico | Ações `/despachar`, `/tentativas`, `/resultado`, `/cancelar`, conforme system design |
| Python | Workspace #61 propunha 3.14 | 3.12 em todos os membros, imagem e CI, para usar o runtime disponível e validado; versões resolvidas no uv.lock |
| Consumo | Diagnóstico usa mediana, tela menciona média, Silver preserva negativos sinalizados | Nenhuma estimativa oficial implementada; original preservado, analítico sintético e método explícito |
| Continuidade | Soma simples no diagnóstico versus duração efetiva/união na Silver | #57 consome os numeradores mensais Gold, denominador fixo por alimentador e exclusão opcional por competência marcada; causas contadas no detalhe, conforme `docs/gold/continuidade.md`. Homologação real continua pendente |
| Gold | Modelos propostos sem contrato aprovado | `0.3.0-provisional`, sinalizado no manifesto; `synthetic` preserva a proveniência e aceita exportação real compatível, com metadados completos (R1–R8) sem certificar as fórmulas |
| Inspeções | Portal e IA compartilhavam a mesma view | `portal_read.inspecoes` para o portal e projeção independente `ai_read.inspecoes` para a IA, ambas do importador |
| Bootstrap | Importador precisa de novas inspeções, migrações não devem precisar de Gold | init → Alembic operations → importador e views, sem dependência circular |
| Redis | Commit de banco e atualização Redis não são uma transação distribuída | Lock de sessão até terminar Redis, timestamp na publicação e sequência para ordenar cargas; em falha, banco segue sendo a fonte de verdade |

Foram mantidas as decisões de segurança da seção 8 do system design: a IA não
recebe sessão do portal, nem USAGE em analytics/operations, nem criação de objetos.
Sua allowlist inicial contém somente `ai_read.ucs` e `ai_read.inspecoes`, sem dados
pessoais detalhados. Nenhum grant automático a views futuras. O importador tem
INSERT em cargas e SELECT em inspeções, sem escrita nas demais tabelas operacionais.

## Pendências concretas com o time de dados

| Entrega necessária | Validação esperada | Módulos liberados |
|---|---|---|
| Contrato Gold e exportador | Revisão das 12 tabelas, nomes, grãos, chaves, tipos, nulls, manifesto e versão, com amostra real coerente | Importação real e todos os módulos |
| Consumo analítico | Média × mediana, janela de referência, negativos não confirmados, fallback, flag da troca e versão da regra | UC 360, receita, KPIs, fila |
| Receita e volume | Pareamento de faturas/leitura, órfãos e quarentena, tributos, arredondamento, pago/aberto; múltiplas faturas na mesma competência têm regra provisória em 0.3.0-provisional (segregadas, competência sem fatura) | Receita, explicação da conta, KPIs |
| Decomposição | Resolvida na #55/P20: R5 define o grão e a soma dos efeitos por subgrão; rotas de receita publicadas e conferidas com KPIs. | Receita e insights (P20) |
| UC ativa (P05) | Homologar se a presença de registro mensal representa atividade. Se a Gold real publicar a grade UC × competência completa, inclusive sem fatura, o card contará todas as UCs e poderá ficar constante; validar cobertura e disponibilidade de status cadastral histórico | KPIs |
| Grupos de UC | Formalizado em 0.3.0-provisional (R3: regra temporal GD > IRREGULARIDADE > DEMAIS com date_trunc) | Receita, fila e avaliações |
| DEC/FEC/CHI | Sobreposições, interrupções contadas, competência de eventos que cruzam meses, denominador temporal e flag de evento atípico | Operação e KPIs |
| Fila | Score e versão aprovados, motivos, energia em kWh/R$, elegibilidade e comportamento após conclusão/reinspeção | Fila oficial e priorização |
| Inspeções | Domínio de tipos (overview e auditoria divergem), precisão de kWh, normalização canônica e IDs para resultados novos | Planilha de campo e integração definitiva P16 |
| Reconciliação | Conferir os números exploratórios de `diagnostico_receita.md` contra Gold, sem tratá-los como oficiais | Apresentação dos resultados |

Referências consultadas: system design, backlog P01–P07/P10/P12/P16/P18, ADR 0001,
GLOSSARY, fluxo Git, overview, auditorias e diagnóstico na dev; análise de
arquiteturas em `docs/22-analise-arquitetura`; Silver de leituras em
`feat/17-silver-leituras`, ocorrências em `feat/21-silver-ocorrencias-rede` e faturas
no PR #62. Nenhum notebook foi executado ou tabela do Databricks modificada.

P17: fila filtrada e paginada entregue; a aprovação do score pela Gold segue pendente.

## Próximos módulos

1. Aprovar contratos e homologar exportação real com hashes, totais e cobertura.
2. P13/P14 UC 360 e explicação da conta, P20 receita,
   após fechar as regras correspondentes. P22 continuidade (#57) e P24 KPIs (#59)
   implementados; homologação real e cache continuam pendentes.
3. Implementação do agente com executor somente leitura, validação SQL, timeout e
   auditoria; insights compartilham os mesmos serviços de métricas.
4. Cache com versão de carga e invalidação da fila, rate limit por usuário,
   exportação/importação de planilha de campo e frontend/Nginx.

## Correções da revisão do PR #63

O contrato passou para `0.2.0-provisional` por ampliar tarifas para seis casas e
definir arredondamento dos derivados na escala exportada. O importador aceita
`synthetic: false` com os mesmos gates de tipo, chave, referência, hash, totais e
reconciliação; nenhuma exportação Gold real foi fornecida para homologação.
A montagem `GOLD_EXPORT_DIR` permite usar `/entrada` no Compose.

Alembic `0002` atualiza bancos já inicializados: faz backfill da ordem de publicação,
cria `portal_read` e preserva a view existente até a próxima carga. Novas publicações
renovam os default privileges no schema promovido. O downgrade conhecido remove as
views antes das tabelas, sem `CASCADE`. As factories de sessão são criadas no lifespan.

O login verifica Argon2 no pool de threads; tentativas guardam o inspetor no próprio
evento; resultados com data futura são rejeitados. Um período atual válido sem ano
anterior completo retorna comparação indisponível (`None`), mantendo a validação
estrita para comparação explícita. O system design passa a registrar Python 3.12
e o mínimo de FastAPI 0.121. O CI detecta caminhos antes de executar o backend,
mantendo o agregador sempre ativo.

O mapa de issues, critérios atendidos e pendências está em
[`pr-63-criterios.md`](pr-63-criterios.md). O PR conjunto foi autorizado na entrega
original; as correções continuam no mesmo PR, sem reescrever seu histórico.

Os rulesets versionados passam a exigir `CI` e `Fluxo Git`. A reaplicação
administrativa no GitHub com `scripts/configurar-github.sh` fica para o ciclo de
integração/revisão: esta entrega versiona a configuração sem aplicar proteções remotas.

## Evolução no ciclo P02 + P05 (0.3.0-provisional)

1. **Contrato Gold 0.3.0-provisional:**
   - Metadados completos em todas as 12 tabelas e colunas (R1: descrições em português, grãos, unidades e totais).
   - `uc_consumo_faturamento_mensal`: nova coluna `data_vencimento` (date, anulável) e modelagem estrita de competências sem fatura emitida (R2: nulos síncronos e zeramento de volume/valores).
   - Enum estrito de bandeira (`VERDE`, `AMARELA`, `VERMELHA_P1`, `VERMELHA_P2`) e validação de `status_pagamento` × arrecadação.
   - Enum de `metodo_consumo` alinhado à Gold de GD (#94): `LEITURA_UTILIZAVEL` exige consumo analítico igual ao original, e a troca de medidor exige uma das medianas.
   - Faturas múltiplas da mesma UC na competência segregadas, como no #67, com a competência publicada como sem fatura.
2. **Decomposição da Receita (R5):**
   - Fórmula canônica formalizada com fator tributário $k_0$, quatro efeitos (volume, reajuste, bandeira, mix) e fechamento exato em Decimal, pronta para implementação na P20.
3. **Regra Temporal de Grupo de UC (R3):**
   - Precedência canônica GD > Irregularidade Confirmada > Demais com `date_trunc('month', ...)`, auditada pelo gate SQL do importador.
4. **Coerência Cadastral e Fila de Inspeção (R4):**
   - `dim_uc.flag_gd` auditado contra `gd_uc`; exclusão obrigatória de UCs com GD da `fila_inspecao`.
5. **Homologação e Validação (R6, R7, R8):**
   - `reference_date` obrigatória no manifesto com gate temporal em relação ao fechamento do período.
   - Gerador autônomo `contracts/manifesto.py` para execução independente em jobs Databricks.
   - Modo `importador --origem <dir> --verificar` para validação transacional com rollback automático.

- **Receita — contagem de UCs por grupo:** o endpoint `/receita/grupos` não retorna a contagem de UCs solicitada na coluna do mockup; a tela omite essa coluna até existir um contrato para a métrica.
