# Referência técnica da Silver de faturas

Os termos de domínio são definidos no [GLOSSARY.md](../../GLOSSARY.md),
incluindo [pendência cadastral](../../GLOSSARY.md#receita) e
[fatura órfã](../../GLOSSARY.md#receita). Este documento conserva o dicionário
dos campos e as regras específicas da implementação; não mantém um glossário
paralelo de termos gerais como JSON, tabela ou Git.

**Evidência de execução:** [publicacao.html](../auditoria_dados/evidencias/faturas-2026-10-29/publicacao.html).

**Versão operacional:** [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb).

O anexo mantém o código e os outputs históricos e contém o Run All com publicação de
29/10/2026. A cópia operacional está sem outputs e isola as futuras revisões
em `v-energy.silver_revisoes`; a versão anterior foi executada com `false` e `true` em 30/10/2026.

## Contrato e verificações

- Uma linha por `id_fatura`, com preenchimento e unicidade exigidos.
- Na principal, ID no padrão `^FT[0-9]{9}$` e correspondência cadastral encontrada.
- Faturas sem cadastro são segregadas e reconciliadas, preservando os IDs FTX.
- Dinheiro em `DECIMAL(18,2)`; energia mais tributos deve ser igual ao total.
- Pagamento inválido não pode passar como ausência legítima: a ausência
  reconhecida possui motivo explícito.
- Emissão usa ISO ou a máscara documentada. Para hífen com ano no fim,
  aplica-se MDY; a ambiguidade original permanece sinalizada.
- Diagnóstico e candidata compartilham as funções de interpretação de datas.
- A candidata é persistida em cache; esse cache não equivale à publicação Delta.
- As comparações de persistência usam todas as colunas e multiplicidade,
  incluindo os metadados da mesma execução.

## Dicionário dos campos

### Campos de negócio

| Campo | Significado | Como foi tratado |
| :--- | :--- | :--- |
| `id_fatura` | Identificador da fatura. | Preservado; `^FT[0-9]{9}$` exigido na principal, com preenchimento e unicidade verificados. |
| `id_uc` | Identificador da unidade consumidora. | Preservado; formato e presença nas referências avaliados. |
| `mes_referencia` | Competência da fatura. | Mantido como texto `AAAA-MM`, sem substituição pelo mês de outra data. |
| `data_emissao` | Emissão interpretada. | DATE conforme representação e convenção adotada. |
| `valor_energia` | Parcela monetária de energia informada. | DECIMAL(18,2), sem inventar quantidade de kWh. |
| `tributos` | Parcela monetária de tributos informada. | DECIMAL(18,2), sem assumir validação de alíquotas legais. |
| `bandeira_tarifaria` | Categoria de bandeira informada pela fonte. | Preservada e verificada no domínio observado; seu adicional não foi recalculado. |
| `valor_total` | Total monetário da fatura. | DECIMAL(18,2), conciliado com energia e tributos. |
| `data_vencimento` | Data informada de vencimento. | DATE ISO. |
| `data_pagamento` | Data real de pagamento, quando informada. | DATE; nulo ou sentinela resultam em ausência com motivo. |
| `status` | Situação informada na extração. | PAGA ou EM ABERTO; não foi transformado em uma posição atual calculada. |

### Indicadores e motivos

| Campo | O que indica | Como interpretar |
| :--- | :--- | :--- |
| `flag_emissao_original_ambigua` | O texto original com hífen admitia duas datas distintas. | Pode ser true mesmo com a data escolhida preenchida. |
| `flag_emissao_fora_competencia` | O mês da emissão escolhida difere da competência. | Não foi usado como motivo automático de exclusão. |
| `flag_pagamento_atrasado` | Pagamento real posterior ao vencimento. | Em fatura sem pagamento, false não quer dizer pagamento em dia; não há data real para comparar. |
| `flag_uc_sem_cadastro` | A UC não foi encontrada na referência cadastral utilizada. | Determina a separação entre principal e pendências neste contrato. |
| `flag_sem_leitura_uc_mes` | O par UC/competência não foi encontrado na referência de leituras. | É uma verificação separada da presença cadastral e da qualidade do consumo. |
| `flag_multiplas_faturas_uc_mes` | Há mais de uma fatura no mesmo par UC/competência. | Não comprova cópia nem define qual cobrança seria válida. |
| `motivo_ausencia_pagamento` | Classifica o motivo de uma data de pagamento ausente. | `CAMPO_NULO` ou `SENTINELA_9999_12_31`; fica nulo quando há pagamento real interpretado. |
| `situacao_referencia_cadastral` | Classificação textual da presença cadastral. | `CADASTRO_ENCONTRADO` ou `PENDENTE_CADASTRO`. |

### Metadados e preservação

| Campo | Significado |
| :--- | :--- |
| `dados_originais` | STRUCT com as onze colunas brutas, antes da tipagem desta Silver. |
| `source_file` | Arquivo registrado como origem da linha, como `faturas.csv`. |
| `ingestion_datetime` | Timestamp de ingestão preservado da Bronze. |
| `metodo_interpretacao_emissao` | Identifica ISO ou a convenção aplicada: `ISO_ANO_MES_DIA`, `CONVENCAO_DMY_BARRAS`, `CONVENCAO_DMY_PONTOS` ou `CONVENCAO_MDY_HIFEN`. |
| `versoes_bronze` | STRUCT com as versões de faturas, cadastro e leituras utilizadas. |
| `versao_regras` | Identificador do conjunto de regras aplicado. |

Os prefixos `_diag_` usados nos DataFrames indicam colunas auxiliares de diagnóstico. Eles não representam, por si só, tabelas persistidas. A candidata seleciona explicitamente os campos que compõem o schema final.

---

## Publicação comprovada

| Destino no catálogo `v-energy` | Versão Delta | Faturas | Valor total |
| :--- | ---: | ---: | ---: |
| `silver.tb_faturas` | 2 | 2.152.336 | R$ 666.482.773,76 |
| `silver.tb_faturas_pendentes_cadastro` | 1 | 32.285 | R$ 10.192.373,82 |

Essas versões foram registradas na execução de 29/10/2026 e podem ser sucedidas
por novas publicações. As comparações completas dos dois destinos passaram;
o conjunto soma 2.184.621 faturas e R$ 676.675.147,58.

O plano usa as versões efetivamente conferidas das revisões de cada execução.
Não existe uma exigência permanente de versão 0. Cada escrita final é uma
transação separada; falhas entre as duas podem produzir publicação parcial.

## Documentos relacionados

- [Auditoria de faturas](../auditoria_dados/auditoria_faturas.md).
- [Textos das seções](textos_secoes_notebook_faturas.md).
- [Operação e revisões](../auditoria_dados/operacao_faturas.md).

## Atualização operacional — 30/10/2026

As execuções com `false` e `true` foram conferidas no código Python da versão operacional no commit `d88ebeb`. A publicação com `true` criou revisões em `silver_revisoes` e publicou `silver.tb_faturas` na versão Delta **3** e `silver.tb_faturas_pendentes_cadastro` na versão **2**. As contagens e os valores foram mantidos. Tabelas referentes a 29/10/2026 neste documento permanecem como histórico.

Consulte o [registro das novas evidências](../auditoria_dados/evidencias_operacionais_faturas.md), com anexos originais, horários, hashes e limites da validação. Os anexos conservam os nomes anteriores à renomeação.


## Correções de publicação — 31/10/2026

O notebook operacional agora inicia com widget salvo em `false`, sem outputs.
Bloqueia divergências de schema, valida IDs das pendências e confirma o par
de snapshots via marcador Delta. Evidências HTML registram somente as execuções
anteriores. O novo código ainda precisa ser executado em catálogo de teste.
Consulte [operação de faturas](../auditoria_dados/operacao_faturas.md).
