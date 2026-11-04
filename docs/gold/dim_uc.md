# Gold `dim_uc` (`GOLD_DIM_UC_V1`)

[Índice do dicionário da Gold](decisoes_silver_to_gold.md), domínio 5.

| Item | Referência |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-dim-uc.ipynb` (autocontido; sem módulo `.py` e sem `%run`) |
| **Fontes** | `` `v-energy`.silver.tb_unidades_consumidoras `` (regras em `docs/silver/silver_unidades_consumidoras.md`), `` `v-energy`.gold.gd_uc `` (`docs/gold/geracao_distribuida.md`), `` `v-energy`.silver.tb_inspecoes `` (`docs/silver/silver_inspecoes.md`) e `` `v-energy`.gold.dim_alimentador `` (`docs/gold/continuidade.md`), esta só para conferência |
| **Tabela publicada** | `` `v-energy`.gold.dim_uc `` (contrato do portal) |
| **Contrato** | `contracts/tabelas/dim_uc.yaml` (`0.3.0-provisional`), lido pelo notebook a cada execução |
| **Usada por** | Backend: fila de inspeção (`perdas`), KPIs, receita, filtros (`meta`) e Visão 360 (`ucs`); view `ai_read.ucs` (`importador/views.sql`), sem titular, documento e endereço; gates R4 e de reconciliação da receita do importador; chaves estrangeiras de 7 tabelas do contrato |
| **Versão das regras** | `GOLD_DIM_UC_V1` |

---

## 1. A pergunta

A Gerente de Atendimento (Camila Barreto) quer, na Visão 360 da UC (requisito F3), saber de quem é a UC e onde ela fica. O cabeçalho mostra titular, CPF/CNPJ mascarado, classe, endereço e alimentador (`docs/system-design.md`, seção 4.3). As outras telas também partem do cadastro:
* a fila de inspeção mostra o município, o bairro e a classe de cada UC;
* os KPIs e a receita filtram por município, bairro, classe e alimentador;
* o agente de IA consulta as UCs por esses recortes.

A `dim_uc` é essa ficha: uma linha por UC, a única tabela do contrato com os dados cadastrais. Sem ela, o importador não carrega o lote, porque sete tabelas do contrato referenciam `dim_uc.id_uc`: `atendimentos`, `fila_inspecao`, `gd_uc`, `inspecoes_historicas`, `medidores_historico`, `ocorrencias_uc` e `uc_consumo_faturamento_mensal`.

## 2. Regras e decisões

### 2.1. Uma linha por UC do cadastro, sem descarte

A `dim_uc` tem exatamente as UCs da Silver de cadastro: hoje, 45.000. As Golds de medidores, atendimentos e continuidade conferem o `id_uc` contra a Silver de cadastro e supõem que a `dim_uc` tem as mesmas UCs (premissa registrada no #106). Uma UC descartada aqui passaria por essas conferências e faria o importador rejeitar o lote inteiro pela chave estrangeira. O notebook para se faltar ou sobrar qualquer UC em relação ao cadastro.

### 2.2. Atributos copiados sem mudança

Titular (`nome_titular` na Silver), município, bairro, classe e alimentador vêm da Silver como estão. A Silver já os padronizou: classe nos 5 valores do contrato, bairros com o encoding corrigido e alimentador no padrão `ALM-<MUN>-<NNN>` (`docs/silver/silver_unidades_consumidoras.md`, seção 7). Há dois motivos para a Gold não mexer neles:
* o importador refaz a `receita_volume_mensal` por competência, município, bairro, classe e grupo de UC, juntando a `uc_consumo_faturamento_mensal` com a `dim_uc`. A Gold de faturas agrega com os atributos da Silver de cadastro; um bairro grafado de outro jeito aqui quebraria essa reconciliação;
* a `dim_alimentador` (Gold de continuidade) conta as UCs de cada alimentador na mesma Silver (seção 2.7).

Hoje são 14 municípios, 5 classes, 122 alimentadores e 272 nomes de bairro, que formam 297 pares município × bairro: o mesmo nome existe em mais de um município (`Centro` aparece em 10). Um filtro por bairro precisa vir junto com o município, como na lista de filtros do backend (`SELECT DISTINCT municipio, bairro`).

### 2.3. Documento mascarado

| Documento | Máscara | Exemplo |
| :--- | :--- | :--- |
| CPF (11 dígitos) | `***.ddd.ddd-**` | `123.456.789-09` vira `***.456.789-**` |
| CNPJ (14 dígitos) | `**.ddd.ddd/dddd-**` | `12.345.678/0001-95` vira `**.345.678/0001-**` |

São os dois formatos que o `mascarar_documento` do backend (`backend/app/modules/ucs/service.py`) devolve sem mascarar de novo; um documento mascarado em outro formato viraria `***` na tela. O CPF ou CNPJ completo fica só na Silver. A view da IA, `ai_read.ucs`, não expõe titular, documento nem endereço. Hoje são 38.992 CPFs e 6.008 CNPJs.

### 2.4. Endereço

`endereco` é o logradouro seguido do número, separados por vírgula, como na amostra do contrato (`Rua fictícia, 0`). Sem número, fica só o logradouro. Sem logradouro, o notebook para: o contrato não aceita endereço vazio, e a Gold não inventa texto. Hoje as 45.000 UCs têm logradouro e número. Município e bairro já são colunas próprias e não se repetem no endereço; CEP e UF ficam de fora, porque o contrato não os pede.

### 2.5. `flag_gd`: presença em `gd_uc` (R4)

`true` para as UCs de `gd_uc` (Gold de GD): hoje, 3.510. É o gate R4 do importador, que reprova o lote se a flag divergir de `gd_uc` em qualquer sentido, inclusive se uma UC de `gd_uc` estiver fora da `dim_uc`. A flag é o retrato de hoje. A regra temporal do grupo de UC (R3, GD a partir do mês de conexão) fica na `uc_consumo_faturamento_mensal`, que usa a `data_conexao` de `gd_uc`.

### 2.6. `flag_irregularidade_confirmada`: alguma inspeção confirmada

`true` para as UCs com pelo menos uma inspeção `IRREGULARIDADE CONFIRMADA` na Silver de inspeções: hoje, 871, com uma inspeção por UC na base. Uma UC continua com a flag mesmo que uma inspeção posterior não ache nada, porque o contrato descreve um histórico ("possui histórico de irregularidade confirmada"). É a mesma fonte da `inspecoes_historicas`, que a Gold de perdas (#124) copia da Silver, sem depender da ordem das Golds. Como a `flag_gd`, é retrato: o grupo de UC temporal da R3 usa a data da primeira inspeção confirmada.

As duas flags são independentes: hoje 1 UC tem as duas. Na R3, a GD tem precedência.

### 2.7. Mesma versão do cadastro que a `dim_alimentador`

`dim_uc.alimentador` referencia a `dim_alimentador` (chave estrangeira do contrato), e o gate R4 do importador exige que o `numero_ucs` da continuidade seja o da `dim_alimentador`. As duas dimensões saem da Silver de cadastro. Se uma Gold rodar sobre uma versão do cadastro e a outra sobre outra, as UCs por alimentador divergem. O notebook lê a `dim_alimentador` publicada e para se algum alimentador tiver outro número de UCs: é o sinal de que a Gold de continuidade precisa rodar de novo sobre o mesmo cadastro. O mesmo cuidado vale para a Gold de faturas, que usa o município, o bairro e a classe do cadastro. O coordenador do lote (#96) vai garantir que todas as Golds leram as mesmas versões (`docs/gold/faturas.md`, "Exportação, manifesto e montagem do lote").

### 2.8. Contrato lido do YAML

Colunas, tipos, ordem e chave vêm de `contracts/tabelas/dim_uc.yaml` a cada execução, como na Gold de medidores, e também as regras de cada valor: obrigatória, texto não vazio, `pattern` do `id_uc` e do `alimentador` e `enum` da `classe`. A Gold confere, antes de gravar, o que o importador vai cobrar (função `parse` de `importador/src/importador/contracts.py`). O `pattern` precisa casar o valor inteiro, como o `re.fullmatch` do importador. As `description` do YAML viram os comentários das colunas no catálogo.

### 2.9. Leitura e publicação

As quatro fontes são lidas com `VERSION AS OF` da versão do início da execução. O padrão `modo=validar` não grava nada; `modo=publicar` grava com o id da execução no `userMetadata` do commit Delta, confere a tabela gravada e, se algo falhar, restaura o destino. O código de publicação é o mesmo da Gold de medidores (#105), até o módulo comum de publicação (#139).

## 3. Dicionário de dados

### `` `v-energy`.gold.dim_uc `` (grão: UC)

| Coluna | Tipo | Nulo | Origem | Descrição |
| :--- | :--- | :---: | :--- | :--- |
| `id_uc` | `string` | Não | `id_uc` | Identificador da UC (`UC` + 6 dígitos). Chave primária |
| `titular` | `string` | Não | `nome_titular` | Nome do titular |
| `documento_mascarado` | `string` | Não | `cpf_cnpj` | CPF ou CNPJ mascarado (seção 2.3) |
| `endereco` | `string` | Não | `logradouro`, `numero` | Logradouro e número (seção 2.4) |
| `municipio` | `string` | Não | `municipio` | Município (14) |
| `bairro` | `string` | Não | `bairro` | Bairro (272 nomes, 297 pares com o município) |
| `classe` | `string` | Não | `classe` | `Residencial`, `Comercial`, `Industrial`, `Rural` ou `Poder Público` |
| `alimentador` | `string` | Não | `alimentador` | Alimentador (`ALM-<MUN>-<NNN>`), presente na `dim_alimentador` |
| `flag_gd` | `boolean` | Não | `gd_uc` | UC com geração distribuída (seção 2.5) |
| `flag_irregularidade_confirmada` | `boolean` | Não | `tb_inspecoes` | UC com irregularidade confirmada em inspeção (seção 2.6) |

### 3.1. Fórmulas das flags e das contagens cadastrais

| Campo / indicador | Fórmula / base | Decisões que afetam o cálculo |
| :--- | :--- | :--- |
| `flag_gd` | `EXISTS(gd_uc WHERE gd_uc.id_uc = dim_uc.id_uc)` | R4 confere a equivalência nos dois sentidos; é retrato cadastral |
| `flag_irregularidade_confirmada` | Existência de ao menos uma inspeção da UC com `resultado = IRREGULARIDADE CONFIRMADA` | Resultado padronizado na Silver; inspeção posterior sem irregularidade não apaga o histórico |
| UCs por município, bairro, classe ou alimentador | `COUNT(*)` na `dim_uc`, agrupado pelos recortes | Chave única e todas as UCs da Silver, sem descartar inativas ou sem leitura; bairro deve ser combinado com município |
| UCs com GD / irregularidade / ambas | `COUNT(*)` filtrado por cada flag, ou pelo `AND` delas | As flags são independentes; somar os dois totais conta duas vezes UCs na interseção |

As contagens são indicadores derivados em consulta, não novas tabelas Gold.
A limpeza da [Silver de cadastro](../silver/silver_unidades_consumidoras.md)
(duplicatas, cadastros de teste, classes e bairros padronizados) define a base
das contagens e o denominador da continuidade. A Gold não refaz essa limpeza.
Para receita por mês, use `grupo_uc` temporal do detalhe comercial: estas flags
atuais não informam a situação da UC em todas as competências anteriores.

## 4. Validações

Todas param o notebook antes de gravar. As regras da tabela se repetem sobre a tabela gravada, com `RESTORE` em caso de falha.

| Grupo | Regras |
| :--- | :--- |
| **Fontes** | colunas usadas presentes; `id_uc` do cadastro não nulo e sem repetição; documento com 11 (CPF) ou 14 (CNPJ) dígitos e `tipo_documento` coerente com o tamanho; logradouro preenchido; resultado das inspeções no domínio; `id_uc` de `gd_uc` sem repetição; UCs de `gd_uc` e das inspeções presentes no cadastro; alimentador da `dim_alimentador` sem repetição |
| **Contrato** (do YAML) | colunas, tipos e ordem; chave `id_uc` única; obrigatórias não nulas; textos não vazios; `id_uc` e `alimentador` no `pattern`; `classe` no `enum` |
| **Cadastro** | nenhuma UC a mais ou a menos que a Silver; titular, município, bairro, classe e alimentador iguais aos da Silver; máscara no formato do backend, com os dígitos visíveis iguais aos do documento da Silver |
| **Flags** | `flag_gd` igual à presença em `gd_uc` nos dois sentidos (R4); `flag_irregularidade_confirmada` igual às UCs com inspeção confirmada nos dois sentidos |
| **Alimentadores** | todo alimentador na `dim_alimentador`; UCs por alimentador iguais ao `numero_ucs` da `dim_alimentador` |

## 5. Números da base atual

| Item | Valor |
| :--- | :--- |
| UCs | 45.000 (38.992 com CPF e 6.008 com CNPJ) |
| Classes | Residencial 38.336, Comercial 4.909, Industrial 877, Rural 656, Poder Público 222 |
| Municípios, bairros e alimentadores | 14 municípios, 272 nomes de bairro (297 pares município × bairro), 122 alimentadores |
| `flag_gd` | 3.510 UCs (3.127 residenciais e 383 comerciais) |
| `flag_irregularidade_confirmada` | 871 UCs (582 residenciais, 287 comerciais, 1 industrial e 1 rural) |
| Com as duas flags | 1 UC |

## 6. Decisões e alternativas

| Decisão | Alternativa | Por que não |
| :--- | :--- | :--- |
| Todas as UCs do cadastro | Tirar UCs inativas ou sem leitura | As outras Golds referenciariam UCs ausentes, e o importador rejeitaria o lote |
| Atributos copiados da Silver | Padronizar de novo na Gold | Quebraria a reconciliação da receita por grão e a contagem da `dim_alimentador` |
| Documento nos formatos do backend | Hash SHA-256 (proposta do #106) | O contrato e a Visão 360 pedem o documento mascarado, e um hash de CPF sem salt se desfaz por força bruta (review do #106) |
| Endereço com logradouro e número | Incluir bairro, município e CEP | Bairro e município já são colunas; o contrato não pede CEP |
| Flag de irregularidade da Silver de inspeções | Ler a `inspecoes_historicas` (Gold de perdas) | Mesma informação, sem depender da ordem das Golds |
| Conferir a `dim_alimentador` publicada | Supor que todas as Golds leram o mesmo cadastro | O importador rejeitaria o lote; a Gold aponta a divergência antes de publicar |
| Contrato lido do YAML | Copiar as colunas no código | Uma mudança no contrato chega à Gold sem editar o notebook |

## 7. Como executar no Databricks

1. **Pré-requisito:** as fontes publicadas.

   ```sql
   SELECT COUNT(*) FROM `v-energy`.silver.tb_unidades_consumidoras;  -- esperado: 45000
   SELECT COUNT(*) FROM `v-energy`.gold.gd_uc;                       -- esperado: 3510
   SELECT COUNT(*) FROM `v-energy`.silver.tb_inspecoes;              -- esperado: 1389
   SELECT COUNT(*) FROM `v-energy`.gold.dim_alimentador;             -- esperado: 122
   ```

2. **Abrir** `silver-to-gold-dim-uc.ipynb` pela pasta Git do repositório e conectar ao **Serverless**. O notebook lê o YAML do contrato pelo caminho relativo; se for importado avulso, informe o caminho do YAML no widget `contrato_yaml`.
3. **Validar:** **Run all** com o widget `modo = validar`. Nada é gravado.
4. **Publicar:** troque o widget `modo` para `publicar` e rode **Run all** de novo.
5. **Conferir:**
   * a tabela de regras, todas `OK`;
   * `[OK] dim_uc: 45,000 UCs validadas em memória`;
   * os recortes, as classes e os municípios da seção 2 do notebook;
   * no fim, `Publicada: ... dim_uc (versão N, com o id desta execução no userMetadata)`.
6. **No Workflow (#97):** a tarefa vai depender das Silvers de cadastro e de inspeções e das Golds de GD e de continuidade, e passar `modo=publicar`.

## 8. Pendências

* **Exportação para o banco do portal (#96):** a `dim_uc` vai para o lote como `dim_uc.csv`, com os booleanos escritos como `true` e `false`, que é o que o importador aceita.
* **Consumidores:** as Golds que conferem o `id_uc` contra a Silver de cadastro podem passar a conferir contra a `dim_uc`. A de medidores já tem o widget `tabela_cadastro` para isso.
* **Contrato provisório:** `dim_uc.yaml` está como `provisorio-nao-aprovado`.
* **Tabelas analíticas do cadastro:** o resumo por município, as UCs por alimentador, a evolução das ligações e a qualidade cadastral seguem no #106.
