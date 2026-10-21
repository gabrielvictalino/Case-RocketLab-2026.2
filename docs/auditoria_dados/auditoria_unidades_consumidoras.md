# Relatório Técnico de Auditoria: `unidades_consumidoras`
**Camada de Origem:** Landing / Bronze (`venergy.bronze.bronze_unidades_consumidoras`)  
**Data da Auditoria:** 19/10/2026  

---

### 1. Panorama Geral de Volumetria e Integridade
* **Total de linhas brutas na Bronze:** 46.461 registros
* **Cabeçalhos espúrios detectados no corpo do arquivo:** 1 linha (`id_uc = 'id_uc'`)
* **Registros cadastrais válidos:** 46.460 registros
* **Unidades Consumidoras únicas reais (`id_uc`):** 45.200 UCs
* **Linhas duplicadas identificadas:** 1.260 excedentes (2,71% de duplicação cadastral)

---

### 2. Análise de Qualidade e Completude
* **Completude geral:** 15 das 16 colunas possuem **100% de preenchimento** (0% nulos/vazios).
* **Ausência de CEP:** Apenas a coluna `cep` apresentou **520 registros nulos/vazios** (~1,12% da base), além de valores sentinela e datas corrompidas (`9999-12-31`, `-1`, `-`), totalizando ~2,57% de códigos postais inválidos.

---

### 3. Principais Anomalias e Plano de Tratamento para a Camada Silver

1. **Remoção de Linhas de Metadados / Cabeçalho Duplicado:**
   * *Diagnóstico:* Foi identificado um cabeçalho repetido no meio do arquivo.
   * *Ação Silver:* Filtrar explicitamente `id_uc != 'id_uc'`.

2. **Deduplicação Determinística de Chave Primária:**
   * *Diagnóstico:* 1.260 registros representam reenvios idênticos da base.
   * *Ação Silver:* Deduplicar via janela analítica particionando por `id_uc`, priorizando o carimbo de ingestão mais recente (`ingestion_datetime`) e desempate determinístico por `data_ligacao`.

3. **Padronização Categórica (Case-Sensitivity e Acentuação):**
   * *UF:* Identificadas 5 grafias distintas (`PE`, `pe`, `pernambuco`, `P.E.`, `Pernambuco`). Padronizar para a sigla oficial `PE`.
   * *Classe de Consumo:* Mistura de caixas altas/baixas e acentos (`Residencial`, `RESIDENCIAL`, `residencial`, `Poder Publico` vs `Poder Público`). Padronizar em formato Title Case / Capitalizado.

4. **Sanitização de Documentos (`cpf_cnpj`) e Zeros à Esquerda:**
   * *Diagnóstico:* Registros misturam formatos numéricos puros com strings pontuadas (pontos, traços e barras).
   * *Ação Silver:* Limpeza de caracteres especiais e aplicação de `lpad` para preservar zeros à esquerda (11 dígitos para CPF, 14 para CNPJ).