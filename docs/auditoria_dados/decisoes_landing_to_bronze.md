# Decisões — Landing to Bronze (V-Energy)

Notebook: `data-engineering/Landing_to_Bronze.ipynb`.

Catálogo `v-energy`, schema `bronze`, volume `/Volumes/v-energy/bronze/landing`. Os arquivos ficam soltos no volume, sem subpasta.

A Bronze copia o que chegou. Não corrige conteúdo. Limpeza, padronização e a decisão sobre valor no lugar errado ficam na Silver.

## 1. Quais arquivos entram

Sete nomes são fixos: `unidades_consumidoras.csv`, `medidores.csv`, `geracao_distribuida.csv`, `faturas.csv`, `ocorrencias_rede.csv`, `atendimentos.json` e `inspecoes.xlsx`. Se faltar um, o notebook para. Outro CSV, que não seja leitura, é ignorado.

As leituras entram por `leituras_*.csv`. Nesta entrega, `leituras_2022.csv` a `leituras_2026.csv` têm de existir, com 271.744, 544.546, 545.652, 546.908 e 273.618 linhas. Um `leituras_2027.csv` entra sem mudar o código.

Motivo: o case pede os arquivos nomeados. Ler qualquer CSV do volume gravaria um arquivo de teste e seguiria mesmo sem `faturas.csv`, por exemplo. As leituras já chegam um arquivo por ano, no mesmo formato. O ano seguinte é outro arquivo desse padrão, não uma fonte nova.

## 2. Cinco arquivos de leitura viram uma tabela

`leituras_2022.csv` a `leituras_2026.csv` vão todos para `tb_leituras`. A coluna `source_file` guarda o nome do arquivo.

Motivo: os cinco arquivos são a mesma entidade e o mesmo grão, uma leitura por linha, com o mesmo cabeçalho. Cinco tabelas (`tb_leituras_2022` … `tb_leituras_2026`) só repartiriam as mesmas linhas pelo ano do arquivo. O ano seguinte criaria outra tabela. `source_file` separa `leituras_2024.csv` de `leituras_2025.csv` sem virar regra de negócio. Juntar não limpa data, não tira duplicata e não converte número.

Depois de gravar `tb_leituras`, o notebook apaga `tb_leituras_2022` … `tb_leituras_2026` se elas ainda existirem. São as tabelas da versão anterior, uma por ano. Sem isso, ficariam no schema ao lado da tabela unificada.

## 3. Três abas de inspeção viram uma tabela

`tb_inspecoes` junta as abas cujo cabeçalho é, nesta ordem, `id_inspecao`, `id_uc`, `data`, `inspetor`, `resultado`, `tipo_irregularidade`, `kwh_recuperado`. A coluna `sheet` guarda o nome da planilha (`ago-set`, `out-nov`, `dez`). Aba de capa ou instrução, com outro cabeçalho, fica de fora. Uma aba nova com o mesmo cabeçalho entra e só gera aviso.

Nesta entrega a referência é `ago-set` 511, `out-nov` 495 e `dez` 383.

Motivo: as três abas são a mesma entidade e o mesmo grão, uma inspeção por linha, com o mesmo cabeçalho. Três tabelas deixariam essa concatenação para a Silver, sem ganho de regra de negócio. `sheet` é metadado de origem, como o `source_file` das leituras. O mês novo, neste arquivo, tende a chegar como aba nova, não como outro CSV. Não se padroniza `resultado`, não se converte `kwh_recuperado` e o nulo de `tipo_irregularidade` permanece. Juntar com a unidade consumidora fica na Silver.

Cadastro, faturas e ocorrências continuam com um arquivo e uma tabela, porque cada um é uma entidade.

## 4. Como o CSV é lido

Um CSV tem um separador só, o mesmo para o arquivo inteiro. `detect_delimiter()` lê a primeira linha, que é o cabeçalho, e conta `;` e `,`. O cabeçalho só tem nome de coluna, então um dos dois aparece e o outro fica em zero. Em `faturas.csv` há dez `;` e nenhuma `,`, e o separador fica `;`. Nos outros CSVs o cabeçalho tem `,` e nenhum `;`, e o separador fica `,`. A partir daí o Spark corta cada linha só nesse caractere.

A vírgula dentro de um valor não entra nessa escolha, porque a função não lê as linhas de dados. Em `faturas.csv` o campo vem como `R$ 225,53`: o separador é `;`, e essa vírgula continua dentro de `valor_total`. Em `geracao_distribuida.csv` a potência vem como `"5,03"`: o separador é `,`, e as aspas mantêm esse trecho como um campo só.

Com o separador errado, o Spark lia o cabeçalho inteiro como uma coluna só e o Delta rejeitava o nome.

`multiLine` e `escape` ficam ligados em todo CSV. As quatro combinações (sem proteção, só `multiLine`, só `escape`, as duas) deram a mesma contagem, e essa contagem fecha com a Bronze. Não houve perda nem inflação de linhas. Aspas no meio do campo, como a potência `"5,03"`, não podem virar coluna extra.

`sanitize_column_name()` troca ` ,;{}()\n\t=` por `_`. É rede de segurança depois do separador certo. Nesta carga os nomes já eram válidos.

Espaço no começo e no fim do campo é preservado (`ignoreLeadingWhiteSpace` e `ignoreTrailingWhiteSpace` em `false`). O padrão do Spark para CSV já é esse. A opção fica escrita para a decisão aparecer no código.

## 5. `overwrite`, porque o arquivo que chega é a história inteira

A primeira carga usava `append` e, ao rodar de novo, dobrou as tabelas. Cada execução agora substitui a tabela.

Não há uma TI real. Ficou combinado o jeito 1 para `faturas.csv`, `ocorrencias_rede.csv` e `atendimentos.json`: todo mês eles reenviam o mesmo arquivo com a história inteira, não só o mês novo. Uma fatura que era `EM ABERTO` e no arquivo novo está `PAGA` entra, porque a linha atualizada veio na exportação. `overwrite` de um arquivo que trouxesse só julho apagaria abril, maio e junho. Essa combinação não é essa.

`unidades_consumidoras.csv`, `medidores.csv` e `geracao_distribuida.csv` chegam como a foto inteira do cadastro, com os registros antigos e os novos juntos. `overwrite` troca a tabela por essa foto. Se um dia o arquivo trouxesse só as unidades novas, essa decisão apagaria as 45.200 que já estavam.

O notebook de atendimentos da equipe gravava com `append` e recusava o mesmo caminho se ele já estivesse na tabela. Isso não entrou: com o jeito 1, recusar o caminho impediria a correção de uma linha antiga.

## 6. Contagem: menos para, mais avisa

O número no código é o tamanho desta entrega. Antes do `overwrite`, ele é comparado com o que foi lido.

Menos linhas interrompe a carga. A tabela que já está na Bronze permanece. Um `faturas.csv` cortado não substitui as 2.184.623 linhas.

Mais linhas imprime um aviso e a gravação segue. No jeito 1 o arquivo volta com a história inteira e o mês novo, então crescer é o caminho esperado.

Vale para cada CSV, para o JSON, para cada `leituras_*.csv` com contagem conhecida e para as abas `ago-set`, `out-nov` e `dez`. Um `leituras_*.csv` novo, sem número no código, entra com aviso.

## 7. Travas de estrutura

Estas travas seguram arquivo cuja estrutura não dá para ler sem deslocar coluna. Quando a carga para, o `overwrite` não roda, a tabela atual permanece e o arquivo continua no volume. O conserto é a origem reenviar o arquivo.

Não há tabela de quarentena. Neste dataset ela nasceria vazia: não há CSV com campo a mais ou a menos, nem chamado JSON sem fechar. Uma tabela vazia no catálogo, sem este texto ao lado, parece carga que falhou.

### CSV

Vale para `unidades_consumidoras.csv`, `medidores.csv`, `ocorrencias_rede.csv`, `faturas.csv`, `geracao_distribuida.csv` e `leituras_*.csv`.

O cabeçalho tem de ser a lista escrita no notebook, nome por nome, na mesma ordem. Fora de ordem, coluna faltando ou com outro nome, a leitura quebra. O aviso é o erro do Spark, não a mensagem de contagem.

Campo vazio não é linha torta. Com o cabeçalho `id_uc,nome,cidade`, a linha `UC1,Maria,` tem três campos e a cidade vazia vira nulo. A linha `UC1,,Recife` tem o nome vazio. A carga segue. Isso é o equivalente da célula vazia do Excel.

Campo a menos é a vírgula que não veio: `UC1,Maria` tem dois pedaços. O leitor não sabe qual coluna faltou. Campo a mais é um pedaço sobrando: `UC1,Maria,Recife,extra`. Os dois interrompem o arquivo inteiro (`FAILFAST`), antes do `overwrite`.

Uma linha com a quantidade certa de campos e o valor no lugar errado entra. Isso fica para a Silver.

### Excel

A aba só entra se o cabeçalho for exatamente `id_inspecao`, `id_uc`, `data`, `inspetor`, `resultado`, `tipo_irregularidade`, `kwh_recuperado`, nessa ordem. As três abas deste arquivo já têm essa lista. Aba de capa fica de fora. Se `ago-set`, `out-nov` ou `dez` vier com outro cabeçalho, a carga de `inspecoes.xlsx` para.

Célula vazia vira nulo e a linha entra. Não existe a trava de campo a mais ou a menos do CSV. Uma coluna a mais muda o cabeçalho e cai na trava do cabeçalho.

### JSON

Um chamado sem fechar faz o Spark criar `_corrupt_record` e seguir. Se essa coluna aparece, a carga para antes do `overwrite`. A contagem poderia fechar e a tabela seria gravada com uma linha vazia e o texto ilegível escondido nessa coluna.

As chaves `protocolo`, `id_uc`, `canal`, `assunto`, `subassunto`, `data_abertura`, `data_fechamento` e `historico` têm de existir e vir preenchidas. `historico` não pode vir vazio. Cada item da lista tem de ter `sequencia`, `data`, `acao` e `canal`. `nota_satisfacao` tem de existir e pode ser nula: a chave está presente e o valor é nulo em 9.566 dos 318.871 chamados. O primeiro caso é o protocolo `AT000000011`, na linha 280 do arquivo. Nenhuma outra chave falta e não há chave extra. A ordem dos nomes dentro do bloco não importa. Chave ou subchave obrigatória faltando interrompe o arquivo inteiro. Um campo novo não rejeita o arquivo, para a Bronze não descartar o que chegou.

## 8. `historico` continua aninhado

Uma linha por chamado. `historico` continua uma lista dentro da linha. Neste arquivo cada chamado tem 1, 2 ou 3 tratativas (`sequencia`, `data`, `acao`, `canal`). Não há limite de tamanho no código.

Motivo: achatar repetiria o protocolo em várias linhas. Isso é transformação e fica para a Silver, se a tela precisar da timeline.

O leitor já aceita uma tratativa a mais com os mesmos campos. Quebra se o mesmo campo mudar de tipo (número numa linha, texto na outra).

## 9. Colunas, carimbo e arquivo de origem

CSV e Excel gravam colunas de negócio como `string`, mais `ingestion_datetime`. O JSON infere tipo (`nota_satisfacao` numérica, `historico` como lista) para não destruir a lista.

Toda tabela ganha `source_file`, com o nome do arquivo de onde a linha saiu. Em `tb_leituras` isso separa o ano. Nas outras tabelas o valor é sempre o mesmo arquivo, e a coluna fica como rastreio, junto com `ingestion_datetime`.

No Excel, a coluna que se chamava `aba` passou a se chamar `sheet`, no mesmo padrão de `source_file` e `ingestion_datetime`. A contagem por planilha e o Teste 3 usam `sheet`. O texto em português continua falando "aba" quando se refere à planilha.

## 10. O que a Bronze não limpa

Ficam como chegaram: vírgula decimal, potência mil vezes grande, data em mais de um formato, cabeçalho repetido no meio do arquivo, sentinela (`9999-12-31`, `-1`, `-`, `R$`). Parte dos medidores `ATIVO` traz `9999-12-31` em `data_retirada` em vez de nulo.

Nulos medidos (campo vazio; sentinela não entra na conta): `tb_medidores.data_retirada` 61,4%, `tb_medidores.data_ultima_manutencao` 100%, `tb_faturas.data_pagamento` 5,2%, `tb_leituras.leitura_anterior` 0,4%, `tb_ocorrencias_rede.causa` 0,8%, `tb_unidades_consumidoras.cep` 0,3%, `tb_inspecoes.tipo_irregularidade` 31,7% (vazio quando não houve irregularidade).

## 11. O que entrou de cada notebook da equipe

A `main` e a `dev` não tinham notebook de ingestão. O código da equipe estava nas branches `feat/1` a `feat/7`. Não há branch de faturas nem de geração distribuída. A versão unificada ficou em `Landing_to_Bronze.ipynb`.

Os caminhos da equipe não coincidem entre si (`venergy`, `workspace.default`, `workspace.venergy_bronze`, subpasta `dados/`). Ficou o catálogo `v-energy` e o volume em que a carga já tinha rodado.

Entrou das leituras: `leituras_*.csv` numa tabela só, com `source_file`.

Entrou de medidores, ocorrências e leituras: contrato de cabeçalho (`enforceSchema = false`), `FAILFAST`, espaço preservado e contagem antes do `overwrite`.

Entrou de atendimentos: a parada quando `_corrupt_record` aparece. O `append` desse notebook não entrou.

Não entrou o Excel da equipe: ele lia qualquer aba e usava `append`, então uma segunda execução duplicava `inspecoes`. Ficou o filtro pelo cabeçalho de inspeção.

Os relatórios de auditoria da equipe estão nesta mesma pasta. As consultas de evidência continuam nesses arquivos. Não foram coladas no notebook de carga.

## 12. Testes que fecharam na carga anterior

- Teste 1: nos 10 CSVs, as quatro opções de leitura deram a mesma contagem, e a contagem do texto puro fecha com a Bronze.
- Teste 2: schema e nulos. O output gravado no notebook ainda lista 12 tabelas, porque foi a execução com uma tabela de leitura por ano. A versão atual grava 8: as sete de nome fixo e `tb_leituras`.
- `historico` conferido como array.
- Contagem por `sheet`: 511, 495 e 383.

A célula de ingestão unificada ainda precisa ser executada de novo no Databricks.

## O que continua escrito no código

- Os sete nomes fixos e as contagens desta entrega.
- As contagens de `leituras_2022.csv` a `leituras_2026.csv`. Um ano novo não precisa de nome novo no código.
- Os três nomes de aba e as três contagens de referência.
- O contrato de colunas de cada CSV e as chaves obrigatórias do JSON.
- `overwrite` em todas as tabelas, pela combinação do jeito 1 e do cadastro completo.
