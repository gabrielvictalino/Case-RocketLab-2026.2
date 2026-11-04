# Exportação da Gold para o portal

Notebook: [`data-engineering/silver_to_gold/gold-exportacao-portal.ipynb`](../../data-engineering/silver_to_gold/gold-exportacao-portal.ipynb) (`GOLD_EXPORTACAO_V1`). Issue: #96.

## 1. O que faz

O portal não lê o Databricks: o `importador` carrega no banco local um **lote** com as 12 tabelas do contrato (`contracts/tabelas/`), um `<tabela>.csv` por tabela e o `manifest.json` (`contracts/manifest.schema.json`). Sem lote, o portal mostra a amostra sintética `contracts/samples`.

Este notebook é o último passo do pipeline. As Golds de domínio continuam cada uma no seu notebook e publicam só no Databricks. A exportação lê as 12 tabelas juntas, confere o lote inteiro com as regras do importador e grava o pacote num Volume.

## 2. Como o lote é montado

* **Um retrato só.** As 10 tabelas Delta são lidas na última versão, fixada (`VERSION AS OF`) para todas as leituras e anotada em `fontes.json` com o `id_delta`. As duas da Gold de faturas (`uc_consumo_faturamento_mensal` e `receita_volume_mensal`) são lidas pelo marcador `tb_gold_faturas_publicacao`, que precisa ter as 8 tabelas esperadas da mesma execução, como pede [`faturas.md`](faturas.md) ("Publicação, interrupção e recuperação").
* **Mesmas versões da Silver.** A Gold de faturas registra no marcador as versões da Silver que leu (cadastro, GD, inspeções, leituras e medidores). Cada uma das outras 10 tabelas precisa ter sido gravada enquanto valia o conteúdo dessas versões: depois da escrita de dados da versão lida pela Gold de faturas e antes da escrita seguinte. Commits que só mudam metadados (propriedades, estatísticas, comentários e restrições) não contam. O mesmo vale para as Golds do lote que outras leem: a `dim_uc` precisa ser posterior à `gd_uc` e à `dim_alimentador` exportadas, e as de perdas, à `gd_uc`. Uma versão exportada que seja um `RESTORE` (publicação desfeita) também para o notebook: a Gold precisa rodar de novo. As dependências de cada tabela estão em `DEPENDENCIAS`, na célula 1.
* **Sem publicação no meio.** A exportação roda depois de todas as Golds: no Workflow (#97), como a última tarefa; à mão, com o Job parado. Antes do manifesto, o notebook confere de novo que nenhuma das 10 tabelas ganhou versão e que o marcador da Gold de faturas é da mesma execução.
* **Período:** a primeira e a última competência de `uc_consumo_faturamento_mensal`, que o importador exige iguais às do manifesto.
* **Data de referência:** o widget `data_referencia`, que precisa ser a mesma da execução da Gold de faturas (o retrato de status da extração; hoje, 2026-10-22). O notebook para se for diferente.
* **CSV:** escrito com o `csv` do Python, o mesmo módulo que o importador usa para ler, em ordem de chave pelos tipos da tabela (a `sequencia` 2 vem antes da 10). Cada tipo do contrato sai no formato que o `parse` do importador aceita:

| Tipo no contrato | Tipo na Gold | No CSV |
| :--- | :--- | :--- |
| `text` | `string` | o texto |
| `date` | `date` | `AAAA-MM-DD` |
| `timestamp` | `timestamp_ntz` | `AAAA-MM-DDTHH:MM:SS`, sem fuso |
| `boolean` | `boolean` | `true` / `false` |
| `integer` | `int` | o número |
| `numeric(p,s)` | `decimal(p,s)` | o número com ponto, sem notação científica |
| `jsonb` | `array<string>` | a lista em JSON (`["...", "..."]`), como `motivos` da `fila_inspecao` |
| nulo | — | campo vazio |

* **Manifesto por último:** gerado por `contracts/manifesto.py`, o gerador do contrato, depois dos 12 CSVs, do `fontes.json` e de todas as conferências. Sem `manifest.json`, o importador não aceita a pasta, então uma pasta com manifesto é sempre um lote conferido; se algo falha antes, a pasta fica sem ele. Cada lote vai para uma pasta nova (`<diretorio_exportacao>/<batch_id>`), e o notebook para se ela já existir.

## 3. Conferências

Todas param o notebook. As quatro primeiras rodam antes de gravar qualquer arquivo:

* **Por tabela:** colunas, tipos e ordem do YAML; obrigatórias não nulas; texto não vazio, com qualquer espaço Unicode contando como vazio, como o `str.strip()` do importador; `pattern` casando o valor inteiro (como o `re.fullmatch` do importador); `enum`; `minimum` e `maximum`; competência no dia 1; lista de `motivos` não vazia e sem texto vazio; data-hora sem fração de segundo; chave única; competência dentro do período do lote.
* **Entre tabelas:** toda chave estrangeira do YAML (`references`) com correspondente, como o importador cria no banco, e os portões do importador (`importador/src/importador/loader.py`) reescritos em Spark SQL: inspeção coerente (resultado, tipo e kWh), medidor retirado depois de instalado, durações das ocorrências, R2 da Gold de faturas, R3 (grupo de UC temporal), R4 (`flag_gd` igual à presença em `gd_uc`, fila sem GD, `numero_ucs` igual ao da `dim_alimentador`) e a receita reconciliada por grão com `uc_consumo_faturamento_mensal` e a `dim_uc`.
* **Do lote:** `data_referencia` e período iguais aos da Gold de faturas; R6 (`data_referencia` não anterior ao último mês do período); `batch_id` de 1 a 200 caracteres, o limite do `manifest.schema.json`.
* **Versões:** cada tabela gravada sobre as versões da Silver lidas pela Gold de faturas e sobre as Golds do lote que ela lê; nenhuma versão exportada é um `RESTORE` (seção 2).
* **Depois de gravar, antes do manifesto:** cada CSV lido de volta pelo `inspecionar_csv` de `contracts/manifesto.py`, com as linhas e os totais de controle iguais aos da tabela; nenhuma tabela publicada durante a exportação. Depois, o manifesto precisa trazer os mesmos SHA-256 conferidos; se não trouxer, o `manifest.json` é apagado.

O `importador --verificar` repete tudo no PostgreSQL antes da carga. As conferências do notebook servem para a falha aparecer no Databricks, junto da tabela que a causou, e não no banco do portal.

## 4. Como executar

No Databricks, pelo bundle de `data-engineering/` (que leva junto `contracts/` e os módulos da Gold de faturas):

1. Rode as Golds de domínio, inclusive a de faturas com a mesma `data_referencia`.
2. Rode este notebook com `modo=validar`: a tabela de regras precisa sair toda OK.
3. Rode com `modo=exportar`, `data_referencia` e `diretorio_exportacao` (por exemplo, `/Volumes/v-energy/gold/exportacao`). A saída mostra a pasta do lote.

Para carregar no portal:

```bash
databricks fs cp -r dbfs:/Volumes/v-energy/gold/exportacao/<batch_id> ./lote-gold/<batch_id>
GOLD_EXPORT_DIR=./lote-gold/<batch_id> docker compose --profile carga run --rm importador --origem /entrada --verificar
GOLD_EXPORT_DIR=./lote-gold/<batch_id> docker compose --profile carga run --rm importador --origem /entrada
```

O `--verificar` carrega o lote numa área temporária, roda todos os portões e desfaz tudo; só a segunda chamada publica.

## 5. Decisões e alternativas

| Decisão | Alternativa | Por que não |
| :--- | :--- | :--- |
| Um notebook lê as 12 tabelas e gera o lote | Cada Gold exporta o seu CSV com recibo, e o `montar_lote_gold.py` junta | Só a Gold de faturas exporta hoje. As outras 10 precisariam de um exportador cada, e a conferência entre tabelas continuaria fora do Databricks |
| Gold de faturas pelo marcador | Ler `uc_consumo_faturamento_mensal` direto | A Gold de faturas publica em revisões; o nome fixo pode ser uma revisão não confirmada |
| `csv` do Python sobre `toLocalIterator` | Escrita CSV do Spark | O importador lê com o `csv` do Python; escrever com o mesmo módulo evita diferenças de aspas e escape |
| Portões do importador também no notebook | Só o `importador --verificar` | A falha aparece no pipeline, antes de alguém baixar o lote |
| Portões reescritos em Spark | Rodar o parser do importador (`importador.contracts`) sobre cada CSV gravado | O parser não vai junto no bundle, e a conferência em Spark mostra a contagem por regra antes de gravar. A garantia final continua no `importador --verificar`, obrigatório antes da carga (seção 4) |
| Versões conferidas pelo histórico Delta | Um marcador de publicação por domínio, como o da Gold de faturas | O marcador exige mudar as 7 Golds de domínio; fica para o módulo comum de publicação (#139). O histórico já registra quando cada conteúdo passou a valer |

## 6. Pendências

* **Workflow (#97):** este notebook vira a última tarefa do Job, depois de todas as Golds.
* **Recibo da Gold de faturas:** a Gold de faturas continua gravando o recibo dela (`comercial.json`) no Volume. O lote do portal sai deste notebook.
