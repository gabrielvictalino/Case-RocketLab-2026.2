# Evidências da versão operacional — 30/10/2026

Os dois arquivos foram enviados pelo autor após execuções no Databricks. Foram preservados byte a byte, inclusive nomes antigos, metadados, widgets e outputs. A comparação das 42 células Python de cada anexo com `data-engineering/bronze-to-silver-faturas.ipynb` do commit `ef4d870c99130118b8b037b84d2acc01a79597c7` confirmou igualdade integral das fontes de código. A renomeação anterior alterou somente apresentação e identificação; os anexos ainda usam o nome `bronze-to-silver-faturas-operacional`.

O notebook operacional com o nome atual recebeu os outputs e metadados da execução com true; somente a apresentação e a identificação foram conciliadas com a versão renomeada. O código Python permaneceu idêntico. Os anexos abaixo conservam os exports originais para auditoria.

| Parâmetro | Arquivo original | Intervalo em America/Fortaleza |
| :--- | :--- | :--- |
| `false` | [bronze-to-silver-faturas-operacional (1).ipynb](evidencias/faturas-2026-10-30/bronze-to-silver-faturas-operacional%20%281%29.ipynb) | 18:47:28 às 18:51:25 |
| `true` | [bronze-to-silver-faturas-operacional (2).ipynb](evidencias/faturas-2026-10-30/bronze-to-silver-faturas-operacional%20%282%29.ipynb) | 18:52:15 às 18:56:30 |

Nos dois anexos, as 42 células Python têm início e fim registrados em sequência, sem outputs de erro ou `Command skipped`. As validações de tipos, chaves, regras por registro, preservação dos originais e metadados, separação cadastral e conservação financeira passaram.

## Execução com false

Os outputs registram validação em memória e o desvio das gravações: nenhuma revisão, plano de escrita ou publicação foi produzido. A mensagem final foi `OK: validação em memória concluída; publicação não solicitada.`

## Execução com true

As revisões `tb_faturas_revisao_c13b3d3df7e94211a5145f883baf0c1b` e `tb_faturas_pendentes_cadastro_revisao_c13b3d3df7e94211a5145f883baf0c1b` foram criadas em `v-energy.silver_revisoes`, ambas na versão Delta 0. As duas foram conferidas integralmente antes da publicação.

| Destino publicado | Versão Delta | Faturas | Valor total |
| :--- | ---: | ---: | ---: |
| `v-energy.silver.tb_faturas` | 3 | 2.152.336 | R$ 666.482.773,76 |
| `v-energy.silver.tb_faturas_pendentes_cadastro` | 2 | 32.285 | R$ 10.192.373,82 |
| **Total** | — | **2.184.621** | **R$ 676.675.147,58** |

Schema e conteúdo dos destinos foram conferidos. A mensagem final foi `OK: publicação definitiva concluída e conferida.` Os outputs demonstram acesso suficiente para as operações executadas em `silver_revisoes`; não demonstram se o schema já existia antes do `CREATE SCHEMA IF NOT EXISTS`.

Estas execuções atendem aos testes com false e true da segunda recomendação do muliroZ. A execução com true publicou nos destinos do projeto, não em catálogo isolado de teste. Não comprova execução da Gold ou de um Job integrado. As duas publicações seguem sendo transações separadas. A retenção e limpeza das revisões antigas em `silver` continuam pendentes de acordo com a equipe.

O anexo com true conserva esse valor no widget. Para novas execuções, use o notebook operacional e confira explicitamente o parâmetro e os destinos.

## Integridade dos anexos

SHA-256 calculado sobre os bytes originais enviados pelo autor:

- `bronze-to-silver-faturas-operacional (1).ipynb`: `13370dddf986965ce14852a2ba7931780ca94957aceab3a675fa44307bf604b7`
- `bronze-to-silver-faturas-operacional (2).ipynb`: `4f028d5b903ba77db0969cb948feb29f94c3e90523884f04ce7f6f6d33bcaae1`
