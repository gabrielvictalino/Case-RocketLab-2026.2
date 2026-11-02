# Camada Silver ? Atendimentos

## 1. Objetivo

Nesta etapa do projeto V-Energy Grid 360, fiquei respons?vel pelo tratamento dos dados de atendimentos, realizando a passagem das informa??es da camada Bronze para a Silver.

O objetivo foi padronizar os dados, identificar poss?veis inconsist?ncias e preparar as informa??es para serem utilizadas posteriormente na camada Gold.

O processamento foi desenvolvido em PySpark, no notebook `data-engineering/bronze_to_silver/bronze-to-silver-atendimentos.ipynb`.

As tabelas utilizadas s?o:

- Origem: `v-energy`.bronze.tb_atendimentos
- Destino: `v-energy`.silver.tb_atendimentos
- Refer?ncia de unidades consumidoras: `v-energy`.silver.tb_unidades_consumidoras

## 2. Tratamentos realizados

No notebook, implementei os seguintes tratamentos:

- Remo??o de espa?os desnecess?rios em `protocolo` e `id_uc`.
- Padroniza??o de `canal`, `assunto` e `subassunto` em letras mai?sculas.
- Convers?o das datas de abertura e fechamento para timestamp.
- Convers?o das notas de satisfa??o para double.
- Padroniza??o das a??es e canais presentes no hist?rico dos atendimentos.
- Convers?o das datas e sequ?ncias dos eventos para os tipos adequados.
- Preserva??o dos campos `ingestion_datetime` e `source_file`, utilizados para rastrear a origem dos dados.

Mantive o hist?rico dentro da pr?pria tabela de atendimentos, pois os eventos est?o diretamente relacionados a cada protocolo.

## 3. Valida??es dos dados

Antes de permitir a grava??o, o notebook verifica:

- Se todas as colunas obrigat?rias existem na Bronze.
- Se a quantidade de atendimentos foi preservada ap?s as transforma??es.
- Se existem protocolos duplicados ou identificadores obrigat?rios vazios.
- Se ocorreram problemas nas convers?es de datas e notas de satisfa??o.
- Se as datas de abertura e fechamento apresentam inconsist?ncias.
- Se as notas preenchidas est?o na faixa de 0 a 10, permitindo valores nulos.
- Se os valores de `id_uc` existem na Silver de unidades consumidoras.
- Se o hist?rico possui eventos inv?lidos, sequ?ncias duplicadas ou fora de ordem e datas incompat?veis com o per?odo do atendimento.
- Se a quantidade de eventos foi preservada.

A valida??o de `id_uc` utiliza um `left_anti join` para localizar unidades sem correspond?ncia. Caso a tabela de refer?ncia n?o exista, o processamento tamb?m ? interrompido.

Se alguma dessas verifica??es falhar, o notebook gera um erro antes da etapa de grava??o.

## 4. Decis?es tomadas

Na auditoria realizada anteriormente, identifiquei 9.566 notas de satisfa??o nulas entre os 318.871 atendimentos.

Decidi preservar esses valores porque n?o ? poss?vel afirmar que sejam erros. Alguns clientes podem n?o ter respondido ? pesquisa, e substituir as notas por zero poderia prejudicar as an?lises.

Tamb?m foi identificado um aumento consider?vel no volume de atendimentos em julho de 2025. Optei por manter esses registros, pois a auditoria n?o encontrou evid?ncias suficientes para classific?-los como incorretos.

Dessa forma, priorizei a padroniza??o e a valida??o, sem excluir informa??es que podem ser importantes para as pr?ximas etapas.

## 5. Controle de vers?es e grava??o na Silver

Para evitar que mudan?as posteriores na Bronze afetem a execu??o, o notebook consulta o hist?rico Delta da tabela de origem e utiliza uma vers?o espec?fica por meio de `VERSION AS OF`.

A grava??o permanece desativada por padr?o, utilizando `CONFIRMAR_GRAVACAO = False`.

Quando a grava??o for autorizada, o notebook foi preparado para:

1. Concluir as valida??es dos dados antes de escrever.
2. Identificar se a tabela Silver j? existe e registrar sua vers?o anterior, quando dispon?vel.
3. Gravar os dados tratados em formato Delta, utilizando `overwrite`.
4. Validar ap?s a grava??o a quantidade de atendimentos, a aus?ncia de protocolos duplicados e a quantidade de eventos.
5. Tentar restaurar a vers?o anterior com `RESTORE TABLE` caso ocorra uma falha durante a grava??o ou nas verifica??es posteriores.

Se n?o existir uma vers?o anterior para restaurar, o notebook informa que ser? necess?ria uma verifica??o manual. A tentativa de rollback n?o garante a recupera??o em todos os cen?rios.

## 6. Situa??o atual

O notebook foi organizado em c?lulas de configura??o, transforma??o, valida??o, diagn?stico e grava??o.

As altera??es passaram por verifica??es locais de estrutura e sintaxe Python. Entretanto, o processamento ainda n?o foi executado no Databricks, devido ? indisponibilidade de recursos computacionais no ambiente.

Portanto, as transforma??es, as valida??es com dados reais, a grava??o e o procedimento de rollback ainda precisam ser testados no Databricks.

Antes de habilitar `CONFIRMAR_GRAVACAO`, ser? necess?rio confirmar que a tabela Silver de unidades consumidoras est? dispon?vel, executar as valida??es e conferir os resultados.

Depois da valida??o da execu??o e da grava??o, os dados poder?o ser utilizados na constru??o da camada Gold.
