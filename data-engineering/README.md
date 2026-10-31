# Gold de faturas

O [notebook](silver_to_gold/silver-to-gold-faturas.ipynb) lê as tabelas Silver
Delta, valida as entradas e produz:

- `gold.tb_faturas`: detalhe das contas, valores e situação de pagamento;
- `gold.tb_faturamento_mensal`: faturamento por competência, município, bairro e classe;
- `gold.tb_variacao_receita`: primeiro ano × últimos 12 meses, com efeitos de volume,
  preço efetivo e receita sem volume utilizável;
- `gold.tb_faturas_excluidas`: faturas segregadas com motivo e valores reconciliáveis.

As transformações ficam em [gold_faturas.py](silver_to_gold/gold_faturas.py).
O [dicionário e as decisões](../docs/gold/faturas.md) definem o grão de cada tabela,
as fórmulas, os limites dos dados e as diferenças em relação ao contrato sintético
provisório do portal.

## Databricks

1. Sincronize este diretório num Git folder do Databricks, mantendo o notebook
   e `gold_faturas.py` lado a lado. O `%run ./gold_faturas` carrega as funções.
2. Use compute com Unity Catalog e acesso às quatro fontes Delta e ao Volume
   de exportação. O bundle usa Jobs serverless; para um workspace sem esse
   recurso, configure compute na tarefa antes da execução.
3. Abra o notebook e confira os widgets das fontes. Os padrões refletem os nomes
   físicos encontrados nos notebooks Silver do projeto; os catálogos ainda não
   estão unificados. São parâmetros independentes para evitar renomear fontes.
4. Informe `data_referencia` como `AAAA-MM-DD`, correspondente ao retrato de status
   da extração e igual ou posterior às emissões e pagamentos observados. A fonte
   não informa a data oficial da extração; ela precisa ser fornecida pelo operador.
   A Gold não usa `current_date()` para envelhecer uma base estática.
5. Execute tudo com `modo=validar` para conferir os resultados sem escrita.
6. Para gravar, configure `schema_gold`, `diretorio_exportacao` em um Volume
   existente, `modo=publicar` e execute tudo desde o início. O schema de destino
   é criado, e as quatro tabelas são substituídas após a validação.

O diretório exportado será `<diretorio_exportacao>/<batch_id>/`, com subdiretórios
por tabela e um `manifest.json`. Cada CSV tem cabeçalho, UTF-8, vírgula, decimal
com ponto e datas ISO. Uma tabela pode ter várias partes: leia todos os
`part-*.csv`, respeitando um cabeçalho por arquivo. O manifesto registra as versões
Delta de origem/destino, tipos, contagens, totais de controle e SHA-256 das partes.
Consuma apenas lotes com manifesto final e valide seus hashes e totais.

As tabelas Delta são transações independentes. Se houver falha na publicação,
inspecione os destinos e reexecute o notebook inteiro antes de consumir o lote.
O manifesto só aparece após todas as escritas e conferências; um diretório sem
manifesto está incompleto e deve ser ignorado. O Job limita a concorrência a 1;
não publique manualmente ao mesmo tempo que ele.

## Job

O [databricks.yml](databricks.yml) define somente a etapa Gold. Não implanta nem
executa Bronze ou Silver e não altera as rotinas existentes. No Workflow completo,
use esta tarefa depois da publicação bem-sucedida de faturas, cadastro e leituras
Silver. Nenhuma execução na plataforma é alegada por este repositório.

Com Databricks CLI autenticado no workspace, a partir deste diretório:

```bash
export BUNDLE_VAR_data_referencia='AAAA-MM-DD'
export BUNDLE_VAR_diretorio_exportacao='/Volumes/catalogo/schema/volume/gold-faturas'
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run -t dev gold_faturas
```

Substitua os placeholders pelos dados da execução. O agendamento está **pausado**
porque o case usa uma extração única. Para produção, a proposta é dia 5 de cada
mês às 03h, `America/Fortaleza`, após o fechamento mensal e as tarefas Silver,
atualizando a data de referência do novo retrato. O processamento é carga completa:
~2,2 milhões de faturas permitem reprocessamento simples e inclusão de pagamentos
tardios, mudanças cadastrais e correções históricas. A implantação/ativação efetiva
do Job e o print de execução dependem do workspace Databricks.

## Validação local

Requer Python 3.12 e Java 17 ou 21. PySpark já existe no Databricks; as dependências
abaixo são para validação local e CI, não devem ser instaladas no cluster.

```bash
python -m pip install -r data-engineering/requirements-test.txt
python -m ruff check data-engineering/silver_to_gold data-engineering/tests
SPARK_LOCAL_IP=127.0.0.1 python -m unittest discover -s data-engineering/tests -v
python -m unittest discover -s tests -v
```

Execute esses comandos da raiz do repositório. Os testes usam Spark real e dados
sintéticos, sem conexão ao Databricks ou aos arquivos brutos do case. O workflow
GitHub Actions `Gold de faturas` repete lint e testes; as proteções administrativas
do GitHub não são alteradas por esta implementação.
