# Dicionário e Decisões — Camada Gold de Geração Distribuída (`GOLD_GD_V1`)

| Item | Referência |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb` (autocontido; sem módulo `.py` e sem `%run`) |
| **Fontes Silver lidas** | `` `v-energy`.silver.tb_geracao_distribuida ``, `` `v-energy`.silver.tb_unidades_consumidoras ``, `` `v-energy`.silver.tb_leituras `` |
| **Tabelas Gold publicadas** | `` `v-energy`.gold.gd_uc ``, `` `v-energy`.gold.tb_gd_uc ``, `` `v-energy`.gold.tb_gd_consumo_mensal ``, `` `v-energy`.gold.tb_gd_resumo_mensal `` |
| **Versão das regras** | `GOLD_GD_V1` |

---

## 1. Por que a Gold de Geração Distribuída cruza três tabelas da Silver?

Na camada Silver (PR #32), `tb_geracao_distribuida` foi desenhada estritamente com os atributos próprios do cadastro de micro e minigeração (`id_uc`, `potencia_kwp`, `energia_injetada_kwh_media_mensal`, `data_conexao`, `modalidade` e flags de qualidade). Atributos cadastrais (`municipio`, `bairro`, `classe`, `alimentador`) foram mantidos exclusivamente na dimensão de Unidades Consumidoras para evitar divergência de grafia entre tabelas. Além disso, o arquivo de geração distribuída é uma foto cadastral (1 linha por UC, com a média mensal declarada de injeção), e não uma série mensal.

Para responder às perguntas de negócio das lideranças da V-Energy na camada Gold (Star Schema), é indispensável cruzar `tb_geracao_distribuida` com mais duas tabelas da Silver:

1. **`` `v-energy`.silver.tb_unidades_consumidoras `` (Cadastro de UCs):** fornece `municipio`, `bairro`, `classe`, `subgrupo_tarifario`, `alimentador`, `data_ligacao` e `status`. Viabiliza os recortes geográficos e tarifários exigidos pelo Diretor Comercial e pela Diretora de Tecnologia.
2. **`` `v-energy`.silver.tb_leituras `` (Medição Mensal):** fornece a série de consumo mensal (`mes_referencia`, `consumo_kwh`, `tipo_leitura` e flags de anomalia de leitura). Como todas as conexões de GD ocorreram a partir de `2024-01-01` e o histórico de leituras cobre `2022-07` a `2026-06`, o cruzamento permite determinar **em quais competências a GD já estava ativa** (`competencia >= trunc(data_conexao, 'month')`) e medir a queda real de consumo faturado antes e depois da conexão.

> **Nota de coordenação com a equipe:** esta etapa apenas **lê** (em modo *snapshot* `VERSION AS OF`) as tabelas Silver de Unidades Consumidoras (PR #24) e de Leituras (PR #18), sem alterá-las. Os nomes das tabelas de entrada são parametrizados via `dbutils.widgets` no notebook, permitindo apontar para `workspace.default.silver_unidades_consumidoras` ou `venergy.silver.leituras` caso o ambiente ainda utilize os nomes anteriores à unificação.

---

## 2. Quais Perguntas de Negócio cada Tabela Gold Responde?

O quadro abaixo conecta cada uma das 4 tabelas geradas às lideranças da V-Energy (`case_final_rocketlab.md`, seções 4.2, 4.3 e 5.2), às telas do portal e ao Agente de IA:

| Tabela Gold | Grão | Quem usa (Persona / Módulo) | Perguntas de Negócio e Requisitos que Responde |
| :--- | :--- | :--- | :--- |
| **`` `v-energy`.gold.gd_uc ``** | 1 linha por UC com GD (`id_uc`) | **Camila Barreto (Atendimento)** · Tela *Unidade Consumidora (Visão 360)* e Importador (`contracts/tabelas/gd_uc.yaml`) | • *"Esse cliente tem painel solar conectado? Qual a potência instalada e desde quando?"*<br>• Alimenta diretamente o cabeçalho da Visão 360 (`GET /api/v1/ucs/{id_uc}`) e a explicação determinística da conta. |
| **`` `v-energy`.gold.tb_gd_uc ``** | 1 linha por UC com GD (`gd_uc_sk`, `id_uc`) | **Patrícia Lins (TI / Agente IA)**, **Rafael Coutinho (Perdas)** e **Henrique Duarte (Comercial)** | • *"Quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?"* (Patrícia Lins — respondida direto por `WHERE municipio = 'Olinda' AND flag_queda_acima_30_pct = true` $\rightarrow$ **327 de 328 UCs**).<br>• *"Quais UCs tiveram queda brusca de consumo por motivo legítimo (painel solar) e NÃO devem ir para a fila de inspeção de fraude?"* (Rafael Coutinho — evita 3.510 falsos positivos na fila).<br>• *"Quanto cada UC com GD consumia em média/mediana antes da conexão versus depois, e qual a razão entre a queda de consumo e a injeção declarada?"* |
| **`` `v-energy`.gold.tb_gd_consumo_mensal ``** | `UC × competência` (`id_uc`, `competencia`) | **Henrique Duarte (Comercial)**, **Camila Barreto (Atendimento)** e **Agente IA** | • *"Em quais meses específicos esta UC já operava com geração distribuída (`flag_gd_ativa_competencia`)?"* (Impede vazamento temporal ao classificar o `grupo_uc = 'GD'` apenas a partir da competência de conexão).<br>• *"Como evoluiu o consumo mensal da UC antes e depois da instalação do painel solar, separando leitura real, leitura estimada e mês de troca de medidor?"* |
| **`` `v-energy`.gold.tb_gd_resumo_mensal ``** | `competência × município × bairro × classe × modalidade` | **Henrique Duarte (Comercial)** · Telas *Visão Geral* e *Receita* · **Diagnóstico da Receita** | • *"Onde e por que o volume faturado caiu quase 4% entre o primeiro ano e os últimos 12 meses?"* (Mostra que a GD sozinha retirou ~11,1 GWh / −61% nas classes Residencial e Comercial).<br>• *"Qual é o ritmo de novas conexões solares por mês e qual o estoque acumulado de potência ativa (`potencia_instalada_ativa_kwp`) em cada município e bairro?"* |

> A visão consolidada de todas as tabelas Gold do projeto (para que toda a equipe agregue seus domínios num único lugar) está em [`docs/gold/decisoes_silver_to_gold.md`](decisoes_silver_to_gold.md).

---

## 3. Arquitetura e Boas Práticas Aplicadas

- **Modelagem Star Schema e Taxonomia:**
  - Criação de chave substituta inteira sequencial (`gd_uc_sk`) via `F.row_number().over(Window.orderBy('id_uc'))` em `tb_gd_uc` e propagação para a tabela fato `tb_gd_consumo_mensal`.
  - Uso explícito dos sufixos de engenharia no pipeline: `_ctx` (contexto cadastral extraído da UC), `_lk` (lookup enxuto de GD para junção), `_agg` (agregação histórica antes/depois por UC) e `_sk` (Surrogate Key).
  - Prevenção de explosão de granularidade (*fan-out*): validação bloqueante de unicidade das chaves primárias nas três fontes (`id_uc` em GD e Cadastro; `(id_uc, mes_referencia)` em Leituras) antes de qualquer `JOIN`.
- **Idempotência e Proteção Transacional (`VERSION AS OF` e `RESTORE`):**
  - As três fontes Silver têm suas versões Delta fixadas no início da execução.
  - Todas as validações de contrato e reconciliação algébrica rodam **antes** da escrita e **novamente** sobre as tabelas persistidas.
  - Se qualquer escrita ou conferência pós-escrita falhar, `publicar_delta` executa `RESTORE TABLE ... TO VERSION AS OF` (ou `DROP TABLE IF EXISTS` na primeira carga) em todos os destinos afetados.

---

## 4. Regras de Negócio e Decisões Analíticas

### 4.1. Ativação temporal da GD (`flag_gd_ativa_competencia`)
- `competencia` é o primeiro dia do mês de `mes_referencia` (`DATE`, formato `yyyy-MM-01`).
- `competencia_conexao` é `trunc(data_conexao, 'month')`.
- `flag_gd_ativa_competencia` é `true` quando `competencia >= competencia_conexao` e `false` nos meses anteriores à homologação do painel solar.
- Isso atende à pendência #3 do `system-design.md` (evitar vazamento temporal: uma UC conectada em `2025-06` pertence ao grupo `DEMAIS` em `2022–2024` e só passa a ter GD ativa a partir de `2025-06-01`).

### 4.2. Tratamento de leituras com flags impeditivas (troca de medidor e negativas não confirmadas)
Na Silver de leituras (PR #18), os consumos negativos com `flag_sinal_corrigido = true` já tiveram o sinal invertido, mas os registros com `flag_troca_medidor` (6.215 na base, sendo 465 em UCs com GD), `flag_sem_leitura_anterior` (9 em UCs com GD) e `flag_sinal_nao_confirmado` (25 em UCs com GD) permanecem negativos para não mascarar o dado original.
Para conciliar a diretriz da Gold de faturas (PR #67, que não estima consumo oculto) com o requisito da Visão 360 e do Diagnóstico da Receita (que imputam a troca de medidor pela mediana da própria UC), a Gold de GD publica **ambas as métricas lado a lado**:

1. **`consumo_kwh_silver` (`decimal(18,2)`):** valor exato vindo da Silver de leituras (inclusive negativo nos meses de troca), preservado para auditoria.
2. **`volume_analise_kwh` (`decimal(18,2)`, anulável):** igual a `consumo_kwh` somente quando `consumo_kwh >= 0` e nenhuma das três flags impeditivas (`flag_troca_medidor`, `flag_sem_leitura_anterior`, `flag_sinal_nao_confirmado`) está ativa; caso contrário, `NULL`. É 100% compatível com a definição de `volume_analise_kwh` da Gold de faturas (`GOLD_FATURAS_V1`).
3. **`consumo_kwh_analitico` (`decimal(18,2)`):** igual a `volume_analise_kwh` quando utilizável; nos meses bloqueados (como troca de medidor), é imputado pela **mediana das leituras utilizáveis da própria UC na mesma fase (`ANTES_CONEXAO` ou `APOS_CONEXAO`)** — ou pela mediana global da UC se a fase não tiver leitura utilizável. A coluna `metodo_consumo` explicita a origem (`LEITURA_UTILIZAVEL`, `MEDIANA_FASE_UC`, `MEDIANA_HISTORICA_UC`).

> **Por que imputar a mediana dentro da mesma fase (`fase_gd`)?** Porque após a conexão do painel solar o consumo mediano da UC cai de ~290 kWh para ~92 kWh/mês. Como todas as trocas de medidor ocorreram entre `set/2025` e `mar/2026` (quando quase todas as UCs com GD já estavam conectadas), usar a mediana global de 48 meses (dominada pelo período pré-solar de 2022–2024) superestimaria em ~3× o consumo do mês da troca.

### 4.3. Comparação antes × depois da conexão e as 5 UCs sem histórico pré-conexão
- Em `tb_gd_uc`, `consumo_medio_antes_kwh` e `consumo_mediano_antes_kwh` são calculados sobre as competências com `flag_gd_ativa_competencia = false` (usando `volume_analise_kwh` utilizável).
- `consumo_medio_apos_kwh` e `consumo_mediano_apos_kwh` são calculados sobre as competências com `flag_gd_ativa_competencia = true`.
- `queda_consumo_pct` = $\text{round}\left(\frac{\text{consumo\_medio\_antes\_kwh} - \text{consumo\_medio\_apos\_kwh}}{\text{consumo\_medio\_antes\_kwh}} \times 100, 2\right)$.
- `flag_queda_acima_30_pct` = `queda_consumo_pct > 30`.
- **Caso especial das 5 UCs com `fl_data_inconsistente = true`** (`UC100259`, `UC102507`, `UC106046`, `UC110560` e `UC119180`): nessas 5 unidades, `data_conexao` é anterior à `data_ligacao` e ao início das leituras da UC. Por isso, `qtd_leituras_utilizaveis_antes = 0`, `consumo_medio_antes_kwh = NULL` e `flag_queda_acima_30_pct = NULL` (não há base pré-conexão para calcular percentual de queda).
- **Reprodução exata da pergunta da Diretora de Tecnologia:** em **Olinda**, há **328 UCs com GD**, sendo 1 delas a `UC119180` (`fl_data_inconsistente = true`, sem leituras antes da conexão). Das 327 UCs com base antes e depois, todas as **327 tiveram queda de consumo acima de 30%** (`327 de 328`, reproduzindo exatamente o número de `docs/overview_dados/perguntas_negocio.md`).

### 4.4. Calendário mensal de `tb_gd_resumo_mensal`
Conexões novas e estoque ativo **não** são calculados só a partir das leituras. O notebook cruza o cadastro de GD com o calendário mensal contínuo (`sequence` do menor ao maior mês entre competências de leitura e de conexão):

- Toda UC entra em `quantidade_novas_conexoes_mes` no mês de `competencia_conexao`, mesmo sem leitura nesse mês. A soma, em todas as competências, fecha com o total de UCs com GD (**3.510**), inclusive as 5 UCs com `fl_data_inconsistente = true` (`UC100259`, `UC102507`, `UC106046`, `UC110560`, `UC119180`), cuja conexão antecede a primeira leitura.
- `quantidade_ucs_gd_ativas` e `potencia_instalada_ativa_kwp` incluem todos os meses a partir da conexão, com ou sem leitura. Na última competência do calendário, o estoque ativo reproduz as 3.510 UCs e os **31.865,60 kWp** do cadastro.
- Volumes e contagens de leitura continuam vindo só de `tb_gd_consumo_mensal`. Mês sem leitura contribui 0.
- Meses anteriores à conexão só entram no resumo quando existe leitura, para preservar o volume pré-solar.

### 4.5. Impacto no volume entre o primeiro ano (`P0`) e os últimos 12 meses (`P1`)
Na base completa (3.510 UCs com GD, potência instalada corrigida total de **31.865,60 kWp**, sendo **3.127 Residenciais** e **383 Comerciais**):
- **Volume em `P0` (`jul/2022–jun/2023`):** **18,30 GWh** (`18.295.442 kWh`).
- **Volume em `P1` (`jul/2025–jun/2026`):** **7,01 GWh** considerando apenas leituras utilizáveis (−61,7%) ou **7,16 GWh** com a imputação analítica dos meses de troca (−60,9%), confirmando a queda de **~61% (−11,1 GWh)** reportada no Diagnóstico da Receita.

---

## 5. Dicionário das Tabelas Publicadas

### 5.1. `` `v-energy`.gold.gd_uc `` (Contrato do Portal — `contracts/tabelas/gd_uc.yaml`)
**Grão:** 1 linha por UC com GD (`id_uc` único, 3.510 linhas).

| Coluna | Tipo | Nulável | Unidade | Definição |
| :--- | :--- | :---: | :---: | :--- |
| `id_uc` | `string` | Não | — | Identificador da UC (`^UC\d{6}$`) |
| `potencia_kw` | `decimal(18,2)` | Não | kW / kWp | Potência instalada corrigida (`potencia_kwp` da Silver convertida para `decimal(18,2)` conforme contrato do portal) |
| `data_conexao` | `date` | Não | data ISO | Data de conexão do sistema de geração distribuída |

### 5.2. `` `v-energy`.gold.tb_gd_uc `` (Dimensão Analítica Enriquecida de GD por UC)
**Grão:** 1 linha por UC com GD (`gd_uc_sk` e `id_uc` únicos, 3.510 linhas). Serve à Visão 360, à exclusão de falsos positivos da fila de inspeção e às consultas do Agente Text-to-SQL.

| Coluna | Tipo | Nulável | Definição |
| :--- | :--- | :---: | :--- |
| `gd_uc_sk` | `bigint` | Não | Surrogate Key sequencial da dimensão de GD (`row_number` ordenado por `id_uc`) |
| `id_uc` | `string` | Não | Chave natural da UC (`^UC\d{6}$`) |
| `municipio`, `bairro`, `classe` | `string` | Não | Localização e classe tarifária padronizadas vindas da Silver de UC |
| `subgrupo_tarifario`, `alimentador`, `status` | `string` | Não | Subgrupo (`B1`, `B3`), alimentador (`ALM-...`) e status cadastral |
| `data_ligacao` | `date` | Sim | Data de ligação da UC no cadastro |
| `data_conexao` | `date` | Não | Data de conexão da GD |
| `competencia_conexao` | `date` | Não | Primeiro dia do mês de `data_conexao` (`yyyy-MM-01`) |
| `modalidade`, `modalidade_origem` | `string` | Não | Código padronizado (`PROPRIA_UC`, `AUTOCONSUMO_REMOTO`, `COMPARTILHADA`) e texto original |
| `faixa_potencia` | `string` | Não | `ATE_5_KWP`, `DE_5_A_10_KWP`, `DE_10_A_25_KWP` ou `ACIMA_25_KWP` |
| `potencia_kwp` | `decimal(10,2)` | Não | Potência instalada em kWp (após correção de escala na Silver) |
| `energia_injetada_kwh_media_mensal` | `decimal(10,2)` | Não | Média mensal declarada de energia excedente injetada na rede (kWh) |
| `kwh_por_kwp_mes` | `decimal(10,2)` | Não | Produtividade mensal declarada (`energia_injetada / potencia_kwp`) |
| `fl_correcao_escala`, `fl_data_inconsistente`, `fl_deduplicado` | `boolean` | Não | Flags de qualidade herdadas da Silver de GD |
| `qtd_competencias_total`, `qtd_competencias_antes_conexao`, `qtd_competencias_apos_conexao` | `bigint` | Não | Quantidade de competências com leitura na série da UC |
| `qtd_leituras_utilizaveis_antes`, `qtd_leituras_utilizaveis_apos` | `bigint` | Não | Quantidade de leituras com `volume_analise_kwh` válido em cada fase |
| `consumo_medio_antes_kwh`, `consumo_medio_apos_kwh` | `decimal(18,2)` | Sim | Média mensal de consumo utilizável antes e depois da conexão (kWh) |
| `consumo_mediano_antes_kwh`, `consumo_mediano_apos_kwh` | `decimal(18,2)` | Sim | Mediana mensal de consumo utilizável antes e depois da conexão (kWh) |
| `queda_consumo_media_kwh` | `decimal(18,2)` | Sim | Redução absoluta do consumo médio mensal (`antes − após`, em kWh) |
| `queda_consumo_pct` | `decimal(10,2)` | Sim | Redução percentual do consumo médio após a conexão (`%`) |
| `flag_queda_acima_30_pct` | `boolean` | Sim | `true` se `queda_consumo_pct > 30`; `null` se não houver leituras antes da conexão |
| `razao_queda_sobre_injecao` | `decimal(10,4)` | Sim | `queda_consumo_media_kwh / energia_injetada_kwh_media_mensal` |
| `volume_p0_utilizavel_kwh`, `volume_p1_utilizavel_kwh` | `decimal(28,2)` | Não | Volume acumulado em `P0` (`jul/22–jun/23`) e `P1` (`jul/25–jun/26`) sem imputação |
| `volume_p0_analitico_kwh`, `volume_p1_analitico_kwh` | `decimal(28,2)` | Não | Volume acumulado em `P0` e `P1` com imputação pela mediana da fase nos meses bloqueados |
| `versao_regras_gold` | `string` | Não | Constante `GOLD_GD_V1` |

### 5.3. `` `v-energy`.gold.tb_gd_consumo_mensal `` (Fato Mensal `UC × Competência`)
**Grão:** 1 linha por `(id_uc, competencia)` para as UCs com GD (168.083 linhas).

| Coluna | Tipo | Nulável | Definição |
| :--- | :--- | :---: | :--- |
| `gd_uc_sk` | `bigint` | Não | Chave estrangeira para `tb_gd_uc` |
| `id_uc` | `string` | Não | Identificador da UC |
| `mes_referencia` | `string` | Não | Competência no formato `AAAA-MM` |
| `competencia` | `date` | Não | Primeiro dia do mês (`yyyy-MM-01`) |
| `municipio`, `bairro`, `classe`, `subgrupo_tarifario`, `alimentador`, `modalidade`, `faixa_potencia` | `string` | Não | Atributos de recorte analítico |
| `data_conexao`, `competencia_conexao` | `date` | Não | Data de conexão e mês de início da GD |
| `flag_gd_ativa_competencia` | `boolean` | Não | `true` se `competencia >= competencia_conexao` |
| `fase_gd` | `string` | Não | `ANTES_CONEXAO` ou `APOS_CONEXAO` |
| `potencia_kwp`, `energia_injetada_kwh_media_mensal` | `decimal(10,2)` | Não | Potência e injeção média declarada da UC |
| `consumo_kwh_silver` | `decimal(18,2)` | Não | Consumo da Silver de leituras (inclui negativos de troca de medidor) |
| `volume_analise_kwh` | `decimal(18,2)` | Sim | Consumo utilizável (`NULL` quando bloqueado por flag) |
| `consumo_kwh_analitico` | `decimal(18,2)` | Sim | Consumo analítico (imputado pela mediana da fase quando bloqueado) |
| `situacao_volume` | `string` | Não | `VOLUME_POSITIVO`, `ZERO_KWH`, `TROCA_MEDIDOR`, `SEM_LEITURA_ANTERIOR` ou `SINAL_NAO_CONFIRMADO` |
| `metodo_consumo` | `string` | Não | `LEITURA_UTILIZAVEL`, `MEDIANA_FASE_UC`, `MEDIANA_HISTORICA_UC` ou `INDISPONIVEL` |
| `tipo_leitura` | `string` | Não | `REAL` ou `ESTIMADA` |
| `flag_sinal_corrigido`, `flag_troca_medidor`, `flag_sem_leitura_anterior`, `flag_sinal_nao_confirmado` | `boolean` | Não | Flags herdadas da Silver de leituras |
| `versao_regras_gold` | `string` | Não | Constante `GOLD_GD_V1` |

### 5.4. `` `v-energy`.gold.tb_gd_resumo_mensal `` (Agregado Mensal de Evolução e Volume)
**Grão:** `competencia × municipio × bairro × classe × modalidade`.

| Coluna | Tipo | Nulável | Definição |
| :--- | :--- | :---: | :--- |
| `competencia`, `municipio`, `bairro`, `classe`, `modalidade` | `date` / `string` | Não | Chaves do agrupamento |
| `quantidade_ucs_gd_cadastradas` | `bigint` | Não | UCs já conectadas na competência, mais UCs ainda não conectadas que têm leitura naquele mês |
| `quantidade_ucs_gd_ativas` | `bigint` | Não | UCs com `competencia >= competencia_conexao`, contadas pelo cadastro cruzado com o calendário, mesmo sem leitura no mês |
| `quantidade_novas_conexoes_mes` | `bigint` | Não | UCs cuja conexão cai exatamente naquela competência. A soma em todo o resumo é o total de UCs com GD (3.510), com ou sem leitura no mês da conexão |
| `potencia_cadastrada_kwp` | `decimal(28,2)` | Não | Soma da potência da coorte na competência |
| `potencia_instalada_ativa_kwp` | `decimal(28,2)` | Não | Soma da potência das UCs já conectadas na competência, pelo cadastro cruzado com o calendário, mesmo sem leitura no mês |
| `energia_injetada_estimada_ativa_kwh` | `decimal(28,2)` | Não | Soma da injeção média declarada das UCs ativas na competência |
| `quantidade_leituras_utilizaveis`, `quantidade_leituras_bloqueadas` | `bigint` | Não | Contagem de leituras válidas e bloqueadas. A soma é menor ou igual a `quantidade_ucs_gd_cadastradas`; a diferença são UCs já conectadas sem leitura naquele mês |
| `volume_utilizavel_kwh`, `volume_utilizavel_gd_ativa_kwh`, `volume_utilizavel_antes_conexao_kwh` | `decimal(28,2)` | Não | Soma de `volume_analise_kwh` total, pós-conexão e pré-conexão |
| `volume_analitico_kwh`, `volume_analitico_gd_ativa_kwh`, `volume_analitico_antes_conexao_kwh` | `decimal(28,2)` | Não | Soma de `consumo_kwh_analitico` total, pós-conexão e pré-conexão |
| `versao_regras_gold` | `string` | Não | Constante `GOLD_GD_V1` |
