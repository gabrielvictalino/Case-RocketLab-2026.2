# Camada Silver: `inspecoes`

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/bronze_to_silver/bronze-to-silver-inspecoes.ipynb` |
| **Entrada** | `` `v-energy`.bronze.tb_inspecoes `` (1.389 linhas das 3 abas de `inspecoes.xlsx`, tudo em texto) |
| **Saída** | `` `v-energy`.silver.tb_inspecoes `` (1.389 linhas, tipada e padronizada) |
| **Grão** | Uma linha por inspeção de campo (`id_inspecao` único) |
| **Depende de** | Bronze unificada (`Landing_to_Bronze.ipynb`, PR #14) e Silver de cadastro (`` `v-energy`.silver.tb_unidades_consumidoras ``, PR #24) |
| **Usada por** | Golds `inspecoes_historicas` e `fila_inspecao` e a `flag_irregularidade_confirmada` da `dim_uc` |
| **Auditoria de origem** | `docs/auditoria_dados/auditoria_inspecoes.md` |

Substitui o notebook de inspeções do PR #35, que ficava fora de `data-engineering/` e lia `venergy.bronze.inspecoes`, um nome que não existe desde a Bronze unificada. A limpeza do #35 foi mantida. Entraram o padrão das outras Silvers (nomes, pasta, `VERSION AS OF`, `RESTORE`) e as validações da seção 3.

---

## 1. Resumo: o que muda da Bronze para a Silver

| | Bronze | Silver |
| :--- | :--- | :--- |
| `data` | texto em 4 formatos; 107 linhas da aba `dez` são de ago a nov | **`DATE`**, convertida pelo formato de cada valor |
| `resultado` | 8 grafias para 2 status | `IRREGULARIDADE CONFIRMADA` (871) ou `SEM IRREGULARIDADE` (518) |
| `inspetor` | espaços nas pontas: 107 grafias | 40 códigos (`INSP-001` a `INSP-040`) |
| `tipo_irregularidade` | 5 tipos + 4 formas de ausência (vazio, `-`, `NULL`, `N/A`) | 5 tipos ou **nulo** |
| `kwh_recuperado` | texto com vírgula ou ponto decimal | **`DECIMAL(18,2)`**, a escala do contrato |
| Linhagem | `sheet`, `source_file`, `ingestion_datetime` | as mesmas, mais `silver_datetime` |

---

## 2. Regras de transformação

### 2.1. `data` pelo formato de cada valor (achados 2.2 e 3.1)
A auditoria encontrou 4 formatos, todos na aba `dez`. Cada valor é testado contra uma expressão regular e convertido com o formato correspondente:

| Padrão do valor | Formato | Na base |
| :--- | :--- | ---: |
| `^\d{4}-\d{2}-\d{2}$` | `yyyy-MM-dd` | 1.256 |
| `^\d{2}/\d{2}/\d{4}$` | `dd/MM/yyyy` | 43 |
| `^\d{2}\.\d{2}\.\d{4}$` | `dd.MM.yyyy` | 44 |
| `^\d{2}-\d{2}-\d{4}$` | `MM-dd-yyyy` (americano) | 46 |

Nos valores com hífen, a primeira parte nunca passa de 12 e a segunda chega a 31, o que confirma o formato americano. Nos com barra e com ponto é o contrário. Outro formato, ou uma data inexistente como `31/02/2025`, vira nulo e é barrado na validação.

A aba fica só como linhagem (`sheet`), nunca como mês: 107 das 383 linhas da aba `dez` são de agosto (24), setembro (23), outubro (34) e novembro (26).

### 2.2. Texto: `inspetor`, `resultado` e `tipo_irregularidade` (achados 3.2 a 3.4)
* Todas as colunas de texto ficam sem espaços nas pontas e em maiúsculas.
* `resultado`: depois disso, `CONFIRMADA` vira `IRREGULARIDADE CONFIRMADA` e `NADA CONSTA` vira `SEM IRREGULARIDADE`. Um valor fora desse mapa fica como veio e é barrado.
* `tipo_irregularidade`: vazio, `-`, `NULL` e `N/A` viram nulo. A planilha tem 311 células vazias, 77 `-`, 68 `NULL` e 62 `N/A`. Conforme o leitor, `NULL` e `N/A` já chegam nulos na Bronze (`docs/overview_dados/inspecoes.md`); a Silver trata os dois casos.

### 2.3. `kwh_recuperado` como `DECIMAL(18,2)` (achado 3.5)
A vírgula vira ponto, e o valor é convertido com `try_cast`. A base não tem separador de milhar, então a troca não é ambígua. Os 58 valores extremos (acima de Q3 + 3 × IQR, até 15.609,40 kWh) ficam como estão: são recuperações reais de UCs maiores (achado 4.1), e a Gold decide como resumi-los.

### 2.4. Duplicatas e linhagem
As duplicatas exatas (as mesmas 7 colunas da origem, já padronizadas) são removidas, e fica a linha da carga mais antiga. A base atual não tem nenhuma. Um `id_inspecao` repetido com valores diferentes é barrado, porque escolher uma das versões é decisão do negócio.

---

## 3. Validações (gate de qualidade)

Todas as regras rodam antes do `overwrite`. Uma regra **crítica** violada para o notebook, e a Silver atual não é tocada.

| Regra | Nível | Hoje |
| :--- | :--- | ---: |
| `id_inspecao` repetido após remover duplicatas exatas | crítica | 0 |
| `id_inspecao` fora do padrão `^IN\d{7}$` (contrato) | crítica | 0 |
| `id_uc` fora do padrão `^UC\d{6}$` (contrato) | crítica | 0 |
| `id_uc` ausente da Silver de cadastro (integridade referencial) | crítica | 0 |
| `inspetor` fora do padrão `INSP-001` a `INSP-040` (contrato) | crítica | 0 |
| `data` vazia, em formato desconhecido ou inexistente | crítica | 0 |
| `data` no futuro (hoje em `America/Recife`, fixado no início da execução) | crítica | 0 |
| `data` antes do início da base (jul/2022), que pegaria uma data sentinela | crítica | 0 |
| `resultado` fora de `IRREGULARIDADE CONFIRMADA` / `SEM IRREGULARIDADE` | crítica | 0 |
| irregularidade confirmada sem `tipo_irregularidade` | crítica | 0 |
| sem irregularidade com tipo ou `kwh_recuperado` diferente de zero | crítica | 0 |
| `kwh_recuperado` vazio, não convertido ou negativo | crítica | 0 |
| irregularidade confirmada com `kwh_recuperado` zero | aviso | 0 |

As duas regras de coerência são a regra de negócio da base: as 871 inspeções confirmadas têm tipo e kWh maior que zero, e as 518 sem irregularidade não têm tipo e têm kWh zero.

---

## 4. Dicionário de dados: `` `v-energy`.silver.tb_inspecoes ``

| Coluna | Tipo | Nulo? | Descrição |
| :--- | :--- | :---: | :--- |
| `id_inspecao` | STRING | não | Identificador da inspeção (`IN` + 7 dígitos), chave da tabela |
| `id_uc` | STRING | não | UC inspecionada; existe na Silver de cadastro |
| `data` | DATE | não | Data da inspeção (seção 2.1) |
| `inspetor` | STRING | não | Código do inspetor, sem espaços |
| `resultado` | STRING | não | `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE` |
| `tipo_irregularidade` | STRING | sim | Tipo da irregularidade confirmada; nulo quando não houve |
| `kwh_recuperado` | DECIMAL(18,2) | não | Energia recuperada apurada na inspeção (kWh); zero sem irregularidade |
| `sheet` | STRING | não | Aba de origem (só linhagem) |
| `source_file` | STRING | não | Arquivo de origem na landing |
| `ingestion_datetime` | TIMESTAMP | não | Momento da carga na Bronze |
| `silver_datetime` | TIMESTAMP | não | Momento da carga na Silver |

---

## 5. Decisões e alternativas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Ausência de tipo como nulo | Etiqueta `NAO APLICAVEL` | O contrato (`inspecoes_historicas.tipo_irregularidade`) é anulável, e o nulo deixa a regra de coerência direta |
| Aba só como linhagem | Usar a aba como mês | 107 linhas da aba `dez` são de outros meses |
| Valores extremos de kWh mantidos | Remover ou limitar | São recuperações registradas em campo; tirar mudaria o total de energia recuperada |
| Inspeções em domingos e feriados mantidas | Marcar ou remover | O achado 4.2 é um alerta sobre a origem, não um erro que a Silver possa corrigir |
| Gravação pelo widget `confirmar_publicacao` (padrão `false`) | Gravar sempre | Mesmo padrão das Silvers de faturas e atendimentos; o Workflow passa `true` |

---

## 6. Como executar no Databricks

### 6.1. Pré-requisitos
```sql
SELECT COUNT(*) FROM `v-energy`.bronze.tb_inspecoes;               -- esperado: 1389
SELECT COUNT(*) FROM `v-energy`.silver.tb_unidades_consumidoras;   -- esperado: 45000
```
Se faltar alguma, rode antes o `Landing_to_Bronze.ipynb` e a Silver de cadastro.

### 6.2. Rodar o notebook
1. Abra `bronze-to-silver-inspecoes.ipynb` e conecte ao **Serverless**.
2. **Run all** com `confirmar_publicacao = false`: valida e mostra as evidências, sem gravar.
3. Troque o widget para `true` e rode de novo para gravar.

### 6.3. O que conferir
* **Tabela de validação:** 13 regras com `violacoes = 0`.
* **Resumo:** `Bronze: 1389 linhas | Silver: 1389 linhas | duplicatas removidas: 0` e `Confirmadas: 871 | sem irregularidade: 518 | energia recuperada: 1473112.00 kWh | inspetores: 40 | datas: 2025-08-01 a 2025-12-31`.
* **Confirmação final** (com `true`): `` OK: 1389 inspeções carregadas em `v-energy`.silver.tb_inspecoes ``.
* **Evidências:**
  * o mapa de `resultado`;
  * os formatos de data por aba e mês (as 107 linhas da aba `dez` em ago a nov);
  * a coerência resultado × tipo × kWh;
  * os problemas da origem: 83 inspetores com espaço, 125 kWh com vírgula, 133 datas fora do ISO e as ausências de tipo (`tipo_vazio` + `tipo_com_marcador` = 518).

### 6.4. Se a validação falhar
A mensagem lista cada regra crítica violada, e logo acima aparecem até 20 exemplos, com a data como veio da origem e a aba. A Silver anterior **não** foi alterada.

| Regra que falhou | Causa provável | O que fazer |
| :--- | :--- | :--- |
| `data` vazia ou em formato desconhecido | Formato novo na planilha | Incluir o formato em `FORMATOS_DATA` |
| `resultado` fora do domínio | Grafia nova do status | Confirmar com Perdas e incluir em `RESULTADOS` |
| `inspetor` fora do padrão | Inspetor novo (`INSP-041`) | Atualizar o padrão aqui e no contrato |
| `id_uc` fora do cadastro | UC nova ainda não cadastrada, ou erro de digitação | Conferir a UC na Silver de cadastro antes de liberar |
| Coerência resultado × tipo × kWh | Laudo preenchido pela metade | Corrigir na origem; a Silver não completa o laudo |
| `A carga foi desfeita` (depois da escrita) | Erro na própria escrita | A Silver já voltou para a versão anterior; rodar de novo |

### 6.5. No Workflow (Job)
```text
landing_to_bronze ──► bronze_to_silver_unidades_consumidoras ──► bronze_to_silver_inspecoes ──► (Golds de perdas e dim_uc)
```
A tarefa passa o parâmetro `confirmar_publicacao = true`.

---

## 7. Testes realizados

No Spark local (PySpark 4.0.1 + Delta), a Bronze foi montada a partir do `inspecoes.xlsx` como faz o `Landing_to_Bronze`.

| Teste | Resultado |
| :--- | :--- |
| `confirmar_publicacao = false` | Validação OK, nada gravado |
| `confirmar_publicacao = true`, duas vezes | 1.389 linhas nas duas; só o `silver_datetime` muda entre elas |
| 12 erros injetados na Bronze, um por regra (id, UC fora do cadastro, inspetor, data inexistente, data futura, data de 1900, resultado, confirmada sem tipo, sem irregularidade com kWh, kWh inválido, duplicata exata, id repetido com outro valor) | Cada regra acusou o seu; a duplicata exata foi removida sem parar a carga; a Silver não ganhou versão; a Bronze voltou ao original |

No Databricks (Serverless), sobre a `` `v-energy`.bronze.tb_inspecoes `` versão 20:

| Teste | Resultado |
| :--- | :--- |
| `confirmar_publicacao = false` | 13 regras OK; nada gravado |
| `confirmar_publicacao = true` | Silver criada na versão 0, com os mesmos números da execução local. As saídas estão salvas no notebook |

---

## 8. Pendências e pontos que dependem de outras tabelas

* **Golds de perdas:** `inspecoes_historicas` e `fila_inspecao` leem esta Silver.
* **`dim_uc`:** a `flag_irregularidade_confirmada` sai das UCs com pelo menos uma inspeção confirmada (hoje 871).
* **Gold de faturas (#67):** o Job do PR ainda aponta `tabela_inspecoes` para `venergy.silver.inspecoes`. Depois deste PR, o nome é `` `v-energy`.silver.tb_inspecoes ``.
