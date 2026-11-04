# Dicionário de dados da Gold — índice, decisões e perguntas de negócio

Documento vivo e compartilhado pela equipe de Engenharia de Dados para consolidar:
1. **Quais tabelas Gold** compõem o schema `` `v-energy`.gold ``;
2. **Quais tabelas da camada Silver são cruzadas (`JOIN`)** em cada domínio;
3. **Quais perguntas de negócio das lideranças** (`case_final_rocketlab.md`, seções 4.2, 4.3 e 5.2) cada tabela responde;
4. **Quais decisões de limpeza da Silver/Gold afetam os números finais** (requisito obrigatório do dicionário da Gold na seção 5.2.1 do case).

Este é o ponto de entrada do dicionário exigido na seção 5.2.1 do case (#108).
Os documentos de domínio abaixo definem colunas, métricas, fórmulas, nulidades
e decisões de limpeza. Os [YAMLs do contrato](../../contracts/tabelas/) são a
referência de layout, tipos e chaves para a exportação; a versão atual é
`0.3.0-provisional`, ainda não aprovada como contrato completo.

**Como manter:** ao integrar uma Gold, atualize sua linha no inventário e o doc
do domínio no mesmo PR. Registre a fórmula, unidade, grão, comportamento sem
base de cálculo, arredondamento e o tratamento Silver/Gold que muda o indicador.
Os números das bases nos docs são evidências de execuções anteriores, não metas
fixas nem uma verificação do estado atual do Databricks.

---

## 1. Inventário por tabela

**Contrato** identifica cada uma das 12 tabelas de `contracts/tabelas/`, inclusive
as duas pendentes de perdas. **Analítica** identifica saídas fora desse contrato.
Implementada significa que há produtor na `dev`; não comprova publicação ou
homologação de um lote real. Todos os destinos usam o schema padrão
`` `v-energy`.gold ``, configurável nos notebooks.

| Domínio | Tabela / saída lógica | Tipo | Grão | Notebook produtor | Dicionário / situação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. GD | `gd_uc` | Contrato | UC | [GD](../../data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb) | [GD](geracao_distribuida.md) — implementada |
| 1. GD | `tb_gd_uc` | Analítica | UC | [GD](../../data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb) | [GD](geracao_distribuida.md) — implementada |
| 1. GD | `tb_gd_consumo_mensal` | Analítica | UC × competência com leitura | [GD](../../data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb) | [GD](geracao_distribuida.md) — implementada |
| 1. GD | `tb_gd_resumo_mensal` | Analítica | competência × município × bairro × classe × modalidade | [GD](../../data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb) | [GD](geracao_distribuida.md) — implementada |
| 2. Faturamento e receita | `uc_consumo_faturamento_mensal` | Contrato | UC × competência com leitura | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada |
| 2. Faturamento e receita | `receita_volume_mensal` | Contrato | competência × município × bairro × classe × grupo de UC | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada |
| 2. Faturamento e receita | `tb_faturas` → `faturas` | Analítica | fatura elegível | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 2. Faturamento e receita | `tb_faturas_excluidas` → `faturas_excluidas` | Analítica | fatura segregada | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 2. Faturamento e receita | `tb_faturamento_mensal` → `faturamento_mensal` | Analítica | competência × município × bairro × classe × referência | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 2. Faturamento e receita | `consumo_proveniencia` | Analítica de auditoria | UC × competência com leitura | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 2. Faturamento e receita | `complemento_proveniencia` | Analítica de auditoria | fatura elegível | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 2. Faturamento e receita | `cobertura_volume` | Analítica de auditoria | grão comercial × método de consumo × tipo de leitura | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) | [Faturas](faturas.md) — implementada, revisão física |
| 3. Continuidade | `continuidade_alimentador_mensal` | Contrato | alimentador × competência | [Continuidade](../../data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb) | [Continuidade](continuidade.md) — implementada |
| 3. Continuidade | `ocorrencias_uc` | Contrato | ocorrência por UC | [Continuidade](../../data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb) | [Continuidade](continuidade.md) — implementada |
| 3. Continuidade | `dim_alimentador` | Contrato | alimentador | [Continuidade](../../data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb) | [Continuidade](continuidade.md) — implementada |
| 4. Perdas e inspeção | `inspecoes_historicas` | Contrato | inspeção | Pendente na [#124](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/124) | [Perdas](perdas.md) — contrato documentado, produtor pendente |
| 4. Perdas e inspeção | `fila_inspecao` | Contrato | UC candidata | Pendente na [#124](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/124) | [Perdas](perdas.md) — score e estimativas pendentes |
| 5. Cadastro 360 | `dim_uc` | Contrato | UC | [Cadastro](../../data-engineering/silver_to_gold/silver-to-gold-dim-uc.ipynb) | [Cadastro](dim_uc.md) — implementada |
| 5. Cadastro 360 | `medidores_historico` | Contrato | instalação de medidor | [Medidores](../../data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb) | [Medidores](medidores.md) — implementada |
| 5. Cadastro 360 | `tb_medidores_historico` | Analítica | instalação de medidor | [Medidores](../../data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb) | [Medidores](medidores.md) — implementada |
| 5. Cadastro 360 | `atendimentos` | Contrato | protocolo | [Atendimentos](../../data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb) | [Atendimentos](atendimentos.md) — implementada |
| 5. Cadastro 360 | `atendimentos_historico` | Contrato | protocolo × sequência | [Atendimentos](../../data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb) | [Atendimentos](atendimentos.md) — implementada |

### 1.1. Nomes físicos e tabelas técnicas de faturas

O nome sem prefixo do contrato é também o nome do CSV esperado pelo importador.
O prefixo `tb_` distingue as analíticas de GD e medidores. Em faturas, os nomes
`tb_faturas`, `tb_faturas_excluidas` e `tb_faturamento_mensal` são referências
lógicas/legadas: o produtor atual não atualiza esses destinos fixos.
O [notebook de faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb)
usa [gold_faturas.py](../../data-engineering/silver_to_gold/gold_faturas.py) e
[gold_contrato_faturas.py](../../data-engineering/silver_to_gold/gold_contrato_faturas.py)
para publicar as oito saídas de seu domínio como revisões:

| Domínio | Tabela física | Tipo | Grão / finalidade | Notebook / módulo | Doc |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2. Faturamento e receita | `tb_gold_faturas_<nome_logico>_revisao_<uuid>` | Revisão técnica de saída contratual ou analítica | Mesmo grão da respectiva saída acima; oito nomes lógicos, UUID por execução | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) / `publicar_revisoes` | [Faturas](faturas.md) |
| 2. Faturamento e receita | `tb_gold_faturas_publicacao` | Técnica, fora do contrato | Uma linha por saída lógica confirmada, com fonte e versão Delta | [Faturas](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb) / `publicar_revisoes` | [Faturas](faturas.md) |
| 2. Faturamento e receita | `tb_gold_faturas_retencao` | Técnica, fora do contrato | Uma linha por revisão aposentada, com primeira observação fora do marcador | [gold_faturas.py](../../data-engineering/silver_to_gold/gold_faturas.py) / `limpar_revisoes_gold` (manutenção explícita) | [Faturas](faturas.md) |

Leia o marcador uma vez e consuma `fonte`/`versao_fonte`, conforme o protocolo
do doc de faturas. As tabelas técnicas não são indicadores adicionais. A Gold
não publica `tb_variacao_receita`; a decomposição é calculada pelo consumidor.

### 1.2. Fontes e consumidores por domínio

| Domínio | Fontes | Consumidores |
| :--- | :--- | :--- |
| 1. GD | Silver de GD, cadastro e leituras | Comercial, Atendimento, Perdas e Agente IA |
| 2. Faturamento e receita | Marcador/revisões da Silver de faturas, cadastro, leituras, GD, inspeções e medidores; complemento opcional | Comercial, Atendimento e Visão Geral |
| 3. Continuidade | Silver de ocorrências e cadastro | Operação, Atendimento e Visão Geral |
| 4. Perdas e inspeção | Previstas: Silver de inspeções, leituras, cadastro, medidores e GD; Gold `gd_uc` | Perdas e Comercial |
| 5. Cadastro 360 | Silver de cadastro, medidores, atendimentos e inspeções; Gold `gd_uc` e `dim_alimentador` | Atendimento, Perdas, Comercial e Agente IA |

---

## 2. Domínio 1 — Geração Distribuída (`GOLD_GD_V1`)

- **Arquivo:** `data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb` (autocontido; sem módulo `.py`)
- **Dicionário completo:** [`docs/gold/geracao_distribuida.md`](geracao_distribuida.md)

### 2.1. Cruzamentos realizados (`JOIN` entre 3 tabelas Silver)

1. `` `v-energy`.silver.tb_geracao_distribuida `` $\bowtie$ `` `v-energy`.silver.tb_unidades_consumidoras `` por `id_uc`:
   - **Motivo:** a Silver de GD guarda apenas atributos do sistema solar (`potencia_kwp`, `energia_injetada_kwh_media_mensal`, `data_conexao`, `modalidade`). Os recortes geográficos e tarifários (`municipio`, `bairro`, `classe`, `subgrupo_tarifario`, `alimentador`, `data_ligacao`, `status`) vêm exclusivamente da Silver de UCs para evitar divergência de grafia.
2. Resultado acima $\bowtie$ `` `v-energy`.silver.tb_leituras `` por `id_uc`:
   - **Motivo:** o arquivo de GD não é uma série mensal. O cruzamento com as 48 competências de leituras (`2022-07` a `2026-06`) permite determinar em quais competências o painel solar já estava conectado (`competencia >= trunc(data_conexao, 'month')`) e medir a queda real de consumo faturado antes e depois da conexão.

### 2.2. Perguntas de negócio respondidas por cada tabela

#### a) `` `v-energy`.gold.gd_uc `` (Grão: `id_uc` — Contrato do Portal)
- **Quem pergunta:** **Camila Barreto (Gerente de Atendimento)** — Requisito `F3` (Visão 360 da UC).
- **Pergunta que responde:**
  - *"Quando o cliente liga reclamando da conta ou pedindo informações, ele possui painel solar conectado? Qual é a potência instalada e desde que data está conectado?"*
- **Como é consumida:** alimenta diretamente a tabela `analytics.gd_uc` do banco local (`contracts/tabelas/gd_uc.yaml`) e o cabeçalho do endpoint `GET /api/v1/ucs/{id_uc}`.

#### b) `` `v-energy`.gold.tb_gd_uc `` (Grão: `gd_uc_sk` / `id_uc` — Dimensão Analítica de Impacto por UC)
- **Quem pergunta:**
  - **Patrícia Lins (Diretora de Tecnologia)** — Requisito `F8` (Agente Conversacional Text-to-SQL);
  - **Rafael Coutinho (Gerente de Perdas)** — Requisito `F4` (Fila de Inspeção sem falsos positivos);
  - **Henrique Duarte (Diretor Comercial)** — Requisito `F2` (Diagnóstico da Receita).
- **Perguntas que responde:**
  1. *"Quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?"* (Pergunta literal da Diretora Patrícia Lins na seção 4.3 do case).
     - **Resposta direta na tabela:** `SELECT COUNT(*) FROM v-energy.gold.tb_gd_uc WHERE municipio = 'Olinda' AND flag_queda_acima_30_pct = true` $\rightarrow$ **327 UCs** (de um total de 328 UCs com GD em Olinda, sendo 1 sem histórico pré-conexão por ter `fl_data_inconsistente = true`).
  2. *"Quais UCs tiveram queda acentuada de consumo por geração solar legítima e devem ser excluídas ou descontadas na fila de suspeita de fraude?"*
     - **Resposta direta na tabela:** identifica as 3.510 UCs com GD, sua data de conexão, injeção média declarada (`energia_injetada_kwh_media_mensal`) e a razão `razao_queda_sobre_injecao` (~0,91 na mediana), evitando que a fila de inspeção seja inundada por falsos positivos.
  3. *"Qual era o consumo médio e mediano das UCs antes de instalarem painel solar versus depois da conexão?"*
     - **Resposta direta na tabela:** colunas `consumo_medio_antes_kwh`, `consumo_medio_apos_kwh`, `consumo_mediano_antes_kwh` (mediana cai de ~290 para ~92 kWh/mês), `queda_consumo_media_kwh` e `queda_consumo_pct`.

#### c) `` `v-energy`.gold.tb_gd_consumo_mensal `` (Grão: `id_uc × competencia` — Fato Mensal de Consumo em UCs com GD)
- **Quem pergunta:** **Henrique Duarte (Diretor Comercial)** e **Camila Barreto (Gerente de Atendimento)**.
- **Perguntas que responde:**
  1. *"Em uma dada competência (`AAAA-MM-01`), esta UC já tinha geração distribuída ativa ou ainda consumia 100% da rede?"*
     - **Resposta direta na tabela:** coluna `flag_gd_ativa_competencia` (`competencia >= competencia_conexao`) e `fase_gd` (`ANTES_CONEXAO` vs `APOS_CONEXAO`), eliminando vazamento temporal ao classificar grupos de UCs ao longo do tempo (pendência #3 do `system-design.md`).
  2. *"Qual foi o consumo da UC em cada mês, separando o valor bruto da leitura, o volume utilizável sem estimativa e o consumo analítico imputado nos meses de troca de medidor?"*
     - **Resposta direta na tabela:** colunas `consumo_kwh_silver`, `volume_analise_kwh`, `consumo_kwh_analitico`, `situacao_volume` e `metodo_consumo`.

#### d) `` `v-energy`.gold.tb_gd_resumo_mensal `` (Grão: `competencia × municipio × bairro × classe × modalidade`)
- **Quem pergunta:** **Henrique Duarte (Diretor Comercial)** e **Diretoria** — Requisitos `F1`, `F2` e Diagnóstico da Receita (5.2.4).
- **Perguntas que responde:**
  1. *"Por que o volume de energia faturada caiu quase 4% entre o primeiro ano (`P0`: jul/22–jun/23) e os últimos 12 meses (`P1`: jul/25–jun/26)? Onde essa perda se concentra?"*
     - **Resposta direta na tabela:** mostra que as 3.510 UCs com GD caíram de **18,30 GWh** em `P0` para **7,01 GWh** (utilizável) / **7,09 GWh** (analítico) em `P1` (**−61%**, cerca de **−11,2 GWh**), concentradas exclusivamente nas classes `Residencial` (3.127 UCs) e `Comercial` (383 UCs). Medindo volume faturado, o Diagnóstico da Receita atribui à GD ~80% de toda a perda de volume da distribuidora.
  2. *"O ritmo de novas conexões de geração solar está acelerando ou desacelerando? Qual é a potência instalada ativa (`kWp`) acumulada a cada mês por município e bairro?"*
     - **Resposta direta na tabela:** colunas `quantidade_novas_conexoes_mes` (a soma em todas as competências fecha em **3.510**, porque o mês de conexão vem do cadastro cruzado com o calendário mensal, mesmo sem leitura) e `potencia_instalada_ativa_kwp` (estoque em operação que atinge **31.865,60 kWp** na última competência).

### 2.3. Decisões de limpeza que afetam métricas da Gold de GD (Auditoria de Indicadores)

| Decisão na Silver / Gold | Métrica Afetada | Impacto se não fosse tratada |
| :--- | :--- | :--- |
| **Correção de escala em `potencia_kwp` (`÷ 1.000` nas 35 linhas em Wp)** | `potencia_kwp`, `potencia_instalada_ativa_kwp` | Sem a divisão por 1.000 nas 35 UCs registradas em Wp (`3.049,99` a `8.994,91`), a potência instalada total da base saltaria de **31,87 MWp** para **~242 MWp** (+660% de erro). |
| **Conversão de vírgula decimal em `potencia_kwp` (316 linhas)** | `potencia_kwp`, `potencia_instalada_ativa_kwp` | Sem trocar `,` por `.`, 9% das UCs com GD virariam `NULL` e ~1,8 MWp desapareceriam do estoque instalado. |
| **Respeito à competência de conexão (`flag_gd_ativa_competencia`)** | `quantidade_ucs_gd_ativas`, `potencia_instalada_ativa_kwp`, `consumo_medio_antes_kwh` | Sem comparar `competencia >= competencia_conexao`, UCs que só instalaram painel em 2025/2026 seriam contadas como GD ativa já em 2022–2023 (vazamento temporal). |
| **Imputação de meses bloqueados pela mediana da própria fase (`fase_gd`)** | `consumo_kwh_analitico`, `volume_p1_analitico_kwh` | Todas as 465 trocas de medidor em UCs com GD ocorreram entre `set/2025` e `mar/2026` (pós-conexão). Imputar pela mediana global dos 48 meses (dominada pelo consumo pré-solar, 3× maior) inflaria o consumo pós-conexão dessas UCs. |
| **Preservação das 5 UCs com `fl_data_inconsistente = true` sem base pré-conexão** | `flag_queda_acima_30_pct`, `queda_consumo_pct` | As 5 UCs com `data_conexao < data_ligacao` não têm leituras antes da conexão; manter `queda_consumo_pct = NULL` evita divisão por zero ou falsos percentuais, preservando a UC na Visão 360. |
| **Calendário mensal no resumo de GD** | `quantidade_novas_conexoes_mes`, `quantidade_ucs_gd_ativas`, `potencia_instalada_ativa_kwp` | Sem cruzar o cadastro com o calendário, as 5 UCs cuja conexão antecede a primeira leitura somem de `quantidade_novas_conexoes_mes` (3.505 em vez de 3.510) e a potência ativa fica ausente nos meses sem leitura. |

---

## 3. Domínio 2 — Faturamento e Receita (`GOLD_FATURAS_V2`)

- **Notebook:** [silver-to-gold-faturas.ipynb](../../data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb).
- **Dicionário completo:** [faturas.md](faturas.md), com o detalhe das saídas comerciais, as fórmulas, a proveniência e o protocolo de publicação.

- **Tabelas publicadas:** `tb_faturas`, `tb_faturas_excluidas`, `tb_faturamento_mensal` como auxiliares, além de `uc_consumo_faturamento_mensal` e `receita_volume_mensal` do contrato.
- **Perguntas de negócio respondidas:**
  - *Evolução da receita nominal faturada, contas pagas e inadimplência (`valor_em_aberto`, `valor_vencido`, `dias_atraso`) por competência, município, bairro e classe.*
  - *Dados comerciais para a decomposição canônica R5 no consumidor (volume, reajuste, bandeira e mix), sobre o consumo analítico.*
  - *Segregação auditável das faturas com pendência cadastral, UC ausente do cadastro, múltiplas faturas na UC/mês ou sem leitura, preservando a reconciliação com a fonte.*

O volume comercial é o consumo analítico associado à fatura elegível; as
auxiliares usam somente o volume utilizável observado. Tarifa derivada e
arrecadação por status seguem a convenção provisória detalhada no doc. As
revisões também guardam `consumo_proveniencia`, `complemento_proveniencia` e
`cobertura_volume`, para auditar doadores, imputações e cobertura.

---

## 4. Domínio 3 — Continuidade da Rede: DEC, FEC e CHI

- **Arquivo:** `data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb`
- **Dicionário completo:** [`docs/gold/continuidade.md`](continuidade.md), com as regras (seção 3), o dicionário das colunas (seção 4) e os números da base (seção 6)
- **Fontes Silver:** `` `v-energy`.silver.tb_ocorrencias_rede `` $\bowtie$ `` `v-energy`.silver.tb_unidades_consumidoras ``
- **Tabelas publicadas:** `continuidade_alimentador_mensal` (alimentador × competência), `ocorrencias_uc` (ocorrência por UC) e `dim_alimentador` (alimentador).
- **Perguntas de negócio respondidas:**
  - *DEC, FEC e CHI de cada alimentador ao longo do tempo e os piores alimentadores, para direcionar a manutenção preventiva (Beatriz Farias, seção 4.2 do case).*
  - *Interrupções de uma UC na visão 360 (Camila Barreto).*
- **Decisões que afetam os números:** o CHI soma `duracao_efetiva_min`, as interrupções contam só `flag_sobreposicao = false`, o denominador é o número de UCs do alimentador no cadastro e `flag_evento_atipico` só marca as competências do evento, sem removê-las.

---

## 5. Domínio 4 — Perdas Não Técnicas e Fila de Inspeção

- **Situação:** produtor pendente na [#124](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/124); não há notebook Gold de perdas integrado na `dev`.
- **Dicionário:** [perdas.md](perdas.md), com as colunas dos dois contratos, as decisões já conhecidas da Silver e as fórmulas que ainda dependem do produtor.
- **Fontes previstas:** `tb_inspecoes`, `tb_leituras`, `tb_unidades_consumidoras`, `tb_medidores`, `tb_geracao_distribuida` e `gd_uc` para a exclusão obrigatória de GD (R4).
- **Tabelas previstas:** `inspecoes_historicas` (laudos de inspeção e kWh recuperados) e `fila_inspecao` (UC candidata, score, motivos e potencial de recuperação).
- **Perguntas:** quais UCs priorizar para inspeção, por quais sinais e com qual potencial de recuperação (Rafael Coutinho); quais irregularidades já foram confirmadas e quanto foi recuperado (Rafael Coutinho e Henrique Duarte).

Score, pesos, limiar e fórmulas de recuperação ainda não estão definidos na
Gold. Ao integrar a #124, seu PR deve atualizar este inventário e `perdas.md`
com as regras efetivamente implementadas. Os samples do contrato são sintéticos
e não preenchem essa pendência.

---

## 6. Domínio 5 — Cadastro 360, Medidores e Atendimentos

- **Notebook / Módulo:** medidores em `data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb` (`GOLD_MEDIDORES_V1`), atendimentos em `data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb` e cadastro (`dim_uc`) em `data-engineering/silver_to_gold/silver-to-gold-dim-uc.ipynb` (`GOLD_DIM_UC_V1`).
- **Fontes Silver:** `tb_unidades_consumidoras`, `tb_medidores`, `tb_atendimentos` e `tb_inspecoes`
- **Dicionários:** [`docs/gold/medidores.md`](medidores.md), [`docs/gold/atendimentos.md`](atendimentos.md) e [`docs/gold/dim_uc.md`](dim_uc.md)

### 6.1. Medidores: tabelas e perguntas respondidas

#### a) `` `v-energy`.gold.medidores_historico `` (Grão: instalação de medidor — Contrato do Portal)
- **Quem pergunta:** **Camila Barreto (Gerente de Atendimento)**, requisito `F3` (Visão 360 da UC).
- **Pergunta que responde:** *"Qual medidor está instalado na UC, de que tecnologia e desde quando? Ele já foi trocado?"*
- **Como é consumida:** só as 5 colunas do contrato (`id_medidor`, `id_uc`, `data_instalacao`, `data_retirada`, `tipo_medidor`), na ordem do YAML, vão para `analytics.medidores_historico`. O medidor atual é o de `data_retirada` nula.

#### b) `` `v-energy`.gold.tb_medidores_historico `` (Grão: instalação de medidor — Analítica)
- **Quem pergunta:** **Rafael Coutinho (Perdas)** e **Henrique Duarte (Comercial)**.
- **Perguntas que responde:**
  1. *"Quantos medidores de cada tecnologia estão instalados hoje?"* `flag_medidor_atual`: 25.738 eletrônicos, 10.832 eletromecânicos e 8.430 smart.
  2. *"Quando e em quais UCs houve a troca para smart?"* `flag_instalado_em_troca` e `competencia_troca`: 6.299 trocas entre 2025-09 e 2026-03, de 873 a 923 por mês, todas para smart (5.661 eletromecânicos, 601 eletrônicos e 37 smart substituídos). A competência da troca é o mês da retirada do medidor anterior, o mesmo que as leituras marcam com `flag_troca_medidor`, e cruza com o consumo e a fatura da UC.

### 6.2. Decisões de limpeza que afetam as tabelas de medidores

| Decisão na Silver / Gold | Métrica Afetada | Impacto se não fosse tratada |
| :--- | :--- | :--- |
| **Remoção das 513 duplicatas exatas** | medidores por UC, `flag_medidor_atual` | 445 UCs apareceriam com dois medidores ativos, e a Visão 360 mostraria dois "medidores instalados" |
| **Datas com hífen lidas como `MM-dd-yyyy`** | `data_instalacao`, `competencia_instalacao` | Lidas como dia-mês, 761 datas falhariam e 469 seriam gravadas no mês errado, sem erro |
| **Sentinela `9999-12-31` → nulo** | `data_retirada`, medidor atual | 13.649 registros de medidores ativos teriam retirada no ano 9999, e "retirada nula = medidor atual" deixaria de valer |
| **`tipo` padronizado (10 grafias → 3)** | `tipo_medidor`, parque por tecnologia | Um `GROUP BY` mostraria 10 tecnologias, e o parque smart sairia sem os 853 medidores gravados como `smart meter` ou `Smart` |
| **Troca invertida bloqueada (anterior precisa estar `RETIRADO`)** | `id_medidor_anterior`, `flag_instalado_em_troca` | Uma data trocada na origem gravaria a troca ao contrário (o retirado como medidor novo) |

### 6.3. Atendimentos

- **Arquivo:** `data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb`
- **Dicionário completo:** [`docs/gold/atendimentos.md`](atendimentos.md), com as regras (seção 2), o dicionário das colunas (seção 3) e os números da base (seção 5)
- **Fontes Silver:** `` `v-energy`.silver.tb_atendimentos `` $\bowtie$ `` `v-energy`.silver.tb_unidades_consumidoras `` (integridade do `id_uc`)
- **Tabelas publicadas:** `atendimentos` (protocolo) e `atendimentos_historico` (protocolo × sequência).
- **Perguntas de negócio respondidas:**
  - *Os chamados que a UC já abriu, com assunto, nota e a linha do tempo das tratativas, no bloco de chamados da Visão 360 (Camila Barreto, seção 4.2 do case).*
  - *Volume e satisfação por assunto e ao longo do tempo, para o agente de IA (Patrícia Lins).*
- **Decisões que afetam os números:** a nota fica decimal de 1 a 5, como na base, e nula quando o titular não avaliou (#117); o `status` vem da existência de `data_fechamento`; o `assunto` mantém os 6 valores da Silver, sem o subassunto. Em julho de 2025, mês do evento atípico da continuidade, os atendimentos triplicam e a nota média cai de 4,10 para 3,11.

### 6.4. Cadastro (`dim_uc`)

- **Arquivo:** `data-engineering/silver_to_gold/silver-to-gold-dim-uc.ipynb` (`GOLD_DIM_UC_V1`)
- **Dicionário completo:** [`docs/gold/dim_uc.md`](dim_uc.md), com as regras (seção 2), o dicionário das colunas (seção 3) e os números da base (seção 5)
- **Fontes:** `` `v-energy`.silver.tb_unidades_consumidoras `` (UCs e atributos), `` `v-energy`.gold.gd_uc `` (`flag_gd`), `` `v-energy`.silver.tb_inspecoes `` (`flag_irregularidade_confirmada`) e `` `v-energy`.gold.dim_alimentador `` (só conferência)
- **Tabela publicada:** `dim_uc` (UC), a única do contrato com os dados cadastrais; 7 tabelas do contrato a referenciam pelo `id_uc`.
- **Perguntas de negócio respondidas:**
  - *De quem é a UC e onde ela fica?* No cabeçalho da Visão 360 (Camila Barreto, requisito F3): titular, documento mascarado, classe, endereço e alimentador.
  - *Município, bairro, classe e alimentador de cada UC*, os recortes dos filtros do portal, da fila de inspeção, dos KPIs, da receita e do agente de IA.
- **Decisões que afetam os números:** todas as 45.000 UCs do cadastro, sem descarte; município, bairro, classe e alimentador copiados da Silver, porque o importador refaz a receita por esses atributos e a `dim_alimentador` conta as UCs do mesmo cadastro; documento mascarado nos formatos do backend, com o CPF ou CNPJ completo só na Silver; `flag_gd` igual à presença em `gd_uc` (R4), em 3.510 UCs; `flag_irregularidade_confirmada` nas 871 UCs com inspeção confirmada.
