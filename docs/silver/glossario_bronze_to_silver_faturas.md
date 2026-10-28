# Glossário do notebook Bronze → Silver de faturas

**Público:** pessoas que vão acompanhar o notebook pela primeira vez, mesmo sem experiência com Databricks ou engenharia de dados.

**Objetivo:** explicar as siglas, os conceitos, as funções e os campos utilizados no tratamento de faturas. Os exemplos estão ligados ao trabalho realizado no projeto V-Energy.

**Escopo:** este documento explica a implementação e a migração inicial registradas no [notebook de faturas](../../data-engineering/bronze_to_silver/bronze-to-silver-faturas-corrigido.ipynb), com 92 células e outputs históricos preservados. As quantidades apresentadas pertencem à extração auditada; não são limites fixos para outras entregas.

Este arquivo é documentação. Para lê-lo ou acrescentar explicações ao notebook, **não é necessário executar células nem clicar em Run All**.

## Como consultar

- Se a dúvida for sobre o projeto e suas camadas, começar pelas Seções 1–3.
- Para entender rastreabilidade e qualidade, consultar as Seções 4–5.
- Para interpretar datas, dinheiro e cruzamentos, consultar as Seções 6–8.
- Para acompanhar o código, consultar as Seções 9–12.
- Para entender versões, campos e números publicados, consultar as Seções 13–15.

---

## 1. Mapa do processo e das responsabilidades

### Engenharia de dados

Área que organiza a coleta, o armazenamento, a transformação e a disponibilização dos dados. Neste trabalho, sua função é transformar faturas brutas em tabelas com tipos, regras e evidências de qualidade conhecidos.

### Arquitetura Medalhão

Organização dos dados em camadas com responsabilidades diferentes:

| Camada | Significado e finalidade | Aplicação neste projeto |
| :--- | :--- | :--- |
| Landing | Local onde os arquivos chegam antes da ingestão. | Arquivos como `faturas.csv` são disponibilizados no volume de entrada. |
| Bronze | Camada que preserva o conteúdo ingerido e seus metadados. | `v-energy.bronze.tb_faturas` mantém as onze colunas de negócio como texto, inclusive as ocorrências ainda não tratadas. |
| Silver | Camada de limpeza, padronização, tipagem, validação e tratamento de qualidade. | O notebook interpreta datas e dinheiro, verifica referências, preserva os originais e separa as pendências cadastrais. |
| Gold | Camada de modelagem e agregação para responder às perguntas de negócio. | Deve utilizar os dados tratados segundo o contrato e a cobertura documentados. A Gold não foi implementada ou validada por este notebook. |

Passar de uma camada para outra não é apenas copiar e renomear uma tabela. A mudança precisa ter regras e validações que expliquem o que foi feito.

### Pipeline, fluxo e etapa

**Pipeline** é a sequência de operações que leva os dados da origem ao resultado. **Fluxo** é usado com sentido semelhante. Uma **etapa** é uma parte dessa sequência, como interpretar dinheiro ou conferir chaves.

O processo histórico deste trabalho foi:

```text
Bronze de faturas + referências de cadastro e leituras
    → exploração e decisões
    → transformação e candidata Silver
    → validação em memória
    → tabelas de revisão e conferência
    → publicação nos dois destinos finais
```

As tabelas de revisão fizeram parte da migração inicial. Esse desenho histórico não significa que toda nova carga precise criar outras revisões ou republicar a revisão antiga.

### ETL e ELT

- **ETL — Extract, Transform, Load:** extrair, transformar e carregar.
- **ELT — Extract, Load, Transform:** extrair, carregar e depois transformar no ambiente de dados.

O trecho estudado transforma dados já carregados na Bronze e grava a Silver. Ele não executa, sozinho, todo o processo desde os sistemas de origem.

---

## 2. Siglas e nomes frequentes

| Sigla ou nome | Significado | Como aparece no trabalho |
| :--- | :--- | :--- |
| UC | Unidade Consumidora. | Identifica a unidade à qual a fatura e a leitura se referem. Não equivale necessariamente a uma pessoa ou CPF. |
| ID | Identificador. | `id_fatura` identifica a fatura; `id_uc`, a unidade consumidora. O identificador não determina, sozinho, a ordem temporal dos acontecimentos. |
| CSV | Comma-Separated Values, formato de texto tabular com delimitador. | O nome não obriga o uso de vírgula: a ingestão de `faturas.csv` usa ponto e vírgula. Exportações de resultados podem usar vírgula. |
| SQL | Structured Query Language, linguagem de consulta e manipulação de dados. | Usada em `DESCRIBE HISTORY`, `SELECT` e `CREATE OR REPLACE TABLE`. |
| Spark | Apache Spark, mecanismo de processamento distribuído. | Executa consultas e transformações sobre as tabelas. |
| PySpark | Interface Python do Spark. | Permite escrever transformações como `select`, `join` e `groupBy` usando Python. |
| Spark Connect | Interface que separa o cliente que escreve o código do servidor que executa o Spark. | Explica a classe `pyspark.sql.connect.dataframe.DataFrame` e diferenças de suporte entre chamadas. Esse nome de classe não é um erro. |
| Databricks | Plataforma de dados que integra notebooks, processamento e tabelas. | Ambiente em que o notebook foi executado e os resultados foram gravados. |
| Unity Catalog | Camada de organização, governança e controle de acesso aos objetos de dados no Databricks. | Organiza catálogo, schema e tabela. Em outros contextos do Databricks, a abreviação UC também pode significar Unity Catalog; em `id_uc`, significa Unidade Consumidora. |
| MDY | Month, Day, Year: mês, dia, ano. | Convenção adotada para emissão com hífen e ano no fim. |
| DMY | Day, Month, Year: dia, mês, ano. | Convenção adotada para emissão com barras ou pontos; também foi testada para hífen durante a investigação. |
| ISO 8601 | Padrão de representação de datas e horários. | A data `2023-03-10` está na ordem ano-mês-dia e representa 10 de março de 2023. |
| UTC | Coordinated Universal Time, referência de tempo mundial. | O sufixo `Z` de um timestamp indica UTC. Um horário exibido sem fuso não deve ser assumido automaticamente como UTC ou horário de Fortaleza. |
| BRL | Código da moeda real brasileiro. | Os campos financeiros auditados estão em reais. `R$` é o símbolo da moeda. |
| kWh | Quilowatt-hora, unidade de energia. | Aparece em leituras e nas análises de consumo. Não há um campo de kWh faturado nas onze colunas de faturas. |
| BI | Business Intelligence, análise e apresentação de informações para apoiar decisões. | Pode consumir indicadores derivados da Gold. |
| UTF-8 | Codificação de texto que representa caracteres como letras acentuadas. | Faz parte do contexto de leitura dos arquivos; não é um tratamento de conteúdo da Silver. |
| JSON | JavaScript Object Notation, formato de dados estruturados. | É o formato interno do arquivo `.ipynb` e também pode representar resultados e configurações. |
| ACID | Atomicidade, Consistência, Isolamento e Durabilidade. | Propriedades transacionais associadas ao Delta Lake; explicadas na Seção 12. |

Os prefixos `FT`, `FTX`, `LT` e semelhantes são partes dos identificadores da entrega. O notebook não recebeu uma definição oficial que autorize traduzir `FTX` como fraude, cancelamento ou duplicata.

---

## 3. Notebook, arquivos e objetos de dados

| Termo | Explicação e finalidade | Exemplo |
| :--- | :--- | :--- |
| Notebook | Documento executável que reúne código, explicações e resultados. | Um único notebook pode ler e gravar várias tabelas. |
| Célula de código | Bloco que executa comandos. | Uma célula que contém `saveAsTable` pode gravar dados. |
| Célula Markdown | Bloco de texto formatado para explicar o trabalho. | Textos sobre objetivo, diagnóstico e decisão de cada seção. |
| Output | Resultado exibido por uma execução. | Schema, tabela de contagens ou mensagem de validação. Um output salvo documenta uma execução anterior; não consulta automaticamente os dados atuais. |
| `.ipynb` | Extensão do arquivo de notebook. | Armazena células, metadados e, quando incluídos na exportação, outputs. Não armazena o estado completo das variáveis da sessão. |
| `.md` | Extensão de um arquivo Markdown. | A auditoria e este glossário são documentação, sem execução de pipeline. |
| `.py` | Extensão de arquivo com código Python. | Um notebook pode ser exportado em um formato Python compatível com Databricks. |
| Tabela | Objeto que armazena dados organizados em linhas e colunas. | `v-energy.silver.tb_faturas`. Criar outra tabela não exige criar outro notebook. |
| View | Consulta armazenada com nome, que apresenta dados de outros objetos. | É diferente de uma tabela materializada. Não foi necessário criar uma view permanente nesta migração. |
| Fonte ou origem | Objeto de onde os dados são lidos. | A Bronze é a fonte da transformação Silver. |
| Destino | Objeto que recebe o resultado de uma gravação. | `v-energy.silver.tb_faturas_pendentes_cadastro`. |
| Catálogo | Primeiro nível de organização dos objetos. | `v-energy`. |
| Schema como namespace | Segundo nível de organização, semelhante a uma pasta lógica de tabelas. | `bronze` e `silver`. |
| Schema como estrutura | Lista dos campos, seus tipos e propriedades. | `df.schema` ou `printSchema()` descrevem colunas como `valor_total: decimal(18,2)`. |
| Volume | Objeto usado para disponibilizar arquivos no ambiente de dados. | O caminho de landing é um volume; não é a própria tabela Bronze. |
| Caminho de arquivo | Endereço de um arquivo ou diretório. | Um caminho começando por `/Volumes/...` identifica arquivos; `v-energy.silver.tb_faturas` é nome de tabela. |

### Leitura do nome completo de uma tabela

```text
v-energy.silver.tb_faturas
    │       │       └── tabela
    │       └────────── schema de organização
    └────────────────── catálogo
```

Os backticks em `` `v-energy`.`silver`.`tb_faturas` `` delimitam os identificadores no SQL. São especialmente importantes para o hífen de `v-energy` não ser interpretado como um operador.

---

## 4. Rastreabilidade, evidência e reprodução

### Rastreabilidade

É a capacidade de acompanhar um dado do resultado até sua origem e entender quais tratamentos foram aplicados. Ajuda a explicar uma data convertida, localizar um valor bruto e investigar por que uma fatura foi para a tabela de pendências.

Neste trabalho, a rastreabilidade combina:

| Recurso | O que permite acompanhar |
| :--- | :--- |
| `id_fatura` | Qual registro de negócio está sendo analisado. |
| `dados_originais` | Como estavam as onze colunas de negócio na Bronze. |
| `source_file` | Qual arquivo está registrado como origem. |
| `ingestion_datetime` | Quando ocorreu a ingestão na Bronze. |
| `versoes_bronze` | Quais versões de faturas, cadastro e leituras foram utilizadas. |
| `metodo_interpretacao_emissao` | Qual máscara ou convenção determinou a data de emissão. |
| `versao_regras` | Qual identificador do conjunto de regras foi registrado. |
| Histórico Delta | Quais operações de gravação ocorreram na tabela. |

**Exemplo real:** `FT000000056` trouxe `03-10-2023`. O resultado escolhe `2023-03-10` pela convenção MDY, registra o método, mantém a indicação de ambiguidade e preserva o texto `03-10-2023` no original. Assim, outra pessoa consegue compreender a transformação sem adivinhar a regra.

`dados_originais` preserva os valores como estavam na Bronze. Ele não é uma cópia byte a byte do CSV e não comprova, sozinho, que a ingestão anterior preservou todo o arquivo corretamente.

### Linhagem de dados

É o caminho de dependências entre arquivos, tabelas e transformações. A rastreabilidade ajuda a investigar um registro; a linhagem também descreve quais fontes alimentaram uma saída. A linhagem registrada neste notebook usa nomes, versões e metadados; isso não equivale à comprovação de que todas as fontes foram extraídas ao mesmo tempo.

### Metadado

É um dado que descreve outro dado ou seu processamento. `source_file` é metadado de origem; `ingestion_datetime` é metadado de ingestão. Eles não são valores financeiros nem datas de negócio da fatura.

### Evidência de execução

É um resultado que sustenta uma conclusão: uma tabela exportada, uma comparação sem diferenças ou o histórico de uma gravação. Escrever `OK` manualmente não seria evidência de teste; no notebook, as mensagens são emitidas depois de verificações programadas.

### Auditoria

É o registro organizado do que foi examinado, do que foi encontrado, das decisões e das verificações realizadas. O arquivo de auditoria permite revisar o processo sem depender da memória da conversa.

### Snapshot

É uma fotografia lógica dos dados em determinado estado. Neste caso, a leitura por uma versão Delta fixa mantém a referência ao mesmo estado da tabela durante a análise.

### Reprodutibilidade

É a possibilidade de repetir o processamento com as mesmas fontes, versões e regras e obter resultados equivalentes. Registrar apenas o número de linhas é insuficiente para isso. Também é necessário conhecer o código e as regras utilizadas.

### Idempotência

É a propriedade de repetir uma operação com as mesmas entradas sem acumular efeitos indesejados. Para este fluxo, significa não duplicar faturas ao reexecutar a substituição completa com os mesmos dados e regras. Pode surgir uma nova versão Delta mesmo quando o conteúdo de negócio permanece igual.

Uma nova ingestão pode mudar metadados, mesmo com negócio equivalente. Por isso, igualdade de negócio e igualdade de todas as colunas são verificações diferentes. Este documento não substitui um teste de reexecução quando a rotina for alterada.

---

## 5. Qualidade e decisões de tratamento

| Termo | Significado | Aplicação às faturas |
| :--- | :--- | :--- |
| Exploração ou perfilamento | Medição das características dos dados antes de definir tratamentos. | Contar formatos de emissão, ausências e repetições. |
| Diagnóstico | Interpretação das medições para entender uma ocorrência. | Distinguir ausência legítima de pagamento de falha de conversão. |
| Amostra | Subconjunto exibido para inspeção. | Dez linhas ajudam a conhecer os campos, mas não demonstram qualidade de toda a base. |
| Volumetria | Quantidade de registros de um universo. | 2.184.623 linhas Bronze, incluindo dois cabeçalhos internos. |
| Registro de negócio | Linha que representa uma ocorrência do domínio. | Uma fatura; o cabeçalho repetido não é uma cobrança. |
| Cabeçalho interno | Repetição dos nomes de colunas dentro dos dados. | Foi identificado somente quando os onze campos coincidiram exatamente com os nomes. |
| Completude | Presença dos valores esperados. | Identificador de fatura preenchido é necessário; pagamento pode estar ausente em uma fatura aberta. |
| Conformidade | Adequação ao formato, tipo ou domínio esperado. | Competência com formato `AAAA-MM`. |
| Validade de calendário | Existência de uma data no calendário. | `2025-02-30` tem aparência ISO, mas não é uma data válida. |
| Semântica | Significado de um dado no domínio de negócio. | A sentinela é uma data válida no calendário, mas significa ausência de pagamento. |
| Sintaxe | Regras formais de escrita do código ou de uma expressão. | Código sem erro de sintaxe ainda pode ter uma regra incorreta ou falhar ao executar no Spark. |
| Consistência | Coerência entre valores relacionados. | Status PAGA acompanhado de data real de pagamento. |
| Unicidade | Ausência de repetição de uma chave. | Cada `id_fatura` deve identificar uma única linha de negócio nesta extração. |
| Domínio | Conjunto de valores aceitos para um campo. | PAGA e EM ABERTO para status. |
| Regra de qualidade | Condição usada para aceitar ou investigar dados. | Bloquear uma carga com ID de fatura repetido. |
| Regra de negócio | Condição fundamentada no significado dos dados ou na política do projeto. | Definir como a ausência cadastral afeta a liberação analítica. |
| Contrato de dados | Conjunto explícito de estrutura, tipos, regras e limites de interpretação. | Define o que a candidata deve cumprir antes da publicação. Não é necessariamente um contrato jurídico. |
| Validação | Execução de verificações contra critérios definidos. | Comparar registros e conferir energia + tributos = total. |
| Homologação | Aprovação de um resultado para determinado uso, considerando critérios e limites conhecidos. | Um teste técnico é parte da avaliação; sozinho não confirma a verdade de todas as informações externas. |
| Hipótese ou suposição | Interpretação adotada sem confirmação completa da origem. | A convenção MDY para hífen é fundamentada pelas evidências, sem provar individualmente cada caso ambíguo. |
| Limpeza | Tratamento de conteúdo que precisa de correção ou separação. | Separar cabeçalhos do universo de negócio. |
| Normalização ou padronização | Uniformização de representações equivalentes. | Converter formatos monetários diferentes para o mesmo tipo. Não foi necessário alterar a caixa dos status observados. |
| Tipagem | Conversão para tipos adequados ao significado. | De texto monetário para DECIMAL(18,2). |
| Enriquecimento | Acréscimo de informação derivada ou obtida de uma referência. | Acrescentar um indicador de presença no cadastro, sem trazer seus atributos. |
| Parsing ou interpretação | Leitura de um texto segundo uma gramática ou máscara. | Interpretar `03-10-2023` como mês-dia-ano. |
| Duplicata exata | Repetição dos mesmos valores nas colunas escolhidas para comparar. | As onze colunas de negócio foram comparadas, sem considerar o timestamp como parte da identidade de negócio. |
| Deduplicação | Remoção de cópias segundo um critério definido. | Não foi aplicada às faturas porque não foram encontradas cópias exatas nem IDs repetidos. |
| Multiplicidade | Mais de um registro associado à mesma chave ou combinação. | Duas faturas de IDs distintos para a mesma UC e competência. Isso não comprova duplicação. |
| Sentinela | Valor especial usado para representar uma condição em vez de um valor real. | `9999-12-31` representa ausência de pagamento na extração analisada. |
| Anomalia | Ocorrência que merece investigação. | Pode ser erro, limitação da fonte ou comportamento legítimo. |
| Outlier ou valor extremo | Valor distante do padrão da distribuição. | Um total alto não foi excluído só por ser alto. |
| Flag ou indicador | Campo, normalmente booleano, que sinaliza uma condição. | `flag_uc_sem_cadastro` indica ausência de correspondência na referência utilizada. |
| Pendência cadastral | Fatura cuja UC não foi encontrada no cadastro disponível. | Foi preservada na tabela de pendências. |
| Quarentena | Termo geral para uma saída separada de dados que precisam de avaliação. | A tabela criada aqui tem escopo específico de pendência cadastral; ela não recebe automaticamente todo tipo de erro do pipeline. |
| Segregação | Separação de registros em grupos explícitos. | Separar faturas com e sem cadastro, reconciliando o total. |

### Identificar, sinalizar, tratar e recuperar

- **Identificar:** detectar e medir uma ocorrência.
- **Sinalizar:** registrar a ocorrência em um indicador ou classificação.
- **Tratar:** aplicar uma política explícita para seu uso ou destino.
- **Recuperar:** conseguir obter ou reconstruir a informação correta.

Enviar uma fatura para pendências trata seu destino no pipeline. Isso não recupera o cadastro ausente. Escolher uma data por convenção fornece uma interpretação operacional; não confirma a verdade externa de todas as datas ambíguas.

As categorias de problema podem se sobrepor. As 42 faturas em pares repetidos já pertencem às 32.285 pendências cadastrais. Somar os dois grupos produziria dupla contagem.

---

## 6. Datas, formatos e ausência de valores

### Datas de negócio e datas técnicas

| Campo ou conceito | O que representa | Distinção importante |
| :--- | :--- | :--- |
| Competência / `mes_referencia` | Período ao qual a fatura se refere. | Não é necessariamente o mês da emissão, do vencimento ou do pagamento. |
| `data_emissao` | Data informada para a emissão da fatura. | Pode exigir uma convenção de interpretação do texto. |
| `data_vencimento` | Data informada como limite para pagamento no prazo. | Não deve ser usada para inventar pagamento ausente. |
| `data_pagamento` | Data real informada para o pagamento. | Pode ser ausente em faturas abertas. |
| `ingestion_datetime` | Momento de ingestão na Bronze. | Não é a data da emissão nem a data oficial de extração do sistema de origem. |
| Timestamp do histórico Delta | Momento de uma operação registrada na tabela. | Não é um commit Git. Pode ser diferente do timestamp de ingestão. |
| Data de extração | Momento em que a origem gerou o conjunto de dados. | Não foi oficialmente fornecida no CSV para determinar a posição atual das faturas. |

### Máscara de data

É a regra que indica como cada parte do texto deve ser lida.

| Texto ou representação | Máscara Spark utilizada | Interpretação |
| :--- | :--- | :--- |
| `2023-03-10` | `yyyy-MM-dd` | 10 de março de 2023 |
| `10/03/2023` | `dd/MM/yyyy` | 10 de março de 2023 pela convenção DMY |
| `10.03.2023` | `dd.MM.yyyy` | 10 de março de 2023 pela convenção DMY |
| `03-10-2023` | `MM-dd-yyyy` | 10 de março de 2023 pela convenção MDY |
| `03-10-2023` | `dd-MM-yyyy` | 3 de outubro de 2023, candidata DMY testada no diagnóstico |

As letras da máscara têm significado e diferenciam maiúsculas de minúsculas. No Spark, `MM` representa mês e `mm`, minutos. Expressões explicativas como `AAAA-MM-DD` ou `YYYY-MM-DD` não devem ser copiadas automaticamente como máscaras técnicas: usar as máscaras exatas do código.

### Ambiguidade

Uma representação é ambígua quando admite mais de um significado. `03-10-2023` pode produzir duas datas válidas. Já `03-03-2023` produz a mesma data nas duas ordens.

O notebook preserva a ambiguidade original mesmo depois de aplicar a convenção. Ter `data_emissao` preenchida e `flag_emissao_original_ambigua = true` é intencional.

### Cronologia

É a ordem temporal dos acontecimentos. Os critérios adotados verificam emissão não posterior ao vencimento e, quando há pagamento real, emissão não posterior ao pagamento. A mesma candidata precisa passar nas duas comparações; não basta usar uma interpretação para cada teste.

### NULL, vazio, texto `null` e zero

| Representação | Significado técnico | Tratamento ou observação |
| :--- | :--- | :--- |
| `NULL` | Ausência de valor. | Não equivale a zero ou a uma data real. |
| `""` | Texto vazio. | É diferente de NULL, embora um leitor CSV possa converter um campo vazio em nulo durante a ingestão. |
| `"   "` | Texto composto por espaços. | Precisa ser medido separadamente antes de decidir uma normalização. |
| `"null"` | Palavra escrita em um campo de texto. | Não é automaticamente um nulo real. A exportação CSV também pode usar uma representação textual para exibir nulos. |
| `0` | Valor numérico conhecido. | Não deve ser usado para preencher uma ausência financeira sem regra de negócio. |
| `9999-12-31` | Data especial usada como sentinela. | É um calendário válido, mas não representa um pagamento real nesta extração. |

Uma condição comparando NULL com `==` normalmente resulta em desconhecido, não em verdadeiro. Por isso, o código usa `isNull`, `isNotNull` ou comparações específicas para lidar com ausência.

---

## 7. Dinheiro e precisão

### DECIMAL(18,2)

Tipo numérico decimal com até 18 dígitos de precisão total e 2 casas decimais. Nesse caso, até 16 dígitos ficam antes do separador decimal, sem contar o sinal.

**Precisão** é a quantidade total de dígitos. **Escala** é a quantidade de casas decimais. O tipo foi escolhido para representar centavos e permitir conciliação decimal exata dos valores aceitos.

### DOUBLE ou FLOAT

São tipos de ponto flutuante que podem representar números de forma aproximada. Não foram escolhidos para os valores monetários do notebook.

### Separador decimal e separador de milhares

No texto `R$ 1.234,56`, a vírgula separa os centavos e o ponto agrupa milhares. Em `1234.56`, o ponto é decimal. Remover todos os pontos sem reconhecer o formato poderia transformar um valor correto em outro.

### Gramática monetária

É o conjunto de formas textuais que a conversão aceita. O notebook reconhece decimal com ponto e duas casas e representações em reais com vírgula, com ou sem agrupamento de milhares. Um formato desconhecido precisa ser investigado.

### Cast, conversão segura e overflow

- **Cast:** conversão de um valor para outro tipo.
- **Conversão segura:** tentativa que permite identificar falhas, em vez de produzir um valor inventado. `try_cast` pode resultar em NULL quando o texto não pode ser convertido ou o valor não cabe no tipo.
- **Overflow:** valor que excede a capacidade do tipo escolhido.

O NULL de uma conversão malsucedida é um sinal para validação. Ele não prova que o dado original representava ausência legítima.

### Conciliação e reconciliação

Neste material:

- **Conciliação por fatura:** verificar `valor_energia + tributos = valor_total` em cada registro.
- **Reconciliação do fluxo:** conferir registros, quantidades e dinheiro entre origem, candidata, saídas e tabelas persistidas.

Exemplo didático de conciliação: R$ 100,00 de energia + R$ 20,00 de tributos = R$ 120,00 de total.

Na reconciliação real desta execução:

```text
2.184.621 faturas = 2.152.336 com cadastro + 32.285 pendentes

R$ 676.675.147,58 = R$ 666.482.773,76 + R$ 10.192.373,82
```

Uma soma global igual pode esconder diferenças que se compensam. Por isso também foram comparados valores por fatura e por competência/status. A igualdade aritmética não certifica tarifas, impostos legais ou legitimidade da cobrança.

---

## 8. Chaves, cruzamentos e cardinalidade

### Chave e chave composta

Uma **chave** é um campo ou conjunto de campos usado para identificar ou relacionar registros. Uma **chave composta** usa mais de um campo, como `(id_uc, mes_referencia)`.

`id_fatura` é a chave de negócio validada para as faturas. O par UC/mês não é único em todo o conjunto bruto e, portanto, não pode ser assumido como identificador único de fatura.

Essa validação no notebook não significa que uma restrição de chave primária tenha sido declarada e automaticamente imposta pelo banco.

### Grão ou granularidade

É o significado de uma linha da tabela. O grão adotado é uma linha por fatura identificada por `id_fatura`. Confundir o grão com uma linha por UC/mês poderia eliminar cobranças diferentes.

### Join ou cruzamento

Operação que combina dados de dois conjuntos por uma condição de correspondência. No notebook, verifica-se se a UC da fatura aparece no cadastro e se o par UC/mês aparece nas leituras.

| Tipo | Funcionamento | Uso ou efeito neste contexto |
| :--- | :--- | :--- |
| Left join | Preserva todas as linhas da esquerda e acrescenta o que corresponder à direita. | Permite manter as faturas sem cadastro e sinalizar a ausência. |
| Inner join | Mantém apenas combinações com correspondência nos dois lados. | Foi usado para examinar faturas dos pares repetidos. Usá-lo diretamente contra cadastro eliminaria da saída as faturas sem referência. |

### Cardinalidade

Descreve quantos registros podem corresponder a uma chave e como isso afeta o cruzamento. Um relacionamento pode ser um para um, um para muitos ou muitos para muitos.

**Exemplo didático:** uma fatura de R$ 100,00 é cruzada com duas linhas cadastrais da mesma UC. O resultado pode apresentar duas linhas de R$ 100,00, fazendo a soma parecer R$ 200,00. A fatura não mudou, mas o cruzamento multiplicou sua representação.

O notebook usa chaves distintas do cadastro e uma linha por par de leituras para evitar essa multiplicação. Depois confere a quantidade de faturas antes e depois dos joins.

### Projeção de chaves distintas

É selecionar somente as colunas usadas como referência e retirar repetições desse conjunto de chaves. Ela responde se a chave existe. Não resolve qual nome, endereço ou classe cadastral deveria prevalecer entre registros conflitantes.

### Integridade referencial

É a coerência entre um identificador e a referência à qual ele deveria estar relacionado. Neste trabalho, a checagem é implementada pelo código de cruzamento e pelos indicadores, não por uma suposição de que todo identificador com formato válido possui cadastro.

### Órfão e correspondência

Um registro é chamado de **órfão** quando não encontra a referência esperada no conjunto consultado. A expressão é relativa à referência disponível. A ausência no cadastro Bronze não prova que a UC inexista no sistema oficial.

Encontrar a UC no cadastro e encontrar o par em leituras são verificações diferentes. Também não garantem que os atributos cadastrais e o consumo estejam tratados.

---

## 9. Tipos e leitura do schema

| Tipo ou propriedade | Significado | Exemplo |
| :--- | :--- | :--- |
| STRING | Texto. | O original `R$ 1.234,56` ainda precisa ser interpretado. |
| DATE | Data de calendário sem horário. | `2023-03-10`. |
| TIMESTAMP | Data e horário, com interpretação dependente das regras de tempo da sessão e do tipo. | `ingestion_datetime`. Sua exibição pode variar com o fuso. |
| DECIMAL(18,2) | Número decimal com precisão e escala definidas. | `valor_total` depois da conversão. |
| INTEGER / INT | Número inteiro. | Versões Bronze registradas como 0. |
| BOOLEAN | Valor lógico verdadeiro, falso ou, quando permitido, NULL. | Um indicador de ausência cadastral. |
| STRUCT | Campo que contém outros campos nomeados. | `dados_originais` reúne as onze colunas brutas dentro de uma coluna. |
| `nullable = true` | O schema permite que o campo contenha nulo. | Não significa que existam nulos reais no conjunto. |
| `nullable = false` | O schema declara o campo como não nulo. | É uma propriedade estrutural; as verificações de conteúdo continuam importantes. |

### Como ler `printSchema()`

```text
root
 |-- valor_total: decimal(18,2) (nullable = true)
 |-- dados_originais: struct (nullable = false)
 |    |-- valor_total: string (nullable = true)
```

`root` é o início da estrutura, não uma coluna de negócio. A indentação mostra que o segundo `valor_total` está dentro de `dados_originais`. Assim, a saída pode conter o valor tipado e sua representação bruta ao mesmo tempo.

---

## 10. DataFrames e funções usadas no código

### DataFrame e prefixo `df_`

DataFrame é uma representação tabular manipulada pelo Spark. Os nomes que começam por `df_` são uma convenção usada para reconhecer essas variáveis.

Quando o notebook diz **em memória**, significa que o resultado intermediário ainda não foi gravado como tabela de saída. Isso não quer dizer que todos os milhões de registros estejam materializados na memória do processo Python: um DataFrame pode representar um plano de execução distribuída.

### Avaliação preguiçosa: transformações e ações

O Spark pode construir um plano sem executar imediatamente todas as etapas. Operações como `select`, `filter` e `withColumn` são transformações. Chamadas como `count()`, `first()` e a exibição com `display()` solicitam resultados e podem disparar processamento.

Uma referência de DataFrame aparecer no output não significa que todas as suas linhas tenham sido verificadas. Isso ajuda a entender por que um erro pode aparecer somente em uma operação posterior.

### Leitura, criação e exibição

| Recurso | Para que serve | Observação |
| :--- | :--- | :--- |
| `spark.read` | Preparar uma leitura de dados. | As opções configuram como o DataFrame será lido. |
| `spark.table` / `.table` | Obter um DataFrame a partir de uma tabela ou view nomeada. | Na leitura com `versionAsOf`, solicita a versão especificada da tabela Delta. |
| `spark.sql` | Executar ou preparar um comando SQL pelo Spark. | Pode consultar ou gravar: o efeito depende do comando SQL, não apenas do nome da função. |
| `createDataFrame` | Construir um DataFrame a partir de uma estrutura aceita pela API. | Usado para apresentar resumos montados em Python. |
| `printSchema` | Exibir nomes, tipos e estrutura dos campos. | Não mostra os valores de todas as linhas. |
| `simpleString` | Obter a representação textual de um tipo. | Comparar `decimal(18,2)` com o tipo esperado não altera os dados. |
| `display` | Mostrar um resultado no notebook Databricks. | Pode solicitar processamento, mas não é uma gravação em tabela por si só. |

### Seleção e construção de colunas

| Função ou expressão | Para que serve | Observação |
| :--- | :--- | :--- |
| `F` | Apelido de `pyspark.sql.functions`. | Agrupa funções de expressão Spark. |
| `F.col("campo")` | Referenciar uma coluna. | Não é o conteúdo de uma linha Python específica. |
| `F.lit(valor)` | Criar uma expressão com valor constante. | Registrar o número da versão de regras/fontes em cada linha. |
| `select` | Selecionar colunas e expressões. | Define quais campos entram na candidata. |
| `alias` | Dar nome a uma expressão no resultado. | Renomear a data convertida como `data_emissao`. |
| `withColumn` | Adicionar ou substituir uma coluna no DataFrame resultante. | Não altera a tabela de origem por si só. |
| `withColumnRenamed` | Mudar o nome de uma coluna no resultado. | Apresentar `count` como `quantidade`. |
| `drop` | Retirar uma coluna do DataFrame resultante. | Não apaga uma tabela nem exclui a coluna da Bronze por si só. |
| `F.struct` | Agrupar campos em uma estrutura nomeada. | Construir `dados_originais` e `versoes_bronze`. |

### Condições e ausências

| Função ou operador | Para que serve | Aplicação |
| :--- | :--- | :--- |
| `filter` | Manter linhas que atendem a uma condição verdadeira. | Separar as pendências cadastrais. Condição desconhecida por NULL não é automaticamente verdadeira. |
| `F.when(...).otherwise(...)` | Definir resultados condicionais. | Classificar formato de pagamento. Sem resultado alternativo, linhas não atendidas podem ficar NULL. |
| `isNull` / `isNotNull` | Verificar ausência/presença. | Diferenciar pagamento real de ausência. |
| `isin` | Verificar se o valor pertence a uma lista. | Validar os status aceitos. |
| `eqNullSafe` | Comparar considerando dois nulos como iguais. | Evitar que a identificação de cabeçalhos produza condições desconhecidas por causa de nulos. |
| `F.coalesce` | Retornar o primeiro argumento não nulo. | Tratar o resultado lógico do indicador de atraso quando não há pagamento. Não comprova que o valor escolhido tenha o significado correto. |
| `&`, `\|` e `~` | Combinar condições Spark com E, OU e NÃO. | As comparações precisam dos parênteses usados no código. Não são substituídos livremente por `and`, `or` e `not` do Python. |

### Texto, formatos e conversões

| Função | Para que serve | Aplicação |
| :--- | :--- | :--- |
| `trim` | Remover espaços das extremidades na expressão resultante. | Medir vazios e espaços, sem alterar automaticamente o original. |
| `lower` | Converter o texto para minúsculas na expressão. | Identificar a palavra literal `null` durante a exploração. |
| `rlike` | Testar correspondência com uma expressão regular. | Identificar a aparência de datas, moedas e IDs. |
| `regexp_replace` | Substituir trechos encontrados por expressão regular. | Remover agrupamento de milhares somente depois de reconhecer a gramática. |
| `try_to_timestamp` | Tentar interpretar texto segundo uma máscara de data/horário. | Calendários não interpretáveis produzem NULL nas tentativas usadas no notebook. |
| `to_date` | Obter um valor DATE a partir de uma expressão. | Retirar a parte de horário da interpretação auxiliar. |
| `date_format` | Representar uma data como texto segundo uma máscara. | Extrair `yyyy-MM` para comparar com a competência. |
| `expr` | Usar uma expressão SQL dentro de uma transformação PySpark. | Executar `try_cast` na conversão monetária. |
| `try_cast` | Tentar converter para um tipo sem inventar valor em caso de falha de conversão. | Converter o texto normalizado para DECIMAL(18,2). |

### Agrupamento, quantidade e ordenação

| Função | Para que serve | Observação |
| :--- | :--- | :--- |
| `groupBy` | Formar grupos por uma ou mais colunas. | Agrupar por status ou por UC/competência. |
| `agg` | Calcular medidas sobre todo o conjunto ou sobre cada grupo. | Contar problemas e somar valores. |
| `df.count()` | Retornar o número de linhas do DataFrame. | É uma ação. |
| `F.count("*")` | Expressão agregadora que conta linhas. | Pode ser usada em `agg` ou em uma janela. |
| `F.count("coluna")` | Contar valores não nulos daquela coluna. | Não deve ser confundido com total de linhas se houver nulos. |
| `countDistinct` | Contar valores ou combinações distintas. | Conferir unicidade; nulos exigem verificação própria. |
| `sum` | Somar valores. | Ignora nulos; se todos forem nulos, o resultado pode ser NULL. Por isso a interpretação deve ser validada antes de confiar na soma. |
| `min` / `max` | Encontrar menor/maior valor. | Mostrar intervalos monetários e de datas. |
| `orderBy` / `desc` | Ordenar resultados, inclusive de forma decrescente. | Apresentar categorias mais frequentes primeiro. |
| `limit` | Restringir a quantidade de linhas retornadas. | Uma amostra limitada não é necessariamente aleatória ou representativa. |
| `first` | Obter a primeira linha do resultado. | Após uma agregação global, pode trazer o resumo de toda a base em uma linha. |
| `asDict` | Converter uma linha retornada para dicionário Python. | Permite identificar quais contagens de falha são diferentes de zero. |

### Janelas e partições

`Window.partitionBy("id_uc", "mes_referencia")` organiza grupos lógicos para um cálculo analítico. `over` aplica o cálculo sobre essa janela.

O notebook conta quantas faturas pertencem ao mesmo par e mantém uma linha por fatura. Isso é diferente de `groupBy`, que produz uma linha agregada por grupo.

**Partição de janela não é a mesma coisa que partição física de armazenamento.** O campo `partitionColumns` do Delta descreve a organização física da tabela; os arquivos anuais de leituras também são uma forma de organização da origem. São conceitos relacionados, mas diferentes.

### União e comparação de conjuntos

| Operação | Funcionamento | Uso |
| :--- | :--- | :--- |
| `distinct` | Retirar repetições das colunas selecionadas. | Construir a referência de chaves. |
| `unionByName` | Reunir linhas alinhando colunas por nome. | Juntar as duas saídas para reconciliação. Preserva repetições; não deduplica automaticamente. |
| `exceptAll` | Retornar diferenças preservando a multiplicidade dos registros. | Detectar perdas, acréscimos ou alterações no conteúdo. |

`exceptAll` é aplicado nos dois sentidos porque uma direção identifica apenas os registros exclusivos de um lado. O código seleciona explicitamente a mesma ordem de colunas, pois a comparação se alinha por posição. A comparação ignora a ordem de apresentação das linhas, mas considera quantas cópias de cada registro existem.

**Multiconjunto** é o nome técnico de um conjunto que também considera a quantidade de repetições. Duas tabelas podem ter os mesmos valores distintos e, ainda assim, quantidades diferentes de cópias.

### Expressão regular ou regex

É uma linguagem para descrever padrões de texto. No padrão `r"^FTX?[0-9]+$"`:

- `^` indica início do texto e `$`, fim.
- `FT` deve aparecer literalmente.
- `X?` permite zero ou uma ocorrência de X.
- `[0-9]+` exige um ou mais dígitos.
- O prefixo Python `r` ajuda a escrever barras invertidas sem escapes adicionais da string.

Isso aceita identificadores começando por FT ou FTX seguidos de números. Validar o padrão não demonstra existência cadastral nem legitimidade da fatura.

Em `r"\d{4}-\d{2}-\d{2}"`, `\d` indica dígito e `{4}` exige quatro ocorrências. Em regex, o ponto simples tem significado especial; `\.` é usado quando se deseja um ponto literal.

---

## 11. Sessão, variáveis e mensagens de erro

### Sessão e estado em memória

A sessão é o contexto em que o código está sendo executado. Variáveis, funções e referências de DataFrames podem desaparecer quando ela é reiniciada. As tabelas Delta já gravadas não desaparecem por esse motivo.

Salvar o notebook preserva seu documento e, conforme a exportação, seus outputs. Não preserva automaticamente todas as variáveis prontas para uso em outra sessão.

### Marcadores de validação

**Regra de bloqueio de pagamento (`pagamento_nao_interpretado`).** Verificação da Seção 10, acrescentada na correção da issue #27. Se a data tipada e o motivo de ausência estiverem ambos nulos, a candidata é bloqueada: não há evidência de uma ausência reconhecida. Um texto inválido ou uma data impossível não podem receber o mesmo tratamento de um nulo original ou da sentinela. Essa regra é uma condição de validação em memória, não uma nova coluna persistida.

`VALIDACOES_CANDIDATA_OK`, `REVISAO_PERSISTIDA_OK` e `PUBLICACAO_FATURAS_OK` são variáveis booleanas usadas como marcadores do andamento da sessão. Elas não são colunas das tabelas.

O código consulta `globals().get(...)` para verificar se uma variável existe e qual seu valor. Ausência ou False interrompe uma etapa dependente. Atribuir True manualmente não executa os testes e não comprova aprovação.

### Dicionário, lista, conjunto e loop

- **Dicionário (`dict`):** associa chaves a valores; usado para guardar versões, destinos e DataFrames.
- **Lista (`list`):** sequência ordenada; usada no plano de gravação.
- **Conjunto (`set`):** coleção de valores únicos; usada para conferir quais destinos foram validados.
- **Loop `for`:** repete instruções; neste notebook, percorre campos ou tabelas. Isso não significa necessariamente processar cada uma das milhões de linhas em Python.

Algumas construções Python ajudam a ler as células:

| Construção | Significado no código |
| :--- | :--- |
| `=` | Atribuir um valor ou objeto a uma variável. |
| `==` | Construir ou realizar uma comparação de igualdade, conforme os objetos envolvidos. |
| `f"...{variavel}..."` | Montar um texto incluindo o valor de uma variável. |
| `[expressao for item in lista]` | Construir uma lista repetindo uma expressão para cada item. |
| `*lista` em uma chamada | Passar os itens da lista como argumentos separados. Em `select(*colunas)`, seleciona as colunas listadas. |
| `get` / `items` / `update` | Consultar valores, percorrer pares ou atualizar um dicionário Python. |
| `append` / `extend` de uma lista | Acrescentar um item ou vários itens a uma lista Python. Não são o modo de gravação Spark `append`. |
| `add` de um conjunto | Registrar um elemento no conjunto, como o nome de um destino validado. |
| `#` | Iniciar um comentário Python. O comentário explica, mas não executa a regra. |

### Leitura das mensagens

| Mensagem ou termo | Significado neste contexto | Interpretação |
| :--- | :--- | :--- |
| `ValueError` | O código detectou uma condição que não permite continuar. | Pode ser uma proteção planejada, como destino já existente ou validação não concluída. |
| `NameError` | Uma variável ou função não está definida. | Pode indicar célula anterior não executada ou sessão reiniciada. |
| `UNSUPPORTED_OPERATION` | A chamada não é suportada pelo ambiente/interface utilizados. | O alias `errorifexists` não foi aceito naquela implementação Spark Connect. |
| `TABLE_OR_VIEW_ALREADY_EXISTS` | Houve tentativa de criar um objeto cujo nome já existe. | Não comprova igualdade dos dados; foi necessário ler e conferir as tabelas existentes. |
| Traceback | Caminho da falha no código. | A linha que efetivamente dispara o erro ajuda a distinguir leitura, validação e gravação. |
| Trace ID | Identificador técnico para correlacionar uma ocorrência em logs. | Não é ID de fatura, versão Delta ou commit Git. |
| SQLSTATE | Código padronizado de uma classe de erro SQL. | Ajuda a classificar a falha, mas não altera o tratamento de negócio. |
| `OK` | Mensagem produzida pelo código após uma condição de sucesso. | Deve ser lida junto com o teste executado e o resultado exportado. |

### Run All

Executa as células do notebook em sequência. Pode recalcular consultas e também gravar tabelas; não é apenas um botão para atualizar a apresentação.

O notebook histórico conserva uma publicação baseada em revisões fixas. Seus outputs podem ser substituídos ao reexecutar. Para explicar o processo, editar as células Markdown não exige Run All.

---

## 12. Persistência, modos de gravação e transações

### Persistir, materializar e publicar

- **Persistir:** salvar um resultado em armazenamento durável, como uma tabela Delta.
- **Materializar:** produzir e armazenar os dados calculados, em vez de manter somente a definição de uma consulta.
- **Publicar:** disponibilizar a saída no destino acordado. Neste trabalho, significa gravar tabelas finais no Databricks, não publicar um site ou fazer push no GitHub.

As tabelas finais criadas com `AS SELECT` armazenam o resultado. Uma consulta posterior à final não volta automaticamente à revisão. Entretanto, o código que executa novamente aquele `AS SELECT` ainda depende da fonte que ele referencia.

### Carga completa, carga incremental e lote

- **Carga completa:** recebe ou reconstrói todo o conjunto previsto. No contrato desta Bronze, os arquivos reenviam a história completa ou a fotografia completa do cadastro.
- **Carga incremental:** recebe ou processa somente parte das mudanças, como novos registros ou atualizações. Exige uma estratégia para manter o que não veio naquela entrega; não foi a estratégia implementada nesta migração.
- **Lote ou batch:** conjunto de registros associado a uma entrega ou execução. O timestamp pode ajudar a identificá-lo, mas selecionar apenas o maior timestamp não é uma regra universal para qualquer fonte.

### Migração

É a passagem de uma estrutura ou organização anterior para outra. Aqui, a migração substituiu a tabela antiga de faturas e criou uma saída separada de pendências, adotando o schema validado. Essa mudança inicial e o processamento rotineiro de novas cargas são etapas com finalidades diferentes.

### Delta Lake e tabela Delta

Delta Lake é uma tecnologia de armazenamento de tabelas que usa arquivos de dados e um log de transações. O log registra versões e permite leituras consistentes e histórico de operações. Delta não corrige automaticamente o significado dos campos: as regras de negócio continuam sendo responsabilidade da implementação.

### Modos e comandos presentes no processo

| Recurso | Finalidade | Observação |
| :--- | :--- | :--- |
| `append` | Acrescentar registros ao destino. | Repetir a carga completa pode acumular cópias. Não é a estratégia Bronze de extração completa adotada neste projeto. |
| `overwrite` | Substituir o conteúdo segundo a operação e as opções utilizadas. | Precisa corresponder ao contrato de fonte completa; não confundir automaticamente com autorização para mudar schema. |
| `error` / intenção de `errorifexists` | Interromper a criação se o destino já existir. | O alias `errorifexists` não funcionou no Spark Connect utilizado; `error` foi a alternativa aceita naquela etapa. |
| `CREATE TABLE AS SELECT` | Criar uma tabela a partir do resultado de uma consulta. | Usado na criação das revisões. |
| `CREATE OR REPLACE TABLE ... AS SELECT` | Criar ou substituir a tabela pelo resultado consultado. | Usado na publicação definitiva aprovada, incluindo o novo schema. |
| `saveAsTable` | Gravar o DataFrame como uma tabela nomeada. | É uma operação de dados, não criação de notebook. |
| `option` | Configurar uma leitura ou gravação. | `versionAsOf` seleciona uma versão; outras opções tratam schema e formato. |
| `mergeSchema` | Permitir união/evolução de schemas em operações compatíveis. | Não deve ser confundido com junção de registros por chave. |
| `overwriteSchema` | Permitir substituição do schema em uma gravação compatível. | Uma mudança de contrato precisa ser explícita; a migração aprovada usou SQL para substituir a tabela. |
| `tableExists` | Verificar se um objeto existe com aquele nome. | Não compara conteúdo nem certifica que ele seja o resultado esperado. |

Encontrar uma tabela já existente pode exigir conferência ou decisão de substituição. Usar uma opção para ignorar sua existência não provaria que os dados estão corretos.

### Atomicidade e ACID

| Propriedade | Explicação acessível |
| :--- | :--- |
| Atomicidade | Uma transação é concluída como uma unidade. Para uma gravação Delta individual, o leitor não deve enxergar apenas uma parte dos arquivos daquela transação. |
| Consistência | As regras estruturais e restrições efetivamente configuradas devem permanecer válidas. Isso não certifica todas as regras de negócio por conta própria. |
| Isolamento | Operações concorrentes seguem regras para lidar com interferência entre transações. |
| Durabilidade | Depois de uma transação confirmada, o resultado é registrado de forma persistente. |

**A atomicidade é por tabela nesta implementação.** A gravação da pendência e a da principal são operações diferentes. Se a primeira funcionar e a segunda falhar, não há uma única transação que reverta ambas automaticamente.

### Workflow, Job, task e dependência

Um **Workflow/Job** organiza a execução automatizada. Uma **task** é uma atividade, como executar um notebook. Uma **dependência** determina que uma task só avance depois de outra concluir com sucesso.

Para o consumo automatizado, a Gold deve depender do sucesso completo da etapa Silver. Esse é um requisito de organização do fluxo; a execução de um Workflow integrado não foi comprovada pelo notebook de faturas.

---

## 13. Versões Delta, regras e Git

### Histórico Delta e time travel

- `DESCRIBE HISTORY` apresenta operações e versões da tabela.
- `versionAsOf` solicita um estado de uma versão específica.
- **Time travel** é o acesso a esses estados anteriores enquanto os arquivos e logs necessários estiverem disponíveis.
- `DESCRIBE DETAIL` apresenta metadados da tabela, como formato e informações de armazenamento. Não é o mesmo que o histórico de operações.

Versão Delta 0 significa a primeira versão registrada daquela tabela. Versão 1 significa outra versão da mesma tabela, não o dia 1 nem o segundo mês da base.

Três fontes com versão 0 não estão necessariamente sincronizadas: cada tabela possui sua própria sequência. A possibilidade de consultar uma versão antiga depende da retenção dos arquivos e logs; histórico não deve ser apresentado como backup permanente por si só.

### Vínculo com a versão conferida

Uma aprovação de qualidade precisa corresponder à mesma tabela e à mesma versão que serão usadas na publicação. Conferir a versão 1 e publicar a 0, por exemplo, não comprova a publicação do conjunto aprovado. Na migração de faturas, a versão 0 continua fixa; a correção da issue #28 bloqueia o fluxo quando a conferência aponta para outra versão e reutiliza o snapshot conferido como referência. A proteção é repetida antes da escrita e não atualiza automaticamente as tabelas com novas cargas Bronze.

### Versão das regras

É o identificador registrado para a política de transformação. Na publicação auditada, `versao_regras` contém `FATURAS_CANDIDATA_V1`. O texto foi preservado no resultado; não significa que a tabela definitiva deixou de existir ou que seu nome seja o mesmo da versão das regras.

### Git e versionamento de código

| Termo | Significado | Distinção neste trabalho |
| :--- | :--- | :--- |
| Repositório | Conjunto organizado de arquivos e histórico de código. | Armazena notebooks e documentação. |
| Commit Git | Registro de uma alteração no histórico do código. | Não é a mesma coisa que uma gravação Delta. |
| Hash do commit | Identificador do commit. | `8381720b2bed81befcc95ba02ba9dc1b9cf75b8d` identifica a base de código utilizada. |
| Branch | Linha de trabalho no histórico do repositório. | Não cria uma cópia automática das tabelas Databricks. |
| Push | Envio de commits para um repositório remoto. | Criar arquivos locais não significa fazer push. |
| Pull request / PR | Proposta de integração de alterações para revisão. | No fluxo do projeto, uma branch de trabalho propõe suas alterações à `dev`. Abrir ou integrar um PR não executa o notebook no Databricks. |

Neste processo houve gravações de dados e versões Delta no Databricks. O versionamento dos arquivos em Git registra o código e a documentação; não cria outra versão das tabelas nem executa o notebook. São ações diferentes, embora ambas possam usar a palavra versão ou commit em seus contextos técnicos.

---

## 14. Dicionário dos campos da Silver

### Campos de negócio

| Campo | Significado | Como foi tratado |
| :--- | :--- | :--- |
| `id_fatura` | Identificador da fatura. | Preservado; padrão, preenchimento e unicidade verificados. |
| `id_uc` | Identificador da unidade consumidora. | Preservado; formato e presença nas referências avaliados. |
| `mes_referencia` | Competência da fatura. | Mantido como texto `AAAA-MM`, sem substituição pelo mês de outra data. |
| `data_emissao` | Emissão interpretada. | DATE conforme representação e convenção adotada. |
| `valor_energia` | Parcela monetária de energia informada. | DECIMAL(18,2), sem inventar quantidade de kWh. |
| `tributos` | Parcela monetária de tributos informada. | DECIMAL(18,2), sem assumir validação de alíquotas legais. |
| `bandeira_tarifaria` | Categoria de bandeira informada pela fonte. | Preservada e verificada no domínio observado; seu adicional não foi recalculado. |
| `valor_total` | Total monetário da fatura. | DECIMAL(18,2), conciliado com energia e tributos. |
| `data_vencimento` | Data informada de vencimento. | DATE ISO. |
| `data_pagamento` | Data real de pagamento, quando informada. | DATE; nulo ou sentinela resultam em ausência com motivo. |
| `status` | Situação informada na extração. | PAGA ou EM ABERTO; não foi transformado em uma posição atual calculada. |

### Indicadores e motivos

| Campo | O que indica | Como interpretar |
| :--- | :--- | :--- |
| `flag_emissao_original_ambigua` | O texto original com hífen admitia duas datas distintas. | Pode ser true mesmo com a data escolhida preenchida. |
| `flag_emissao_fora_competencia` | O mês da emissão escolhida difere da competência. | Não foi usado como motivo automático de exclusão. |
| `flag_pagamento_atrasado` | Pagamento real posterior ao vencimento. | Em fatura sem pagamento, false não quer dizer pagamento em dia; não há data real para comparar. |
| `flag_uc_sem_cadastro` | A UC não foi encontrada na referência cadastral utilizada. | Determina a separação entre principal e pendências neste contrato. |
| `flag_sem_leitura_uc_mes` | O par UC/competência não foi encontrado na referência de leituras. | É uma verificação separada da presença cadastral e da qualidade do consumo. |
| `flag_multiplas_faturas_uc_mes` | Há mais de uma fatura no mesmo par UC/competência. | Não comprova cópia nem define qual cobrança seria válida. |
| `motivo_ausencia_pagamento` | Classifica o motivo de uma data de pagamento ausente. | `CAMPO_NULO` ou `SENTINELA_9999_12_31`; fica nulo quando há pagamento real interpretado. |
| `situacao_referencia_cadastral` | Classificação textual da presença cadastral. | `CADASTRO_ENCONTRADO` ou `PENDENTE_CADASTRO`. |

### Metadados e preservação

| Campo | Significado |
| :--- | :--- |
| `dados_originais` | STRUCT com as onze colunas brutas, antes da tipagem desta Silver. |
| `source_file` | Arquivo registrado como origem da linha, como `faturas.csv`. |
| `ingestion_datetime` | Timestamp de ingestão preservado da Bronze. |
| `metodo_interpretacao_emissao` | Identifica ISO ou a convenção aplicada: `ISO_ANO_MES_DIA`, `CONVENCAO_DMY_BARRAS`, `CONVENCAO_DMY_PONTOS` ou `CONVENCAO_MDY_HIFEN`. |
| `versoes_bronze` | STRUCT com as versões de faturas, cadastro e leituras utilizadas. |
| `versao_regras` | Identificador do conjunto de regras aplicado. |

Os prefixos `_diag_` usados nos DataFrames indicam colunas auxiliares de diagnóstico. Eles não representam, por si só, tabelas persistidas. A candidata seleciona explicitamente os campos que compõem o schema final.

---

## 15. Resultado publicado e limites de interpretação

| Destino no catálogo `v-energy` | Versão registrada | Faturas | Valor total |
| :--- | ---: | ---: | ---: |
| `silver.tb_faturas` | 1 | 2.152.336 | R$ 666.482.773,76 |
| `silver.tb_faturas_pendentes_cadastro` | 0 | 32.285 | R$ 10.192.373,82 |

Os dois destinos são tabelas gravadas pelo mesmo notebook. Não são dois notebooks diferentes. Somados, preservam 2.184.621 faturas e R$ 676.675.147,58.

O termo **definitivo** identifica o destino aprovado para uso, não uma tabela que nunca mais poderá receber outra versão.

### Revisão e destino definitivo

As tabelas com `_revisao_v1` foram usadas para conferir a persistência antes da mudança definitiva. São objetos diferentes dos destinos finais. O trecho histórico de publicação lê a versão 0 dessas revisões, portanto não deve ser apresentado como rotina que sempre publica a Bronze mais recente.

### Cuidados ao apresentar os resultados

1. **Preservar não é homologar.** Manter todos os registros evita perda silenciosa; não garante que todas as cobranças sejam legítimas.
2. **Sinalizar não é corrigir a origem.** A flag documenta uma condição e pode apoiar um tratamento, mas não recupera automaticamente informação faltante.
3. **Validar um contrato não confirma toda a realidade.** A implementação pode aplicar corretamente uma convenção cuja origem ainda não foi formalmente confirmada.
4. **Mesmo total não garante mesmos registros.** Por isso foram usadas comparações completas e com multiplicidade, além das somas.
5. **Presença de chave não valida atributos.** Encontrar cadastro ou leitura não conclui a qualidade dessas entidades.
6. **Pendências não são receita zero.** A parcela segregada deve ser informada para explicar a cobertura das análises.
7. **Validação local, execução Databricks e Workflow são evidências diferentes.** O sucesso de uma não deve ser apresentado como prova automática das demais.
8. **O relatório descreve esta extração.** Uma futura carga pode trazer novos formatos, categorias ou problemas que precisem de diagnóstico e decisão.

## Documentos relacionados

- [Auditoria de faturas](../auditoria_dados/auditoria_faturas.md): resultados detalhados, decisões, reconciliações e limites.
- [Textos das seções do notebook](textos_secoes_notebook_faturas.md): explicações para acompanhar cada etapa na apresentação.

Este glossário documenta os termos do trabalho realizado. Sua leitura e edição não executam células nem alteram os dados ou resultados do notebook. O versionamento do documento em Git é separado da publicação das tabelas Delta.
