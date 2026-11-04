# Workflow do Databricks

O pipeline roda de ponta a ponta num Job do Databricks, definido no bundle [`data-engineering/databricks.yml`](../data-engineering/databricks.yml) (#97). Uma execução lê os arquivos da landing, publica a Bronze, as 8 Silvers e as Golds, e termina com o lote das 12 tabelas do contrato que o importador do portal carrega ([`docs/gold/exportacao.md`](gold/exportacao.md)).

## 1. Tarefas e dependências

Uma tarefa por notebook. Cada uma espera só as tarefas cujas tabelas ela lê, então as Silvers rodam em paralelo depois da Bronze, e as Golds começam assim que as suas fontes ficam prontas.

| Tarefa | Notebook | Espera |
| :--- | :--- | :--- |
| `landing_to_bronze` | `data-engineering/Landing_to_Bronze.ipynb` | — |
| `silver_unidades_consumidoras` | `data-engineering/bronze_to_silver/bronze-to-silver-unidades-consumidoras.ipynb` | Bronze |
| `silver_geracao_distribuida` | `data-engineering/bronze_to_silver/bronze-to-silver-geracao-distribuida.ipynb` | Bronze |
| `silver_leituras` | `data-engineering/bronze_to_silver/bronze-to-silver-leituras.ipynb` | Bronze |
| `silver_medidores` | `data-engineering/bronze_to_silver/bronze-to-silver-medidores.ipynb` | Bronze |
| `silver_ocorrencias_rede` | `data-engineering/bronze_to_silver/bronze-to-silver-ocorrencias-rede.ipynb` | Bronze |
| `silver_atendimentos` | `data-engineering/bronze_to_silver/bronze-to-silver-atendimentos.ipynb` | Bronze |
| `silver_faturas` | `data-engineering/bronze-to-silver-faturas.ipynb` | Bronze |
| `silver_inspecoes` | `data-engineering/bronze_to_silver/bronze-to-silver-inspecoes.ipynb` | Silver de cadastro (confere toda UC inspecionada) |
| `gold_geracao_distribuida` | `data-engineering/silver_to_gold/silver-to-gold-geracao-distribuida.ipynb` | Silvers de GD, cadastro e leituras |
| `gold_continuidade` | `data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb` | Silvers de ocorrências e cadastro |
| `gold_atendimentos` | `data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb` | Silvers de atendimentos e cadastro |
| `gold_medidores` | `data-engineering/silver_to_gold/silver-to-gold-medidores.ipynb` | Silvers de medidores e cadastro |
| `gold_faturas` | `data-engineering/silver_to_gold/silver-to-gold-faturas.ipynb` | Silvers de faturas, cadastro, leituras, GD, inspeções e medidores |
| `gold_perdas` | `data-engineering/silver_to_gold/silver-to-gold-perdas.ipynb` | Silvers de leituras, cadastro, medidores, inspeções e faturas; Gold de GD (R4) |
| `gold_dim_uc` | `data-engineering/silver_to_gold/silver-to-gold-dim-uc.ipynb` | Silvers de cadastro e inspeções; Golds de GD e de continuidade (`flag_gd` e UCs por alimentador) |
| `gold_exportacao_portal` | `data-engineering/silver_to_gold/gold-exportacao-portal.ipynb` | Todas as Golds |

**Parâmetros.**
- As Silvers que têm o widget `confirmar_publicacao` (atendimentos, faturas e inspeções) recebem `true`.
- As Golds recebem `modo=publicar`. O padrão dos notebooks continua `validar`, para que um *Run all* manual não grave nada.
- A exportação recebe `modo=exportar`.
- A Gold de faturas e a exportação recebem a mesma `data_referencia` e o mesmo `diretorio_exportacao`, que são variáveis do bundle.

## 2. Garantias de uma execução

- **No máximo uma execução por vez** (`max_concurrent_runs: 1`). A exportação confere que nenhuma Gold mudou durante o lote, e duas execuções simultâneas se atropelariam.
- **Reexecutar não duplica dados.** As camadas gravam por substituição: cada Silver e cada Gold reescreve a tabela inteira, e as de faturas (Silver e Gold) publicam uma revisão nova e trocam o marcador. Rodar de novo com as mesmas fontes produz as mesmas tabelas: na execução de teste de 04/11, que partiu da landing, os 12 CSVs do lote saíram com o mesmo SHA-256 do lote anterior.
- **Uma falha para o que depende dela.** Se uma Gold falha na validação, ela restaura a versão anterior (`RESTORE`) e a exportação não roda, porque depende de todas. O lote anterior continua no Volume, e o portal só troca de lote quando alguém o carrega.
- **Retomada.** Corrigida a causa, *Repair run* reexecuta só a tarefa que falhou e as que dependem dela.

## 3. Agendamento

O Job **não tem cron**. A base do case é uma extração pontual, e a Gold de faturas exige a data do retrato de status da extração (`data_referencia`, hoje 2026-10-22), que não é o dia da execução ([`docs/gold/faturas.md`](gold/faturas.md)). Um agendamento automático publicaria um lote com a referência errada.

Na operação, a carga é mensal, depois do fechamento mensal das faturas. Quem recebe a extração põe os arquivos na landing e dispara o Job com a `data_referencia` daquele retrato. Quando a extração chegar sozinha, numa data fixa, o passo seguinte é um gatilho por chegada de arquivo na landing (*file arrival trigger*), ou um cron mensal logo depois dessa data, com a `data_referencia` calculada pela própria extração.

## 4. Como executar

Com a Databricks CLI configurada, a partir de `data-engineering/`:

```bash
export BUNDLE_VAR_data_referencia=2026-10-22
export BUNDLE_VAR_diretorio_exportacao=/Volumes/v-energy/gold/exportacao
databricks bundle deploy
databricks bundle run pipeline
```

A pasta do lote aparece na saída da tarefa `gold_exportacao_portal`. Para carregar no portal, siga a seção 4 de [`docs/gold/exportacao.md`](gold/exportacao.md): baixar a pasta, rodar o `importador --verificar` e, se der OK, a carga.

**Pré-requisitos no workspace:** o catálogo `v-energy` com os schemas `bronze`, `silver`, `silver_revisoes` e `gold`; os arquivos de origem no Volume `/Volumes/v-energy/bronze/landing`; e o Volume da exportação.
