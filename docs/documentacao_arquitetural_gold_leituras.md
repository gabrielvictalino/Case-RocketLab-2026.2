# Documentação de Arquitetura e Engenharia de Dados

**Projeto:** V-Energy Grid 360
**Domínio:** Leituras de Medição
**Camada:** Gold (Business-Level / Enriched & Aggregated)
**Data da Documentação:** 31 de Outubro de 2026

---

## 1. Visão Geral da Camada

A camada Gold de Leituras atua como a camada de consumo analítico e executivo do projeto, modelada para responder às questões de negócio das lideranças e alimentar o portal e os agentes de Inteligência Artificial com métricas consolidadas.

O objetivo desta etapa é enriquecer as medições higienizadas da camada Silver (`workspace.silver.leituras`) com os atributos cadastrais e de rede das Unidades Consumidoras (`workspace.bronze.unidades_consumidoras`), garantindo a integridade referencial, isolando anomalias de medição para não distorcer agregações de consumo e publicando um dicionário de dados auditável em formato Delta.

---

## 2. Estratégia de Integração, Integridade Referencial e Prevenção de Fan-out (Data Cleansing)

A base de entrada `workspace.silver.leituras` possui exatamente 2.152.336 registos validados (originados de 2.182.468 linhas brutas na Bronze, após a exclusão de 21.523 duplicados exatos e 8.609 clones LTX/MD9… sem medidor cadastrado), garantindo a granularidade estrita de uma leitura por par (`id_uc`, `mes_referencia`).

Durante o cruzamento inicial (`INNER JOIN`) com a tabela `workspace.bronze.unidades_consumidoras` (46.461 linhas brutas), detetou-se um efeito de multiplicação indevida (fan-out) que inflava a tabela enriquecida para 2.212.620 linhas (+60.284 registos duplicados).

A estabilização da camada Gold em exatas 2.152.336 leituras e 45.000 Unidades Consumidoras com histórico de medição fundamentou-se nas seguintes decisões de engenharia:

- **Auditoria de Integridade Referencial (Zero Órfãos):** A validação de chaves entre `silver.leituras` e o cadastro de unidades consumidoras confirmou 0 registos órfãos, assegurando que 100% das leituras pertencem a unidades consumidoras devidamente identificadas.
- **Remoção de Cabeçalhos Espúrios:** O ficheiro bruto de unidades consumidoras continha uma linha de cabeçalho repetida infiltrada no meio dos dados (`id_uc = 'ID_UC'`), que criava categorias inválidas como `'CLASSE'`, `'SUBGRUPO_TARIFARIO'`, `'UF'` e `'STATUS'`. Foi aplicado o filtro `UPPER(TRIM(id_uc)) != 'ID_UC'` para expurgar esse registo.
- **Deduplicação Dimensional de Unidades Consumidoras:** Das 46.461 linhas brutas do cadastro de UCs, identificaram-se 900 cópias exatas em todas as colunas (reduzindo para 45.561 linhas) e 360 repetições de `id_uc` causadas exclusivamente por divergência de grafia em maiúsculas/minúsculas na coluna `nome_titular` (ex.: ADRIANA PADILHA vs. Adriana Padilha), totalizando 45.200 unidades únicas após higienização.
- **Isolamento das Unidades com Medição Efetiva (45.000 UCs):** Ao cruzar as 45.200 UCs únicas com as leituras válidas da Silver, 200 unidades cadastradas (associadas a registos de teste/QA ou sem consumo no período de 2022 a 2026) não possuíam leituras vinculadas, consolidando a base analítica final em exatas 45.000 Unidades Consumidoras ativas e medidas.

---

## 3. Modelagem Analítica, Padronização de Domínios e Regras de Negócio

Para impedir a fragmentação de indicadores nos painéis de gestão e nas consultas da IA, aplicou-se a padronização categórica das dimensões e a separação estrita entre consumo bruto auditável e consumo válido para agregação.

### 3.1 Unificação de Categorias e Acentuação nas Dimensões

- **UF:** Variações como `PE`, `pe`, `P.E.` e `Pernambuco` foram normalizadas exclusivamente para a sigla `PE`.
- **Classe de Consumo:** Aplicação de `UPPER` e `TRIM` combinada com a unificação de acentuação (`PODER PUBLICO` → `PODER PÚBLICO`), estabilizando o domínio em 5 classes (`COMERCIAL`, `INDUSTRIAL`, `PODER PÚBLICO`, `RESIDENCIAL`, `RURAL`).
- **Subgrupo Tarifário e Alimentador:** Padronização em caixa alta (`A4`, `B1`, `B2`, `B3` e códigos de alimentador como `ALM-REC-017`).
- **Município e Tipo de Leitura:** Formatação dos 14 municípios em InitCap (Title Case) e padronização de `tipo_leitura` em `REAL` e `ESTIMADA`.

### 3.2 Regra de Saneamento do Consumo (`consumo_kwh_valido`)

Na camada Silver, 1.334 leituras com sinal invertido confirmado (`flag_sinal_corrigido`) tiveram o sinal corrigido para positivo, enquanto 6.682 leituras negativas foram retidas com o valor original para fins de auditoria:

- 6.215 por reset de troca de medidor (`flag_troca_medidor`);
- 114 por ausência de leitura anterior (`flag_sem_leitura_anterior`);
- 353 por sinal não confirmado em ±1 kWh (`flag_sinal_nao_confirmado`).

Na camada Gold, criou-se o atributo `consumo_kwh_valido`, que preserva as 2.145.654 leituras válidas (`consumo_kwh >= 0`) e atribui `NULL` às 6.682 anomalias negativas, evitando que somas (`SUM`) e médias (`AVG`) sofram deflação artificial.

### 3.3 Estrutura de Tabelas Disponibilizadas na Camada Gold

| Tabela | Linhas | Descrição |
|---|---|---|
| `workspace.gold.f_leituras_enriquecidas` | 2.152.336 | Tabela fato ao nível de leitura, enriquecida com localização, rede elétrica, flags de qualidade (`possui_anomalia_consumo`) e `consumo_kwh_valido`. |
| `workspace.gold.agg_consumo_mensal` | 26.736 | Tabela agregada por `mes_referencia`, `municipio`, `alimentador`, `classe` e `subgrupo_tarifario`, contendo totais de leituras, UCs medidas, consumo total/médio/mínimo/máximo, percentual de leituras estimadas e contagens de flags. |
| `workspace.gold.agg_perfil_consumo_uc` | 45.000 | Visão consolidada do histórico de cada Unidade Consumidora entre 2022 e 2026 (`primeiro_mes_leitura`, `ultimo_mes_leitura`, `qtd_meses_medidos`, `qtd_medidores_distintos`, consumo acumulado/médio e histórico de trocas de medidor). |
| `workspace.gold.dicionario_dados_leituras` | 28 | Catálogo de metadados contendo a descrição funcional de cada coluna/métrica e as decisões de limpeza que a impactam. |

---

## 4. Testes e Atestado de Qualidade (Data Quality)

Em cumprimento aos requisitos de testes automatizados de qualidade no pipeline, executou-se uma bateria de reconciliação cruzada (Silver ↔ Fato Gold ↔ Agregada Mensal ↔ Agregada por UC) validada por asserções (`assert`):

1. **Teste de Conservação de Volume e Granularidade:** O total de leituras em `silver.leituras` (2.152.336) reconciliou exatamente com a contagem de `f_leituras_enriquecidas` (2.152.336), com a soma de `qtd_leituras_total` em `agg_consumo_mensal` (2.152.336) e com a soma de `qtd_meses_medidos` em `agg_perfil_consumo_uc` (2.152.336), comprovando ausência de perda ou duplicação de registos.
2. **Reconciliação Energética Global (kWh):** A soma de energia válida (`consumo_kwh_valido`) fechou em exatos 888.655.666 kWh de forma unânime nas quatro tabelas auditadas (Silver filtrada >= 0, Fato Enriquecida, Mensal e Perfil UC), distribuídos pelas 2.145.654 leituras válidas.
3. **Blindagem contra Valores Negativos:** A auditoria de limites extremos confirmou que o menor consumo considerado válido (`MIN`) em todas as tabelas da camada Gold é de 8 kWh, atestando que nenhuma das 6.682 leituras negativas (`possui_anomalia_consumo = True`) contaminou o cálculo de médias ou totais.
4. **Completude de Dimensões Obrigatórias:** A varredura de nulidade sobre os atributos estruturais (`id_uc`, `mes_referencia`, `municipio`, `uf`, `alimentador`, `classe`, `subgrupo_tarifario`) retornou 0 registos nulos.

---

## 5. Linhagem, Governança e Auditoria (Data Lineage)

**Decisão Arquitetural:** Manteve-se a rastreabilidade ponta a ponta preservando os metadados `source_file` e `ingestion_datetime` (herdados da Bronze e da Silver) na tabela `f_leituras_enriquecidas`, adicionando o carimbo temporal `processed_datetime` nas tabelas agregadas (`agg_consumo_mensal` e `agg_perfil_consumo_uc`) e `published_datetime` na tabela de governança `dicionario_dados_leituras`.
