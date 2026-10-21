# Análise comparativa — Landing → Bronze de faturas e PR #14

Data do documento: 21/10/2026.

## 1. Escopo e fontes

Esta análise compara a implementação específica de faturas com a proposta de
ingestão unificada da camada Bronze do projeto V-Energy.

| Fonte | Versão analisada |
|---|---|
| Implementação local | ZIP `faturas-revisao.zip`, enviado pelo usuário como cópia dos arquivos de `C:\Users\gabri\Case-RocketLab-2026.2\data-engineering\` |
| Arquivos locais | `Landing_to_Bronze-faturas.ipynb`, `README.md` e `auditoria_faturas.md` |
| Proposta remota | [PR #14 — unifica a ingestão da landing na bronze](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/pull/14) |
| Commit remoto analisado | `7e8ef28347267aaccdf33582e450d6971c953022` |
| Notebook remoto | [Landing_to_Bronze.ipynb no commit analisado](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/blob/7e8ef28347267aaccdf33582e450d6971c953022/data-engineering/Landing_to_Bronze.ipynb) |
| Decisões remotas | [Decisões da carga unificada no commit analisado](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/blob/7e8ef28347267aaccdf33582e450d6971c953022/docs/auditoria_dados/decisoes_landing_to_bronze.md) |

O PR estava aberto e não integrado na consulta usada para esta análise.
As conclusões se referem a esse commit, não a eventuais alterações posteriores.

Não houve acesso direto ao disco Windows, alteração dos arquivos de implementação,
execução no Databricks, commit, push ou criação de PR durante esta revisão.
O ZIP representa os arquivos locais somente no momento em que foi preparado.

## 2. Resultado da comparação

As duas implementações seguem a mesma estratégia de Bronze: preservar os valores
de negócio e substituir a extração completa. A implementação de faturas faz
conferências mais detalhadas de estrutura, origem e dados persistidos. O PR #14
organiza todas as fontes em uma carga e acrescenta uma referência mínima de volume.

Essas proteções se complementam. Entretanto, os contratos de destino, metadados e
campos vazios diferem. Os notebooks não devem ser considerados intercambiáveis
para escrever na mesma tabela sem conciliar essas decisões.

## 3. Semelhanças

| Aspecto | Comportamento comum |
|---|---|
| Responsabilidade da Bronze | Preservar a origem; saneamento pertence à Silver |
| Faturas | Manter as 11 colunas de negócio como texto |
| Datas e valores | Não converter formatos nem aplicar correções de negócio |
| Cabeçalhos internos | Não aplicar filtro para remover as repetições internas |
| Duplicatas | Não deduplicar registros |
| Leitura CSV | Cabeçalho, UTF-8, suporte a multilinha e escape por aspas duplicadas |
| Espaços | Preservar espaços no começo e no fim dos campos |
| Escrita | Delta com `overwrite`, substituindo a extração anterior |
| Metadados | Acrescentar instante de ingestão e identificação da origem |

Para faturas, ambas usam o cabeçalho com as colunas `id_fatura`, `id_uc`,
`mes_referencia`, `data_emissao`, `valor_energia`, `tributos`,
`bandeira_tarifaria`, `valor_total`, `data_vencimento`, `data_pagamento` e `status`.

A reexecução com a mesma extração pretende manter o conjunto de dados de negócio,
sem acumular linhas. Timestamp e versão Delta podem mudar. Essa propriedade deve
ser verificada na versão final do pipeline, e não presumida somente pelo modo de escrita.

## 4. Organização e contrato operacional

| Aspecto | Implementação específica de faturas | PR #14 |
|---|---|---|
| Notebook | `Landing_to_Bronze-faturas.ipynb` | `Landing_to_Bronze.ipynb` |
| Escopo | Somente faturas | Todas as fontes, consolidadas em oito tabelas |
| Catálogo | `venergy` | `v-energy` |
| Landing | `/Volumes/venergy/landing/landing_volume` | `/Volumes/v-energy/bronze/landing` |
| Destino de faturas | `venergy.bronze.tb_faturas` | `` `v-energy`.bronze.tb_faturas `` |
| Proveniência | `source_file_path`, caminho completo | `source_file`, nome do arquivo |
| Campo CSV vazio | String vazia após preenchimento com `na.fill` | Nulo, conforme o leitor e o contrato documentado |
| Separador de faturas | `;` explícito | Detectado pelo cabeçalho |
| Dependências | Spark e biblioteca padrão Python | Acrescenta pandas/openpyxl para Excel |
| Preparação do ambiente | Cria catálogo, schemas Landing/Bronze e Volume | Cria catálogo, schemas Bronze/Silver/Gold e Volume na Bronze |

O PR reúne leituras anuais em `tb_leituras` e abas de inspeções em `tb_inspecoes`.
Essa abrangência não existe no notebook dedicado a faturas. Ela atende à organização
da camada inteira, mas não substitui as validações específicas de cada fonte.

## 5. Validações antes da escrita

### 5.1. Estrutura de cada registro

O notebook de faturas percorre o CSV com `csv.reader` antes da leitura Spark.
Ele verifica:

- Existência de um arquivo e de registros após o cabeçalho.
- Cabeçalho exato, incluindo ordem das colunas.
- Exatamente 11 campos em cada registro.
- UTF-8 válido e parsing de aspas com modo estrito.
- Ausência de caracteres NUL.
- Quantidade de registros e de cabeçalhos internos.

Depois, compara as contagens de registros e de cabeçalhos internos com as obtidas
pelo Spark. A agregação também referencia as colunas de negócio para identificar
as repetições completas do cabeçalho.

O PR usa schema explícito, `enforceSchema=false` e `FAILFAST`. Essas opções são
proteções relevantes, mas não equivalem à conferência independente da quantidade
de campos por registro. O leitor CSV do Spark pode tratar campos faltantes ou
excedentes de forma diferente do bloqueio prometido na documentação. A rejeição
desses casos precisa ser comprovada com fixtures no runtime utilizado.

Recomendação: preservar a pré-validação por registro ao integrar faturas na carga
unificada. Não presumir que `FAILFAST` sozinho cobre todo erro de largura do CSV.

### 5.2. Volume e extração incompleta

| Controle | Implementação de faturas | PR #14 |
|---|---|---|
| Extração sem registros | Rejeita | Rejeita pela referência mínima de faturas |
| Extração pequena, mas válida | Aceita se Python e Spark concordarem | Rejeita abaixo de 2.184.623 registros |
| Extração maior que a referência | Não compara com uma referência fixa | Avisa e continua |

A revisão confirmou que uma fixture com apenas um registro é aceita pela
pré-validação local. Isso não significa que ela esteja estruturalmente errada:
significa que estrutura válida e completude da entrega são controles diferentes.

O limite do PR protege contra redução em relação à referência desta entrega.
Também não comprova que todas as competências ou faturas esperadas chegaram.
Uma mudança legítima na regra de extração exige revisar essa referência.

## 6. Rastreabilidade e validações após a escrita

| Controle | Implementação de faturas | PR #14 |
|---|---|---|
| SHA-256 da origem | Calcula e inclui no relatório | Não calcula |
| Estabilidade da origem | Confere tamanho e data de modificação em etapas da carga | Não há conferência equivalente |
| Contagem persistida de faturas | Compara com o perfil independente do CSV | Compara com a contagem do DataFrame |
| Cabeçalhos internos persistidos | Confere a quantidade | Não há controle específico |
| Timestamp e proveniência de todas as linhas | Confere os valores esperados | Não há controle equivalente |
| Resultado final | JSON com hash, contagens, instante e status | Mensagens de execução e verificações gerais |

As verificações locais de tamanho e modificação não substituem a exigência
operacional de manter a origem estável durante a carga. A comparação de contagens
também não é uma comparação de conteúdo campo a campo.

A pré-validação Python e o cálculo do hash acrescentam leituras sequenciais no
driver. Esse custo deve ser considerado para arquivos substancialmente maiores.
O PR depende principalmente de ações Spark e também executa diversas leituras e
contagens. Não foi realizado benchmark de desempenho entre as duas soluções.

## 7. Timestamp, schema e recuperação

### 7.1. Timestamp de ingestão

O notebook de faturas captura `datetime.now(timezone.utc)` uma vez, usa o instante
como literal e configura a sessão Spark para UTC. Após a escrita, verifica que
todas as linhas possuem o timestamp esperado.

O PR usa `current_timestamp()` na função de gravação. No Spark, o valor é
consistente dentro da mesma consulta; ele não implica um timestamp diferente por
linha. Como há gravações separadas por tabela, o código não estabelece um único
instante global capturado para toda a execução. O notebook remoto também não fixa
explicitamente o fuso da sessão nem valida o timestamp persistido como o local.

### 7.2. Compatibilidade de schema

O notebook de faturas exige que o destino existente seja Delta e tenha os nomes,
tipos e ordem de colunas esperados. O PR utiliza `overwriteSchema=true` na escrita.

Se os dois forem direcionados à mesma tabela:

- O notebook local rejeitará um schema que tenha `source_file` no lugar de
  `source_file_path`.
- A escrita do PR poderá substituir o schema pelo contrato unificado.
- A representação dos pagamentos vazios mudará entre string vazia e nulo.

Hoje os catálogos diferentes separam os destinos. Apenas trocar `venergy` por
`v-energy` não resolve a integração. Além disso, os comandos `CREATE` locais
precisam delimitar o catálogo com crases ao usar o nome com hífen.

### 7.3. Atomicidade e falhas

A carga local escreve uma tabela. O PR escreve as tabelas sequencialmente.
Se uma fonte posterior falhar, tabelas anteriores podem já ter sido atualizadas.
Não há transação única cobrindo as oito tabelas.

Cada escrita Delta tem sua própria transação. Uma falha de validação após o commit
de uma escrita não desfaz automaticamente a versão publicada, inclusive no
notebook local. O procedimento de recuperação precisa distinguir falha anterior
à escrita de falha detectada posteriormente.

## 8. Documentação e evidências

### 8.1. Auditoria de faturas

O arquivo `auditoria_faturas.md` acrescenta análise de datas ambíguas, formatos
monetários, relacionamento com UCs, granularidade, somas e limites das conclusões.
Ele complementa a documentação operacional do PR.

As propostas de saneamento permanecem atribuídas à Silver. As estatísticas não
foram reproduzidas nesta revisão, pois o ZIP não contém os dados nem o código
completo que gerou a auditoria. Não devem ser apresentadas como resultados
recalculados durante esta comparação.

Há espaços finais nas linhas 3, 4 e 5 da auditoria recebida. O check de whitespace
do fluxo Git pode rejeitar essas linhas quando forem incluídas no diff.

### 8.2. README local

O README precisa ser conciliado com a implementação efetiva. Ele ainda menciona:

- `Landing_to_Bronze_Faturas.ipynb`, enquanto o arquivo enviado tem outro nome.
- Widgets que não existem na configuração atual do notebook.
- Catálogo `workspace`, enquanto o código usa `venergy`.
- `verificar_faturas.py` e evidência JSON ausentes no ZIP de revisão.
- Ausência de execução remota, enquanto o notebook contém outputs de execução.

### 8.3. Evidências observadas e verificações realizadas

| Evidência ou verificação | Escopo e limite |
|---|---|
| Output do notebook local | Registra `validation: passed`, 2.184.623 registros, dois cabeçalhos internos e destino `venergy.bronze.tb_faturas`; não foi reproduzido nesta revisão |
| Relato do PR #14 | Informa execução das oito tabelas e testes no Databricks; não foi reproduzido nesta revisão |
| Sintaxe local | As nove células Python foram compiladas durante a revisão anterior do mesmo ZIP |
| Fixtures locais | Sete cenários sintéticos exercitaram a pré-validação: válido com vazio, duplicata/cabeçalho interno, somente cabeçalho, campo faltante, campo excedente, cabeçalho errado e NUL |
| Spark/Delta | Não executados nesta comparação |
| Auditoria estatística | Não recalculada nesta comparação |

O check `Fluxo Git` valida o processo de colaboração e as verificações configuradas
no repositório. Seu sucesso não comprova, por si só, execução autenticada no
Databricks ou correção dos dados carregados.

## 9. Recomendação de integração

Usar a organização unificada do PR #14 e incorporar as proteções específicas mais
fortes da carga de faturas, preservando também a auditoria como documentação.
Evitar dois processos operacionais escrevendo na mesma tabela com contratos diferentes.

A sequência recomendada é:

1. Definir catálogo, Volume, representação de vazios e colunas de proveniência.
   Se o destino comum for `v-energy`, ajustar também a delimitação nos comandos SQL.
2. Conciliar a pré-validação por registro com o limite mínimo de volume acordado.
3. Incorporar hash, conferência de estabilidade da origem e validação dos metadados
   persistidos, considerando o custo de leitura no driver.
4. Atualizar o README para descrever somente parâmetros, arquivos e comportamentos
   existentes. Colocar a auditoria em `docs/auditoria_dados/auditoria_faturas.md`.
5. Preservar o relatório de execução como evidência identificada e limpar outputs
   do notebook de código antes da publicação, conforme o padrão adotado no PR.
6. Testar a versão conciliada no Databricks e revisar o diff antes de qualquer commit.

Critérios de aceite sugeridos para a versão conciliada:

- Carga válida conserva registros, cabeçalhos internos e valores de negócio.
- Campos faltantes ou excedentes interrompem a carga antes da escrita.
- Extração abaixo da referência mínima acordada não substitui faturas.
- Crescimento da extração segue a política documentada de aviso e aceitação.
- Reexecução não acumula registros e atualiza os metadados conforme o contrato.
- Schema, representação de vazios, origem e timestamp correspondem ao esperado.
- Falha posterior à escrita é identificada sem afirmar rollback automático.
- Evidência distingue testes sintéticos, auditoria da fonte e execução Databricks.

## 10. Continuidade pelo fluxo Git

A preparação local informada pelo usuário está na branch
`feat/8-ingestao-faturas-bronze`, criada a partir de `origin/dev`. Na leitura local
fornecida, os arquivos ainda estavam não rastreados e sem commits próprios.
Este documento não verifica novamente esse estado.

Quando houver autorização para publicar, o fluxo permanece: revisar e selecionar
somente os arquivos da fatia, fazer commit com Conventional Commits, enviar a branch
de trabalho e abrir ou atualizar PR para `dev`. A integração exige revisão e checks
aprovados. A promoção `dev` → `main` ocorre na conclusão do módulo.

A produção deste documento não realiza nenhuma dessas ações nem altera o PR #14.
