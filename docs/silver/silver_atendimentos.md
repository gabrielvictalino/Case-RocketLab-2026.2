# Camada Silver — Atendimentos

## 1. Objetivo

Nesta etapa do projeto V-Energy Grid 360, fiquei responsável pelo tratamento dos dados de atendimentos, realizando a passagem das informações da camada Bronze para a Silver.

O objetivo foi padronizar os dados, identificar possíveis inconsistências e preparar as informações para serem utilizadas posteriormente na camada Gold.

O processamento foi desenvolvido em PySpark, no notebook `data-engineering/bronze_to_silver/bronze-to-silver-atendimentos.ipynb`.

As tabelas utilizadas são:

- Origem: `v-energy`.bronze.tb_atendimentos
- Destino: `v-energy`.silver.tb_atendimentos
- Referência de unidades consumidoras: `v-energy`.silver.tb_unidades_consumidoras

## 2. Tratamentos realizados

No notebook, implementei os seguintes tratamentos:

- Remoção de espaços desnecessários em `protocolo` e `id_uc`.
- Padronização de `canal`, `assunto` e `subassunto` em letras maiúsculas.
- Conversão das datas de abertura e fechamento para timestamp.
- Conversão das notas de satisfação para double.
- Padronização das ações e canais presentes no histórico dos atendimentos.
- Conversão das datas e sequências dos eventos para os tipos adequados.
- Preservação dos campos `ingestion_datetime` e `source_file`, utilizados para rastrear a origem dos dados.

Mantive o histórico dentro da própria tabela de atendimentos, pois os eventos estão diretamente relacionados a cada protocolo.

## 3. Validações dos dados

Antes de permitir a gravação, o notebook verifica:

- Se todas as colunas obrigatórias existem na Bronze.
- Se a quantidade de atendimentos foi preservada após as transformações.
- Se existem protocolos duplicados ou identificadores obrigatórios vazios.
- Se ocorreram problemas nas conversões de datas e notas de satisfação.
- Se as datas de abertura e fechamento apresentam inconsistências.
- Se as notas preenchidas estão na faixa de 1 a 5, com no máximo uma casa decimal, permitindo valores nulos. É a escala do contrato (`atendimentos.nota`, `numeric(2,1)`, #117). Na base, as notas vão de 1,3 a 5,0.
- Se os valores de `id_uc` existem na Silver de unidades consumidoras.
- Se o histórico possui eventos inválidos, sequências duplicadas ou fora de ordem e datas incompatíveis com o período do atendimento.
- Se a quantidade de eventos foi preservada.

A validação de `id_uc` utiliza um `left_anti join` para localizar unidades sem correspondência. Caso a tabela de referência não exista, o processamento também é interrompido.

Se alguma dessas verificações falhar, o notebook gera um erro antes da etapa de gravação.

## 4. Decisões tomadas

Na auditoria realizada anteriormente, identifiquei 9.566 notas de satisfação nulas entre os 318.871 atendimentos.

Decidi preservar esses valores porque não é possível afirmar que sejam erros. Alguns clientes podem não ter respondido à pesquisa, e substituir as notas por zero poderia prejudicar as análises.

Também foi identificado um aumento considerável no volume de atendimentos em julho de 2025. Optei por manter esses registros, pois a auditoria não encontrou evidências suficientes para classificá-los como incorretos.

Dessa forma, priorizei a padronização e a validação, sem excluir informações que podem ser importantes para as próximas etapas.

## 5. Controle de versões e gravação na Silver

Para evitar que mudanças posteriores na Bronze afetem a execução, o notebook consulta o histórico Delta da tabela de origem e utiliza uma versão específica por meio de `VERSION AS OF`.

A gravação permanece desativada por padrão. O parâmetro Databricks `confirmar_publicacao` inicia como `false` e pode ser definido como `true` pelo Workflow para autorizar a publicação após as validações. Fora do Databricks, sem `dbutils`, a gravação permanece desativada.

Quando a gravação for autorizada, o notebook foi preparado para:

1. Concluir as validações dos dados antes de escrever.
2. Identificar se a tabela Silver já existe e registrar sua versão anterior, quando disponível.
3. Gravar os dados tratados em formato Delta, utilizando `overwrite`.
4. Validar após a gravação a quantidade de atendimentos, a ausência de protocolos duplicados e a quantidade de eventos.
5. Tentar restaurar a versão anterior com `RESTORE TABLE` caso ocorra uma falha durante a gravação ou nas verificações posteriores.

Se não existir uma versão anterior para restaurar, o notebook informa que será necessária uma verificação manual. A tentativa de rollback não garante a recuperação em todos os cenários.

## 6. Situação atual

O notebook foi organizado em células de configuração, transformação, validação, diagnóstico e gravação.

As alterações passaram por verificações locais de estrutura e sintaxe Python. Na revisão, Fernando também executou o pipeline localmente com PySpark 4.0 e Delta, verificando as contagens, as validações, a gravação Silver e o bloqueio de dados inválidos.

Em 02/11, a Silver rodou no Databricks com `confirmar_publicacao=true`. Gravou 318.871 atendimentos, com 636.857 eventos no histórico e 9.566 notas nulas, os mesmos números da execução local.

A faixa da nota passou a ser de 1 a 5, com no máximo uma casa decimal (#117). As 309.305 notas preenchidas da base passam na regra. Uma nota 0,5 e outra 4,35, injetadas na Bronze local, foram barradas antes da gravação.
