# Gold de medidores (`GOLD_MEDIDORES_V1`)

| Item | Referência |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb` (autocontido; sem módulo `.py` e sem `%run`) |
| **Fonte Silver lida** | `` `v-energy`.silver.tb_medidores `` (PR #22; regras em `docs/silver/silver_medidores.md`) |
| **Tabelas Gold publicadas** | `` `v-energy`.gold.medidores_historico `` (contrato do portal) e `` `v-energy`.gold.tb_medidores_historico `` (analítica) |
| **Contrato** | `contracts/tabelas/medidores_historico.yaml` (`0.3.0-provisional`) |
| **Versão das regras** | `GOLD_MEDIDORES_V1` |

---

## 1. A pergunta

A Gerente de Atendimento (Camila Barreto) pede, na seção 4.2 do case, que o atendente veja numa tela só, entre outras coisas, **"o medidor instalado"** na UC. O system design (seção 4.3) detalha: medidor atual no cabeçalho da Visão 360 e histórico de trocas. O mesmo dado ajuda:
* o Gerente de Perdas (Rafael Coutinho), porque a tecnologia do medidor entra na fila de inspeção;
* o Diretor Comercial (Henrique Duarte), porque a campanha de troca para smart (set/2025 a mar/2026) cai dentro do período do diagnóstico de receita.

---

## 2. Duas tabelas: contrato e analítica

A regra de nomes da Gold (`docs/gold/decisoes_silver_to_gold.md`) diz que a tabela do contrato do portal leva o nome do contrato, sem prefixo e só com as colunas dele, e que as tabelas analíticas levam o prefixo `tb_`. É o mesmo par da Gold de GD (`gd_uc` e `tb_gd_uc`).

| Tabela | Colunas | Para quem |
| :--- | :--- | :--- |
| `medidores_historico` | Exatamente as 5 do contrato, na ordem do YAML | Exportação para o Postgres do portal (`analytics.medidores_historico`) |
| `tb_medidores_historico` | As 5 do contrato, 10 derivadas e a versão das regras | Consultas no Databricks e proposta de colunas para a próxima versão do contrato |

As duas têm as mesmas linhas, e uma regra crítica confere que as 5 colunas do contrato são idênticas nas duas.

---

## 3. Regras e decisões

### 3.1. A Gold não muda nenhum valor da Silver
A Silver de medidores já entrega os dados limpos (PR #22):
* 513 duplicatas exatas removidas;
* `tipo` de 10 grafias para 3 valores;
* 4 formatos de data, com hífen = `MM-dd-yyyy`;
* sentinela `9999-12-31` → nulo;
* exatamente 1 medidor `ATIVO` por UC;
* `id_medidor_anterior` nas 6.299 trocas.

A Gold só renomeia `tipo` → `tipo_medidor` (nome do contrato) e `tipo_anterior` → `tipo_medidor_anterior`, e acrescenta colunas derivadas.

### 3.2. Chave do contrato
O contrato define a chave `id_medidor` + `data_instalacao`, que permitiria o mesmo medidor reinstalado em outra data. Na base, `id_medidor` já é único (a Silver bloqueia id repetido), então as duas chaves coincidem. A Gold confere a chave do contrato.

### 3.3. Ordem na UC e medidor atual
`ordem_na_uc` segue a mesma ordenação da Silver: data de instalação e, no empate, o medidor com retirada antes do atual. A validação confere quatro coisas:
* exatamente 1 `flag_medidor_atual` por UC;
* o atual é o último da sequência;
* `flag_instalado_em_troca` ⇔ `ordem_na_uc > 1`;
* o medidor anterior é exatamente o da posição anterior e está `RETIRADO`.

### 3.4. Competências como data
O contrato usa a competência como **data do primeiro dia do mês** (`AAAA-MM-01`, `contracts/README.md`). `competencia_instalacao`, `competencia_retirada` e `competencia_troca` seguem essa convenção.

### 3.5. Competência da troca
`competencia_troca` é o mês da **retirada do medidor anterior**, e não o da instalação do novo. É o mesmo mês que as leituras marcam com `flag_troca_medidor`: no mês da troca, a leitura já vem com o medidor novo, e o cruzamento com o cadastro é feito por (`id_uc`, mês da retirada) (`docs/silver/silver_leituras.md`, seção 2.5). É ela que cruza com o consumo e com a fatura da UC.

A Silver aceita uma lacuna entre a retirada do anterior e a instalação do novo (aviso, não regra crítica). Com lacuna, a instalação pode cair no mês seguinte. Usar o mês da instalação moveria a troca para esse mês sem erro, e esta Gold discordaria da Gold de consumo. Na base atual, a instalação cai no mesmo dia da retirada nas 6.299 trocas, então `competencia_troca` = `competencia_instalacao`.

### 3.6. Versão das regras
Cada linha da `tb_medidores_historico` grava `versao_regras_gold` (`GOLD_MEDIDORES_V1`), como as tabelas `tb_` da Gold de GD. A tabela do contrato fica só com as 5 colunas do YAML.

### 3.7. Leitura e publicação
Mesmo padrão das Golds de GD (#94) e de continuidade (#98):
* **Widgets:** `tabela_medidores`, `schema_gold` e `modo`.
* **Leitura** da Silver por versão fixa (`VERSION AS OF`).
* **`modo=validar`** (padrão) monta e confere tudo em memória, sem gravar.
* **`modo=publicar`** grava, confere schema e conteúdo gravados, repete as validações sobre as tabelas gravadas e, se algo falhar, volta cada tabela com `RESTORE TABLE ... TO VERSION AS OF` (ou a remove, na primeira carga).

---

## 4. Dicionário de dados

### `` `v-energy`.gold.medidores_historico `` (contrato; grão: instalação de medidor)

| Coluna | Tipo | Nulo? | Unidade | Definição | Decisões de limpeza que a afetam (Silver) |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id_medidor` | STRING | não | — | Medidor (**chave**, com `data_instalacao`) | 513 duplicatas exatas removidas; id repetido com conteúdo diferente bloqueia a carga |
| `id_uc` | STRING | não | — | UC onde o medidor está ou esteve (`UC` + 6 dígitos, como o contrato) | Ids em maiúsculas, sem espaços |
| `data_instalacao` | DATE | não | — | Data de instalação na UC (**chave**, com `id_medidor`) | 4 formatos convertidos; hífen = `MM-dd-yyyy` (ler como dia-mês corromperia 469 datas) |
| `data_retirada` | DATE | sim | — | Data de retirada; nula para o medidor atual | Sentinela `9999-12-31` → nulo; nula ⇔ `ATIVO` |
| `tipo_medidor` | STRING | não | — | `ELETRONICO`, `ELETROMECANICO` ou `SMART` | 10 grafias → 3 valores, por regra |

### `` `v-energy`.gold.tb_medidores_historico `` (analítica; grão: instalação de medidor)

As 5 colunas acima e mais:

| Coluna | Tipo | Nulo? | Definição |
| :--- | :--- | :---: | :--- |
| `modelo` | STRING | não | Modelo do medidor (9 modelos, ex.: `EL-3000`) |
| `status` | STRING | não | `ATIVO` (instalado hoje) ou `RETIRADO` |
| `flag_medidor_atual` | BOOLEAN | não | `true` para o medidor instalado hoje (exatamente 1 por UC) |
| `ordem_na_uc` | INT | não | 1 = primeiro medidor da UC, 2 = o que o substituiu… |
| `competencia_instalacao` | DATE | não | Primeiro dia do mês da instalação |
| `competencia_retirada` | DATE | sim | Primeiro dia do mês da retirada; nula no medidor atual |
| `flag_instalado_em_troca` | BOOLEAN | não | `true` se o medidor entrou substituindo outro da mesma UC |
| `competencia_troca` | DATE | sim | Primeiro dia do mês da retirada do medidor anterior (seção 3.5); nula se o medidor não entrou em troca |
| `id_medidor_anterior` | STRING | sim | Medidor substituído por este |
| `tipo_medidor_anterior` | STRING | sim | Tecnologia do medidor substituído |
| `versao_regras_gold` | STRING | não | Versão das regras da Gold que gerou a linha (`GOLD_MEDIDORES_V1`) |

As descrições também ficam gravadas como comentários das colunas no Unity Catalog.

---

## 5. Validações

Todas as regras são críticas: qualquer violação interrompe a execução com a lista das regras violadas e a quantidade de linhas. Em `modo=publicar`, elas rodam em memória e de novo sobre as tabelas gravadas.

| Regra | Hoje |
| :--- | :---: |
| **Silver:** `id_medidor` nulo ou fora do padrão, `id_medidor` repetido, `id_uc` nulo, `tipo`/`status` fora do domínio, `data_instalacao` nula, `status` incoerente com `data_retirada`, UC sem exatamente 1 `ATIVO` | 0 |
| **Contrato:** chave (`id_medidor`, `data_instalacao`) repetida | 0 |
| **Contrato:** coluna obrigatória nula | 0 |
| **Contrato:** `id_uc` fora de `^UC\d{6}$` | 0 |
| **Contrato:** `tipo_medidor` fora do domínio | 0 |
| **Contrato:** `data_retirada` anterior à instalação | 0 |
| **Contrato:** colunas, tipos ou ordem diferentes do YAML | 0 |
| **Contrato:** linhas diferentes da Silver | 0 |
| **Analítica:** UC sem exatamente 1 medidor atual / atual não é o último da UC | 0 |
| **Analítica:** troca incoerente com `ordem_na_uc` | 0 |
| **Analítica:** medidor anterior diferente da ordem ou não `RETIRADO` | 0 |
| **Analítica:** competência diferente do mês da data | 0 |
| **Analítica:** `competencia_troca` diferente da retirada do medidor anterior | 0 |
| **Analítica:** linhas diferentes da Silver | 0 |
| **Analítica:** as 5 colunas do contrato diferentes da tabela do contrato | 0 |

---

## 6. Números da base atual

| Recorte | Valor |
| :--- | :---: |
| Medidores (linhas das duas tabelas) | 51.299 |
| Medidores atuais (1 por UC) | 45.000 |
| Atuais `ELETRONICO` / `ELETROMECANICO` / `SMART` | 25.738 / 10.832 / 8.430 |
| Instalados em troca (todos `SMART`) | 6.299 |
| Tecnologia substituída | 5.661 eletromecânicos, 601 eletrônicos, 37 smart |
| Trocas por `competencia_troca` | 2025-09: 917 · 2025-10: 890 · 2025-11: 905 · 2025-12: 890 · 2026-01: 901 · 2026-02: 873 · 2026-03: 923 |

Exemplo da Visão 360, a `UC100015`:

| `ordem_na_uc` | `id_medidor` | `tipo_medidor` | `modelo` | `data_instalacao` | `data_retirada` | `flag_medidor_atual` |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| 1 | `MD500015` | `ELETROMECANICO` | `EM-1200` | 2019-01-12 | 2025-10-24 | false |
| 2 | `MD545821` | `SMART` | `IQ-900` | 2025-10-24 | — | true |

```sql
-- Visão 360: medidor instalado hoje (tabela analítica)
SELECT id_medidor, tipo_medidor, modelo, data_instalacao
FROM `v-energy`.gold.tb_medidores_historico
WHERE id_uc = 'UC100015' AND flag_medidor_atual;

-- No portal, só com o contrato: o medidor atual é o de data_retirada nula
SELECT id_medidor, tipo_medidor, data_instalacao
FROM analytics.medidores_historico
WHERE id_uc = 'UC100015' AND data_retirada IS NULL;

-- Competência de troca da UC, para marcar no consumo e na fatura
SELECT id_uc, competencia_troca, tipo_medidor_anterior, tipo_medidor
FROM `v-energy`.gold.tb_medidores_historico
WHERE flag_instalado_em_troca;
```

---

## 7. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| Tabela do contrato só com as 5 colunas, na ordem do YAML | Uma tabela só, com colunas extras | O importador exige as colunas exatas; regra de nomes da Gold |
| Colunas derivadas na `tb_medidores_historico` | Deixar o backend derivar | O backend "filtra e agrega, mas não inventa regra" (system design, princípio 1). A `tb_` é a proposta para a próxima versão do contrato (#111). Até lá, o portal não lê a `tb_` e define o medidor atual por `data_retirada` nula, a mesma regra da Gold (`GLOSSARY.md`, "Medidor atual") |
| Competência da troca no mês da retirada do anterior | Mês da instalação do novo; ou bloquear a carga quando os dois meses diferem | É o mês que as leituras usam. A Silver aceita a lacuna como aviso, e bloquear a Gold por ela pararia a carga por um dado que a Silver aceita |
| Competência como data `AAAA-MM-01` | Texto `AAAA-MM` | Convenção do contrato e das outras Golds |
| `tipo` → `tipo_medidor` | Manter o nome da Silver | Nome do contrato |
| Ler a Silver por versão fixa e publicar com `RESTORE` | `overwrite` direto | Mesmo padrão das outras Golds; uma carga reprovada nunca substitui a Gold boa |

---

## 8. Como executar no Databricks

1. **Pré-requisito:** `` SELECT COUNT(*) FROM `v-energy`.silver.tb_medidores `` → 51.299. Se não existir, rode antes a Bronze unificada e a Silver de medidores.
2. **Importar** `silver-to-gold-medidores.ipynb` (Workspace → Import → File, ou pelo Git folder) e conectar em **Serverless**.
3. **Validar:** **Run all** com o widget `modo = validar`. Nada é gravado.
4. **Publicar:** troque o widget `modo` para `publicar` e rode **Run all** de novo.
5. **Conferir:**
   * tabela de regras com 23 linhas `OK`;
   * `[OK] medidores_historico: 51,299 registros` e o mesmo para a `tb_`;
   * a Visão 360 da `UC100015`;
   * o parque atual por tecnologia e as trocas por competência;
   * no fim, `Publicada: ... medidores_historico` e `Publicada: ... tb_medidores_historico`.
6. **No Workflow (#97):** a tarefa depende da Silver de medidores e passa `modo=publicar`.

---

## 9. Testes realizados

A cadeia Bronze → Silver → Gold rodou localmente em Spark 4.0.1 + Delta 4.0.0 (ANSI ligado), com os notebooks **atuais** da `dev` sem modificação. A Bronze das três fontes foi montada com as mesmas opções de leitura da Bronze unificada (#14). Resultados:
* a Silver de medidores dá os 51.299 medidores documentados;
* em `modo=validar`, nada é gravado;
* em `modo=publicar`:
  * as colunas e os tipos da tabela do contrato são exatamente os do YAML;
  * as 51.299 linhas têm chave única;
  * o parque atual, as 6.299 trocas por competência e a `UC100015` conferem com o cálculo independente;
* a reexecução dá o mesmo conteúdo e só uma versão Delta nova;
* defeitos na Silver bloqueiam a carga com a Gold intacta:
  * `id_uc` com 7 dígitos;
  * medidor repetido;
  * tipo fora do domínio;
* troca com lacuna (retirada do `MD500015` em 30/09/2025 e instalação do `MD545821` em 01/10/2025, na `UC100015`): as 23 regras passam, e a troca fica em 2025-09, com `competencia_instalacao` em 2025-10;
* `competencia_troca` adulterada numa linha bloqueia a carga pela regra nova;
* a Gold de continuidade do #98 também rodou na mesma cadeia (5.856 linhas).

---

## 10. Pendências

* **Contrato provisório:** o YAML está como `provisorio-nao-aprovado`. As colunas da `tb_medidores_historico` (medidor atual, ordem e troca) são uma proposta para a próxima versão (#111), se o portal quiser usá-las direto.
* **Exportação para o banco local:** passo único de exportação do Job (#96).
