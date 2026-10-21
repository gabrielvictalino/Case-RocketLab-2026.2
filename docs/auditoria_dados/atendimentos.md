# Análise de Qualidade dos Dados — atendimentos.json

## 1. Sumário Executivo de Anomalias

A análise foi feita no arquivo `atendimentos.json`, utilizando Python e a biblioteca `ijson` para conseguir ler os dados sem precisar carregar o arquivo inteiro na memória.

No total, foram analisados **318.871 atendimentos** e **636.857 eventos de histórico**.

O objetivo foi verificar se existiam dados faltando, registros duplicados, datas incorretas, problemas nos históricos e valores que merecessem uma análise mais detalhada.

Durante a verificação, encontrei dois pontos que chamaram atenção: algumas notas de satisfação estão vazias e houve um aumento muito grande na quantidade de atendimentos em julho de 2025.

| Campo / Análise | Situação encontrada | Quantidade | Percentual | Criticidade |
|---|---|---:|---:|---|
| `nota_satisfacao` | Valores nulos | 9.566 | 3,00% | Baixa/Média |
| `data_abertura` | Aumento de atendimentos em julho/2025 | 18.061 | 5,66% da base | Média |
| `protocolo` | Protocolos duplicados | 0 | 0% | Nenhuma ocorrência |
| Datas | Datas inválidas ou invertidas | 0 | 0% | Nenhuma ocorrência |
| `historico` | Problemas na estrutura ou sequência | 0 | 0% | Nenhuma ocorrência |

As criticidades são estimativas iniciais. Para confirmar se os pontos encontrados são realmente problemas, seria necessário conhecer melhor algumas regras do sistema.

## 2. Diagnóstico Estrutural

O arquivo está no formato JSON e contém uma lista de atendimentos. Cada atendimento possui informações sobre o cliente, o motivo do contato, as datas e o histórico das ações realizadas.

Os campos principais são:

- `protocolo`
- `id_uc`
- `canal`
- `assunto`
- `subassunto`
- `data_abertura`
- `data_fechamento`
- `nota_satisfacao`
- `historico`

O campo `historico` contém uma lista de eventos. Cada evento possui `sequencia`, `data`, `acao` e `canal`.

Para verificar a estrutura, analisei se os campos estavam presentes, se os tipos dos dados eram consistentes e se os históricos possuíam informações faltando.

| Verificação | Resultado |
|---|---:|
| Atendimentos analisados | 318.871 |
| Eventos de histórico analisados | 636.857 |
| Campos principais ausentes | 0 |
| Protocolos duplicados | 0 |
| Históricos vazios | 0 |
| Eventos com campos ausentes ou nulos | 0 |
| Datas inválidas nos históricos | 0 |
| Sequências duplicadas | 0 |
| Sequências fora de ordem | 0 |
| Lacunas nas sequências | 0 |

Todos os atendimentos possuem os campos esperados. O único campo principal que apresentou valores nulos foi `nota_satisfacao`, que será detalhado mais adiante.

Nos históricos, não foram encontrados problemas nas verificações realizadas.

## 3. Diagnóstico de Qualidade por Atributo

### 3.1. Protocolo e identificação da unidade

Comecei verificando os campos `protocolo` e `id_uc`.

Todos os atendimentos possuem esses dois campos preenchidos. Também verifiquei se existiam protocolos repetidos, mas não encontrei nenhuma duplicação.

Isso é importante porque o protocolo é utilizado para identificar cada atendimento.

### 3.2. Canal, assunto e subassunto

Nesses campos, procurei valores vazios, espaços desnecessários e diferenças na escrita que poderiam atrapalhar uma análise posterior.

Encontrei a seguinte quantidade de valores distintos:

| Campo | Valores distintos |
|---|---:|
| `canal` | 5 |
| `assunto` | 6 |
| `subassunto` | 15 |

Os canais encontrados foram `SITE`, `WHATSAPP`, `TELEFONE`, `PRESENCIAL` e `APP`.

Os assuntos foram `RELIGACAO`, `FALTA DE ENERGIA`, `LIGACAO NOVA`, `DANO ELETRICO`, `FATURA` e `GERACAO DISTRIBUIDA`.

Não foram identificados problemas de padronização na escrita desses campos.

Também encontrei 17 combinações diferentes entre assunto e subassunto. Não identifiquei problemas de preenchimento, mas a validação dessas combinações dependeria das regras de negócio.

### 3.3. Datas de abertura e fechamento

Analisei as datas para verificar se estavam no formato esperado e se algum atendimento havia sido encerrado antes de ser aberto.

Os resultados foram:

| Verificação | Resultado |
|---|---:|
| Datas de abertura inválidas | 0 |
| Datas de fechamento inválidas | 0 |
| Fechamentos anteriores à abertura | 0 |
| Atendimentos com duração de zero hora | 0 |
| Atendimentos com duração superior a 30 dias | 0 |
| Menor duração encontrada | 1 hora |
| Maior duração encontrada | 719 horas |

Os atendimentos possuem datas de abertura entre julho de 2022 e junho de 2026.

Não encontrei inconsistências nas datas com as verificações realizadas.

### 3.4. Nota de satisfação

Esse foi o campo em que encontrei a principal questão relacionada ao preenchimento dos dados.

Dos 318.871 atendimentos, **9.566 estão com a nota de satisfação nula**, representando aproximadamente **3% da base**.

| Informação | Resultado |
|---|---:|
| Total de atendimentos | 318.871 |
| Notas preenchidas | 309.305 |
| Notas nulas | 9.566 |
| Menor nota encontrada | 1,3 |
| Maior nota encontrada | 5,0 |
| Valores diferentes de nota | 38 |

Também separei as notas nulas por assunto para verificar onde elas apareciam com mais frequência.

| Assunto | Notas nulas |
|---|---:|
| FALTA DE ENERGIA | 3.017 |
| LIGACAO NOVA | 1.327 |
| FATURA | 1.329 |
| DANO ELETRICO | 1.326 |
| RELIGACAO | 1.299 |
| GERACAO DISTRIBUIDA | 1.268 |
| **Total** | **9.566** |

Alguns exemplos de protocolos com nota nula são `AT000000011`, `AT000000020` e `AT000000080`.

Apesar de existir essa quantidade de valores nulos, não dá para afirmar que todos são erros. Uma possibilidade é que alguns clientes simplesmente não tenham respondido à pesquisa de satisfação.

Por isso, antes de preencher ou remover esses valores, seria necessário confirmar se a nota é obrigatória.

As notas preenchidas ficaram entre 1,3 e 5,0. Nenhuma ficou fora da faixa de 0 a 5, utilizada como referência na análise, mas a escala oficial ainda precisa ser confirmada.

### 3.5. Histórico dos atendimentos

O arquivo possui **636.857 eventos de histórico**, distribuídos entre os atendimentos.

Nessa parte, verifiquei se os eventos tinham os campos esperados, se existiam datas inválidas e se as sequências estavam organizadas.

Também comparei as datas dos eventos com as datas de abertura e fechamento dos atendimentos.

| Verificação | Ocorrências |
|---|---:|
| Históricos vazios | 0 |
| Eventos com campos ausentes ou nulos | 0 |
| Eventos com datas inválidas | 0 |
| Eventos anteriores à abertura | 0 |
| Eventos posteriores ao fechamento | 0 |
| Sequências duplicadas | 0 |
| Sequências fora de ordem | 0 |
| Eventos fora de ordem cronológica | 0 |

Foram encontrados cinco tipos de ação: `ABERTURA`, `ANALISE`, `DESPACHO`, `RETORNO AO CLIENTE` e `ENCERRAMENTO`.

Os canais dos eventos também foram comparados com os canais dos atendimentos, sem diferenças encontradas.

Com isso, os históricos apresentaram uma estrutura consistente nas verificações realizadas.

## 4. Anomalias Estatísticas e Regras de Negócio

### 4.1. Aumento de atendimentos em julho de 2025

Ao analisar a quantidade de atendimentos por mês, percebi que julho de 2025 teve um aumento muito acima dos meses próximos.

Em junho foram registrados 6.334 atendimentos, enquanto julho teve 18.061. Já em agosto, a quantidade caiu para 6.504.

Para entender melhor, separei os registros desses três meses por assunto.

| Assunto | Junho/2025 | Julho/2025 | Agosto/2025 |
|---|---:|---:|---:|
| DANO ELETRICO | 908 | 2.361 | 923 |
| FALTA DE ENERGIA | 1.957 | 6.186 | 2.018 |
| FATURA | 881 | 2.384 | 865 |
| GERACAO DISTRIBUIDA | 855 | 2.339 | 918 |
| LIGACAO NOVA | 834 | 2.406 | 917 |
| RELIGACAO | 899 | 2.385 | 863 |
| **Total** | **6.334** | **18.061** | **6.504** |

O aumento de julho foi de aproximadamente **185% em relação a junho**.

O que mais chamou atenção foi que o crescimento aconteceu em todos os assuntos, e não apenas em um tipo de atendimento.

Isso indica que o aumento foi geral. Pode ter acontecido algum evento específico nesse período ou alguma mudança na forma de registrar os atendimentos, mas não tenho informações suficientes para confirmar a causa.

Por isso, considerei esse aumento um ponto que merece investigação, sem classificá-lo diretamente como erro.

### 4.2. Verificação de datas e sequências

Além da análise mensal, também procurei situações que poderiam indicar problemas no funcionamento dos atendimentos, como:

- Fechamento anterior à abertura.
- Eventos registrados fora do período do atendimento.
- Sequências repetidas ou com números faltando.
- Eventos fora da ordem cronológica.
- Atendimentos com duração superior a 30 dias.

Não encontrei nenhuma dessas situações.

Ainda assim, algumas regras mais específicas precisam ser confirmadas, principalmente em relação à ordem esperada das ações e à obrigatoriedade de determinados eventos.

## 5. Plano Recomendado de Saneamento

Com base nos resultados, organizei algumas recomendações para os pontos encontrados e para evitar problemas em futuras cargas.

| Situação | Recomendação | Prioridade |
|---|---|---|
| Notas de satisfação nulas | Verificar se a nota é obrigatória ou se pode ficar vazia quando o cliente não responde | Baixa/Média |
| Aumento em julho de 2025 | Investigar o motivo do crescimento e verificar se houve algum evento ou alteração no registro dos dados | Média |
| Protocolos | Continuar verificando duplicações em futuras cargas | Preventiva |
| Datas | Manter as verificações de abertura, fechamento e duração | Preventiva |
| Categorias | Manter a padronização dos canais, assuntos e subassuntos | Preventiva |
| Históricos | Continuar verificando datas e sequências dos eventos | Preventiva |

### Cuidados na camada Bronze

Como essa etapa do projeto envolve a ingestão do arquivo na camada Bronze, considero importante manter os dados da forma como vieram da origem.

Por exemplo, não seria correto substituir automaticamente as notas nulas por zero, porque isso poderia alterar o significado dos dados. Da mesma forma, não faria sentido excluir os atendimentos de julho de 2025 apenas porque houve um aumento na quantidade.

Esses pontos devem ser analisados antes de qualquer tratamento.

A auditoria foi realizada localmente em Python. A execução do notebook e a gravação dos dados no Databricks ainda não foram validadas, pois o ambiente estava sem recursos computacionais disponíveis.

### Conclusão

De forma geral, o arquivo `atendimentos.json` apresentou bons resultados nas verificações de qualidade realizadas.

Não foram encontrados protocolos duplicados, datas inválidas, campos ausentes ou problemas na organização dos históricos.

Os dois pontos que merecem mais atenção são as **9.566 notas de satisfação nulas** e o **aumento de atendimentos em julho de 2025**.

Antes de fazer qualquer correção, seria importante entender melhor essas situações e confirmar as regras de negócio. Por enquanto, a recomendação é manter os dados originais preservados na camada Bronze e utilizar essa análise como referência para a próxima etapa do projeto.
