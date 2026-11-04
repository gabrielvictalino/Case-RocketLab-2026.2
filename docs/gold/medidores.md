# Gold de medidores (`GOLD_MEDIDORES_V1`)

[Índice do dicionário da Gold](decisoes_silver_to_gold.md), domínio 5.

| Item | Referência |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb` (autocontido; sem módulo `.py` e sem `%run`) |
| **Fontes lidas** | `` `v-energy`.silver.tb_medidores `` (PR #22; regras em `docs/silver/silver_medidores.md`) e, na publicação final, `` `v-energy`.gold.dim_uc `` via `tabela_cadastro`, só o `id_uc`, para a referência contratual |
| **Tabelas Gold publicadas** | `` `v-energy`.gold.medidores_historico `` (contrato do portal) e `` `v-energy`.gold.tb_medidores_historico `` (analítica) |
| **Contrato** | `contracts/tabelas/medidores_historico.yaml` (`0.3.0-provisional`), lido pelo notebook a cada execução |
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

As duas têm as mesmas linhas e as mesmas 5 colunas do contrato: a tabela do contrato é um `select` da analítica, e a publicação confere que cada tabela gravada é igual à montada em memória.

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
`ordem_na_uc` segue a mesma ordenação da Silver: data de instalação e, no empate, o medidor com retirada antes do atual. A validação confere cinco coisas:
* exatamente 1 `flag_medidor_atual` por UC;
* o atual é o último da sequência;
* `flag_instalado_em_troca` ⇔ `ordem_na_uc > 1`;
* o medidor anterior é exatamente o da posição anterior e está `RETIRADO`;
* `tipo_medidor_anterior` é a tecnologia do medidor da posição anterior. Ele vem da Silver, e a Gold confere com a própria ordem, como faz com `id_medidor_anterior`: se a Silver desempatar de outro jeito, a carga para em vez de gravar a tecnologia errada.

### 3.4. Competências como data
O contrato usa a competência como **data do primeiro dia do mês** (`AAAA-MM-01`, `contracts/README.md`). `competencia_instalacao`, `competencia_retirada` e `competencia_troca` seguem essa convenção.

### 3.5. Competência da troca
`competencia_troca` é o mês da **retirada do medidor anterior**, e não o da instalação do novo. É o mesmo mês que as leituras marcam com `flag_troca_medidor`: no mês da troca, a leitura já vem com o medidor novo, e o cruzamento com o cadastro é feito por (`id_uc`, mês da retirada) (`docs/silver/silver_leituras.md`, seção 2.5). É ela que cruza com o consumo e com a fatura da UC.

A Silver aceita uma lacuna entre a retirada do anterior e a instalação do novo (aviso, não regra crítica). Com lacuna, a instalação pode cair no mês seguinte. Usar o mês da instalação moveria a troca para esse mês sem erro, e esta Gold discordaria da Gold de consumo. Na base atual, a instalação cai no mesmo dia da retirada nas 6.299 trocas, então `competencia_troca` = `competencia_instalacao`.

### 3.6. Versão das regras
Cada linha da `tb_medidores_historico` grava `versao_regras_gold` (`GOLD_MEDIDORES_V1`), como as tabelas `tb_` da Gold de GD. A tabela do contrato fica só com as 5 colunas do YAML.

### 3.7. Contrato lido do YAML
As colunas (nome, tipo e ordem), a chave, as colunas obrigatórias e o padrão do `id_uc` vêm de `contracts/tabelas/medidores_historico.yaml`, lido a cada execução (widget `contrato_yaml`, relativo à pasta do notebook no Git folder). Os tipos do YAML viram tipos do Spark (`text` → `string`, `numeric(p,s)` → `decimal(p,s)`). Também param a carga um tipo sem equivalente e uma coluna sem `type` ou `nullable` (obrigatórios pela regra R1 do contrato), inclusive uma coluna declarada sem nada embaixo. O `pattern` do `id_uc` é opcional, como no importador: sem ele, a regra do padrão não se aplica.

Quando o YAML mudar (#111), a carga para em vez de passar contra uma cópia antiga no código:
* um tipo ou uma ordem diferente faz falhar a regra de colunas;
* uma coluna que a Gold não gera interrompe a montagem, com a lista das colunas que faltam.

Uma coluna da `tb_` que entrar no contrato passa a sair também na tabela do contrato, na posição do YAML.

### 3.8. `id_uc` no cadastro
O YAML declara `references: [dim_uc, id_uc]`. A `dim_uc` sai da Silver de cadastro, então a Gold confere todo `id_uc` contra `` `v-energy`.silver.tb_unidades_consumidoras ``, como as Golds de GD e de continuidade. Sem essa regra, um medidor de UC removida do cadastro (uma `TESTE*` ou uma duplicata) passaria por todas as regras e só seria barrado no importador, que rejeita a exportação inteira pela chave estrangeira. Na base atual, todo `id_uc` de medidores está no cadastro.

**Publicação final:** o produtor de `dim_uc` foi integrado pelo #145. Depois de executá-lo
no workspace, o Job deve passar `tabela_cadastro` = `` `v-energy`.gold.dim_uc ``,
conferindo a própria tabela da chave estrangeira. O widget conserva o padrão Silver
para compatibilidade com as execuções anteriores; na homologação final é obrigatório
sobrescrevê-lo e depender da tarefa da `dim_uc`. A existência do produtor no Git não
comprova que a tabela foi publicada no workspace. A execução final de medidores com
esse parâmetro ainda precisa de evidência no Databricks.

### 3.9. Leitura e publicação
Mesmo padrão das Golds de GD (#94) e de continuidade (#98):
* **Widgets:** `tabela_medidores`, `tabela_cadastro`, `contrato_yaml`, `schema_gold` e `modo`.
* **Leitura** das Silvers por versão fixa (`VERSION AS OF`).
* **`modo=validar`** (padrão) monta e confere tudo em memória, sem gravar.
* **`modo=publicar`** grava, confere schema e conteúdo gravados e repete as regras do contrato e da analítica sobre as tabelas gravadas.
* **Recuperação:** cada escrita leva o id da execução no `userMetadata` do commit Delta. Se algo falhar, o notebook lê no `DESCRIBE HISTORY` os commits posteriores à versão guardada no início:
  * se forem só desta execução ou de manutenção que não muda dados (`OPTIMIZE`, `VACUUM START` e `VACUUM END`, que o auto compaction e a predictive optimization do Databricks podem gravar logo depois da escrita), a tabela volta à versão anterior com `RESTORE TABLE ... TO VERSION AS OF`, ou é removida na primeira carga. Isso vale também quando a escrita confirmou e a leitura do histórico logo depois falhou;
  * se outra escrita entrou no meio, o `RESTORE` descartaria o commit dela, então o notebook para com os commits de fora na mensagem, para a recuperação manual.
* **Destino:** o schema da Gold não pode ser `silver`, `bronze` ou `default`, e nenhum destino pode ser uma das fontes. As duas conferências ignoram maiúsculas, como o Unity Catalog.

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

### 4.1. Fórmulas das flags e dos indicadores de parque e troca

| Campo / indicador | Fórmula / base | Decisões que afetam o cálculo |
| :--- | :--- | :--- |
| `flag_medidor_atual` | `status = ATIVO`, validado como equivalente a `data_retirada IS NULL` | Sentinela `9999-12-31` anulada na Silver; exatamente um atual por UC |
| `ordem_na_uc` | `row_number()` por UC, ordenado por instalação, retirada (nula por último) e `id_medidor` | Datas tipadas na Silver; cadeia do medidor anterior validada |
| `flag_instalado_em_troca` | `id_medidor_anterior IS NOT NULL`, validado como equivalente a `ordem_na_uc > 1` | A deduplicação e a validação da cadeia evitam trocas artificiais |
| `competencia_instalacao`, `competencia_retirada` | `trunc(data_instalacao, 'month')`, `trunc(data_retirada, 'month')` | Quatro formatos de data tratados; retirada nula mantém competência nula |
| `competencia_troca` | `trunc(data_retirada_do_medidor_anterior, 'month')` | A lacuna entre retirada e nova instalação não desloca a troca para o mês seguinte |
| Medidores atuais por tecnologia | `COUNT(*)` onde `flag_medidor_atual`, agrupado por `tipo_medidor` | 10 grafias padronizadas para três tecnologias; não inclui retirados |
| Trocas por mês / tecnologia substituída | `COUNT(*)` onde `flag_instalado_em_troca`, por `competencia_troca` / `tipo_medidor_anterior` | Conta o medidor que entrou na troca, uma vez; não soma as duas linhas da substituição |

As contagens são consultas derivadas, não colunas adicionais. O parque atual é
um retrato da extração, não um estoque histórico reconstruído mês a mês.
As duas tabelas têm as mesmas instalações: uni-las ou somar suas contagens
duplicaria o parque. A remoção das 513 duplicatas exatas na
[Silver](../silver/silver_medidores.md) evita inflar parque e trocas; nenhuma
tecnologia ou data é corrigida novamente na Gold.

## 5. Validações

Todas as regras são críticas: qualquer violação interrompe a execução com a lista das regras violadas e a quantidade de linhas. As da Silver rodam uma vez, antes da montagem. Em `modo=publicar`, as do contrato e da analítica rodam em memória e de novo sobre as tabelas gravadas.

| Regra | Hoje |
| :--- | :---: |
| **Silver:** `id_medidor` nulo ou fora do padrão, `id_medidor` repetido, `id_uc` nulo, `tipo`/`status` fora do domínio, `data_instalacao` nula, `data_retirada` anterior à instalação, `status` incoerente com `data_retirada`, UC sem exatamente 1 `ATIVO` | 0 |
| **Contrato:** chave (`id_medidor`, `data_instalacao`) repetida | 0 |
| **Contrato:** coluna obrigatória nula | 0 |
| **Contrato:** `id_uc` fora do padrão do YAML (`^UC\d{6}$`) | 0 |
| **Contrato:** `tipo_medidor` fora do domínio | 0 |
| **Contrato:** colunas, tipos ou ordem diferentes do YAML | 0 |
| **Contrato:** linhas diferentes da Silver | 0 |
| **Contrato:** `id_uc` sem cadastro (referência à `dim_uc`) | 0 |
| **Analítica:** UC sem exatamente 1 medidor atual / atual não é o último da UC | 0 |
| **Analítica:** troca incoerente com `ordem_na_uc` | 0 |
| **Analítica:** medidor anterior diferente da ordem ou não `RETIRADO` | 0 |
| **Analítica:** competência diferente do mês da data | 0 |
| **Analítica:** `tipo_medidor_anterior` diferente do tipo do medidor anterior | 0 |
| **Analítica:** `competencia_troca` diferente da retirada do medidor anterior | 0 |
| **Analítica:** linhas diferentes da Silver | 0 |

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
| `RESTORE` só se, depois da versão guardada, houver apenas commits desta execução (marcados no `userMetadata`) e de manutenção | `RESTORE` direto à versão guardada; ou aceitar qualquer commit de escrita | Um `RESTORE` às cegas descartaria o commit de outra tarefa do Job ou de outra pessoa, e o tipo da operação sozinho não separa a escrita desta execução da de outra |
| Contrato lido do YAML a cada execução | Cópia das colunas no notebook | Com o contrato `0.3.0-provisional` e o #111 propondo colunas novas, a cópia passaria a conferir a Gold contra um contrato antigo |
| `id_uc` conferido contra a `dim_uc` na publicação final; Silver apenas no fluxo anterior | Deixar para o importador | O importador rejeita a exportação inteira; a Gold aponta a linha antes de publicar |

---

## 8. Como executar no Databricks

1. **Pré-requisito:** na extração documentada, `` SELECT COUNT(*) FROM `v-energy`.silver.tb_medidores `` → 51.299 e `` SELECT COUNT(*) FROM `v-energy`.gold.dim_uc `` → 45.000. Se não existirem, execute a Bronze/Silvers e o produtor de `dim_uc` (#145), respeitando suas dependências. Esses totais são referências da extração, não constantes para futuras cargas.
2. **Abrir** `silver-to-gold-medidores.ipynb` pelo Git folder do repositório e conectar em **Serverless**. O notebook lê o YAML do contrato pelo caminho relativo; se for importado avulso, informe o caminho do YAML no widget `contrato_yaml`.
3. **Validar:** configure `tabela_cadastro = v-energy.gold.dim_uc` e **Run all** com `modo = validar`. Nada é gravado. Não use o padrão Silver para esta homologação final.
4. **Publicar:** troque o widget `modo` para `publicar` e rode **Run all** de novo.
5. **Conferir:**
   * tabela de regras com 24 linhas `OK`;
   * `[OK] medidores_historico: 51,299 registros` e o mesmo para a `tb_`;
   * a Visão 360 da `UC100015`;
   * o parque atual por tecnologia e as trocas por competência;
   * no fim, `Publicada: ... medidores_historico` e `Publicada: ... tb_medidores_historico`.
6. **No Workflow (#97):** a tarefa depende da Silver de medidores e da Gold `dim_uc`, passando `modo=publicar` e `tabela_cadastro=v-energy.gold.dim_uc`. O Job completo e seu print de sucesso ainda são pendências de integração.
7. **Evidência:** registre commit, parâmetros, data, link/id da execução e versões Delta das duas saídas. Confira a ausência de órfãos e mantenha o print das regras aprovadas. Depois inclua `medidores_historico` no lote consolidado (#96); a tabela analítica `tb_medidores_historico` fica fora do contrato.

```sql
SELECT count(*) AS orfaos
FROM `v-energy`.gold.medidores_historico m
LEFT ANTI JOIN `v-energy`.gold.dim_uc u ON u.id_uc = m.id_uc;
-- Esperado: 0. Conferir também as regras do próprio notebook.
DESCRIBE HISTORY `v-energy`.gold.medidores_historico LIMIT 1;
DESCRIBE HISTORY `v-energy`.gold.tb_medidores_historico LIMIT 1;
```

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
* troca com lacuna (retirada do `MD500015` em 30/09/2025 e instalação do `MD545821` em 01/10/2025, na `UC100015`): as 24 regras passam, e a troca fica em 2025-09, com `competencia_instalacao` em 2025-10;
* `competencia_troca` adulterada numa linha bloqueia a carga pela regra nova;
* cada regra da segunda review bloqueia o defeito que deve bloquear:
  * a `UC100015` fora do cadastro para em `id_uc sem cadastro`;
  * `tipo_medidor_anterior` trocado numa troca para na regra do tipo anterior;
  * `schema_gold = spark_catalog.Silver` é recusado;
  * uma retirada anterior à instalação na Silver para nas regras da Silver;
  * um YAML com outro tipo em `data_retirada` para na regra de colunas, e um YAML com uma coluna nova (`flag_medidor_atual`) leva a coluna para a tabela do contrato;
* cada ponto da terceira review:
  * com um `OPTIMIZE` entre a gravação e a falha, a tabela volta com `RESTORE` à versão anterior;
  * com outra escrita entre a gravação e a falha, o notebook não restaura e para com os commits de fora;
  * na primeira carga, a tabela nova é removida quando a validação reprova e também quando a leitura do histórico logo depois da escrita falha;
  * com `tabela_cadastro` apontando para uma `dim_uc` sem a `UC100015`, a carga para em `id_uc sem cadastro`;
  * um YAML com uma coluna que a Gold não gera para com o nome da coluna, e um sem `nullable` para com o nome da coluna;
  * um YAML sem o `pattern` do `id_uc`, ou com uma só coluna obrigatória, roda as 24 regras;
* a Gold de continuidade do #98 também rodou na mesma cadeia (5.856 linhas).

---

## 10. Pendências

* **Homologação final:** executar a versão revisada em Serverless com `tabela_cadastro=v-energy.gold.dim_uc`, registrar a evidência e incluir a tarefa no Workflow #97. As execuções anteriores documentadas não substituem essa rodada.
* **Contrato provisório:** o YAML está como `provisorio-nao-aprovado`. As colunas da `tb_medidores_historico` (medidor atual, ordem e troca) são uma proposta para a próxima versão (#111), se o portal quiser usá-las direto.
* **Exportação para o banco local:** passo único de exportação do Job (#96).
* **Código de publicação comum:** `publicar_delta`, `qualificar`, `ler_snapshot` e `_contar` estão copiados nas Golds, e só esta tem a recuperação que confere o histórico. A issue #139 leva esse código para um módulo compartilhado.
