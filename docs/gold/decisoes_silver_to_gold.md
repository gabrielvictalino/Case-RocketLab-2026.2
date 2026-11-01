# Decisões e Perguntas de Negócio — Silver to Gold (V-Energy Grid 360)

Documento vivo e compartilhado pela equipe de Engenharia de Dados para consolidar:
1. **Quais tabelas Gold** compõem o schema `` `v-energy`.gold ``;
2. **Quais tabelas da camada Silver são cruzadas (`JOIN`)** em cada domínio;
3. **Quais perguntas de negócio das lideranças** (`case_final_rocketlab.md`, seções 4.2, 4.3 e 5.2) cada tabela responde;
4. **Quais decisões de limpeza da Silver/Gold afetam os números finais** (requisito obrigatório do dicionário da Gold na seção 5.2.1 do case).

> **Como contribuir (para a equipe):** ao desenvolver ou atualizar o notebook `silver_to_gold` do seu domínio, preencha a respectiva seção abaixo e adicione o link para o dicionário detalhado da sua entrega em `docs/gold/<dominio>.md`.

---

## 1. Visão Consolidada: Domínios da Gold × Fontes Silver × Lideranças Atendidas

| Domínio Gold | Notebook / Módulo | Tabelas Silver Cruzadas (`JOIN`) | Tabelas Gold Publicadas | Lideranças / Módulos Consumidores | Dicionário Detalhado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Geração Distribuída (GD)** | `silver-to-gold-geracao-distribuida.ipynb` | • `tb_geracao_distribuida`<br>• `tb_unidades_consumidoras`<br>• `tb_leituras` | • `gd_uc`<br>• `tb_gd_uc`<br>• `tb_gd_consumo_mensal`<br>• `tb_gd_resumo_mensal` | • **Henrique Duarte** (Comercial)<br>• **Camila Barreto** (Atendimento)<br>• **Rafael Coutinho** (Perdas)<br>• **Patrícia Lins** (TI / Agente IA) | [`docs/gold/geracao_distribuida.md`](geracao_distribuida.md) |
| **2. Faturamento e Receita** | `silver-to-gold-faturas.ipynb`<br>`gold_faturas.py` *(PR #67)* | • `tb_faturas`<br>• `tb_faturas_pendentes_cadastro`<br>• `tb_unidades_consumidoras`<br>• `tb_leituras` | • `tb_faturas`<br>• `tb_faturas_excluidas`<br>• `tb_faturamento_mensal`<br>• `tb_variacao_receita` | • **Henrique Duarte** (Comercial)<br>• **Camila Barreto** (Atendimento)<br>• **Diretoria** (Visão Geral) | `docs/gold/faturas.md` *(em revisão no PR #67)* |
| **3. Continuidade da Rede (DEC/FEC)** | *(a integrar pela equipe)* | • `tb_ocorrencias_rede`<br>• `tb_unidades_consumidoras` | • `continuidade_alimentador_mensal`<br>• `ocorrencias_uc`<br>• `dim_alimentador` | • **Beatriz Farias** (Operação)<br>• **Camila Barreto** (Atendimento) | *(a adicionar)* |
| **4. Perdas e Fila de Inspeção** | *(a integrar pela equipe)* | • `tb_inspecoes`<br>• `tb_leituras`<br>• `tb_unidades_consumidoras`<br>• `tb_medidores`<br>• `tb_geracao_distribuida` | • `inspecoes_historicas`<br>• `fila_inspecao` | • **Rafael Coutinho** (Perdas)<br>• **Henrique Duarte** (Comercial) | *(a adicionar)* |
| **5. Cadastro 360, Medidores e Atendimentos** | *(a integrar pela equipe)* | • `tb_unidades_consumidoras`<br>• `tb_medidores`<br>• `tb_atendimentos`<br>• `tb_geracao_distribuida`<br>• `tb_inspecoes` | • `dim_uc`<br>• `medidores_historico`<br>• `atendimentos`<br>• `atendimentos_historico` | • **Camila Barreto** (Atendimento)<br>• **Patrícia Lins** (TI / Agente IA) | *(a adicionar)* |

**Nomes das tabelas Gold:** cada tabela do contrato do portal leva o nome do contrato, sem prefixo (`gd_uc`, `continuidade_alimentador_mensal`), o mesmo do `<tabela>.csv` que o importador espera (`contracts/tabelas/<tabela>.yaml`). As tabelas analíticas fora do contrato levam o prefixo `tb_` (`tb_gd_uc`, `tb_gd_consumo_mensal`).

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

## 3. Domínio 2 — Faturamento e Receita (`GOLD_FATURAS_V1` — PR #67)

*(Resumo de referência do PR #67 — dicionário completo em `docs/gold/faturas.md` quando integrado)*

- **Tabelas publicadas:** `tb_faturas`, `tb_faturas_excluidas`, `tb_faturamento_mensal`, `tb_variacao_receita`.
- **Perguntas de negócio respondidas:**
  - *Evolução da receita nominal faturada, contas pagas e inadimplência (`valor_em_aberto`, `valor_vencido`, `dias_atraso`) por competência, município, bairro e classe.*
  - *Decomposição da variação de receita entre dois períodos (`efeito_volume`, `efeito_preco_efetivo` e `efeito_receita_sem_volume`).*
  - *Segregação auditável das 32.285 faturas órfãs (`PENDENTE_CADASTRO_SILVER`) e das faturas duplicadas no mesmo mês (`MULTIPLAS_FATURAS_UC_MES`) para não inflar a receita em +1,5%.*

---

## 4. Domínio 3 — Continuidade da Rede: DEC, FEC e CHI *(Espaço para a equipe)*

- **Notebook / Módulo:** *(preencher ao integrar)*
- **Fontes Silver:** `` `v-energy`.silver.tb_ocorrencias_rede `` $\bowtie$ `` `v-energy`.silver.tb_unidades_consumidoras ``
- **Tabelas Gold e perguntas respondidas:** *(preencher com `continuidade_alimentador_mensal`, `ocorrencias_uc` e `dim_alimentador`, detalhando o cálculo com `duracao_efetiva_min`, `flag_sobreposicao` e `flag_evento_atipico`)*.

---

## 5. Domínio 4 — Perdas Não Técnicas e Fila de Inspeção *(Espaço para a equipe)*

- **Notebook / Módulo:** *(preencher ao integrar)*
- **Fontes Silver:** `tb_inspecoes`, `tb_leituras`, `tb_unidades_consumidoras`, `tb_medidores`, `tb_geracao_distribuida`
- **Tabelas Gold e perguntas respondidas:** *(preencher com `inspecoes_historicas` e `fila_inspecao`, detalhando o score de suspeita, a exclusão/desconto das UCs com GD e a estimativa de `energia_recuperar_kwh`)*.

---

## 6. Domínio 5 — Cadastro 360, Medidores e Atendimentos *(Espaço para a equipe)*

- **Notebook / Módulo:** *(preencher ao integrar)*
- **Fontes Silver:** `tb_unidades_consumidoras`, `tb_medidores`, `tb_atendimentos`
- **Tabelas Gold e perguntas respondidas:** *(preencher com `dim_uc`, `medidores_historico`, `atendimentos` e `atendimentos_historico`)*.
