# Gold de faturas

A Gold lê Silver por snapshots e prepara duas saídas comerciais do contrato
`0.3.0-provisional`: `uc_consumo_faturamento_mensal` e `receita_volume_mensal`.
Mantém detalhe, exclusões, agregado mensal e decomposição de preço efetivo como
auxiliares reconciliáveis. Regras, fontes e operação estão no
[dicionário](../docs/gold/faturas.md); requisitos e bloqueios, na
[matriz de aderência](../docs/gold/aderencia-faturas-0.3.md).

## Execução no Databricks

1. Sincronize o repositório inteiro em Git folder, preservando `contracts/`.
   Use runtime com Python 3.12, Spark compatível com 4.0 e PyYAML; o notebook e
   módulos `.py` devem permanecer juntos. Imports locais precisam estar habilitados.
   O bundle inclui `.` e `../contracts` em `sync.paths` para preservar essa árvore;
   use uma Databricks CLI que suporte sincronização fora da raiz do bundle.
2. Confira os widgets do [notebook](silver_to_gold/silver-to-gold-faturas.ipynb).
   O marcador padrão é `v-energy.silver.tb_faturas_publicacao`; ausência ou
   incoerência bloqueia, sem ler os nomes finais como fallback. Cadastro e leituras
   usam `v-energy.silver.tb_unidades_consumidoras` e `v-energy.silver.tb_leituras`.
   GD usa `v-energy.silver.tb_geracao_distribuida`; inspeções usam o nome legado do
   produtor, `venergy.silver.inspecoes`, parametrizável. Confirme disponibilidade.
3. Informe `data_referencia` como data do retrato de status da extração; ela vira
   `reference_date`. Não é automaticamente a ingestão ou o dia da execução.
4. Execute desde o início em `modo=validar`: nenhuma escrita ou limpeza.
   Com `tabela_complemento_faturamento` vazio, deriva o complemento conforme
   decisão 6587742059: volume analítico, tarifa por subgrupo/mês e bandeiras fixas.
   Configure também `tabela_medidores` (Silver com `data_retirada`). Falta de doadores
   bloqueia; faturas sem leitura são segregadas.
5. A publicação só é possível com todas as fontes/gates satisfeitos, escritor
   único por ACL e `diretorio_exportacao` em `/Volumes/...`. O código prepara
   revisões exclusivas, reconcilia integralmente, confirma por marcador e exporta
   arquivos com conferência de conteúdo final. O agendamento permanece `PAUSED`.
6. Consuma Delta pelo marcador `gold.tb_gold_faturas_publicacao`, com uma única
   leitura e `versionAsOf`; os nomes fixos legados não representam esta publicação.
   Após interrupção, consulte o marcador para recuperar o conjunto confirmado.
   Revisões fora dele só são limpas por manutenção explícita com retenção persistente.

O [bundle](databricks.yml) limita concorrência a uma execução. A definição da
referência oficial de cada extração é pré-condição para eventual ativação futura.
Não execute publicações manuais em paralelo. A manutenção, permissões, retenção e
protocolo de arquivos ainda exigem homologação no runtime Databricks.

## Lote para o portal

A pasta `<diretorio_exportacao>/<batch_id>/comercial/` contém os dois CSVs canônicos
e `comercial.json`, recibo do domínio. `auxiliares/` usa formato próprio e não entra
como substituto do contrato. O coordenador reúne as dez exportações dos demais
domínios, prepara plano com hashes e proveniência comum e executa:

```bash
python data-engineering/silver_to_gold/montar_lote_gold.py --plano plano.json --destino /tmp/lote-gold
uv run importador --origem /tmp/lote-gold --verificar
```

O montador reutiliza `contracts/manifesto.py` para gerar `manifest.json` de 12
tabelas. O importador confere FKs, gates de negócio e índices e faz rollback em
`--verificar`. Use banco de teste. Uma fixture aprovada não homologa dados reais.
O [dicionário](../docs/gold/faturas.md) fornece o formato do plano e a divisão entre domínios.

## Testes locais e CI

Python 3.12 e Java 17/21:

```bash
python -m pip install -r data-engineering/requirements-test.txt
python -m ruff check data-engineering/silver_to_gold data-engineering/tests
python -m ruff format --check data-engineering/silver_to_gold data-engineering/tests
SPARK_LOCAL_IP=127.0.0.1 python -m unittest discover -s data-engineering/tests -v
python -m unittest discover -s tests -v
uv run pytest importador -q
```

A suíte Gold está no job `gold` de `.github/workflows/ci.yml` e no agregador `CI`.
O workflow separado foi removido. Os testes não se conectam ao Databricks; o
importador usa PostgreSQL 17 e Redis 7 locais via Testcontainers.
