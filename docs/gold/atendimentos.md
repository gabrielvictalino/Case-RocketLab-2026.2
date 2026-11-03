# Gold de atendimentos

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-atendimentos.ipynb` |
| **Entradas** | `` `v-energy`.silver.tb_atendimentos `` (PR #16) e `` `v-energy`.silver.tb_unidades_consumidoras `` (PR #24) |
| **Saídas** | `` `v-energy`.gold.atendimentos `` e `` `v-energy`.gold.atendimentos_historico `` |
| **Contrato** | `contracts/tabelas/atendimentos.yaml` e `atendimentos_historico.yaml` |
| **Usada por** | Bloco de chamados da Visão 360 (`backend/app/modules/ucs`), views `ai_read.atendimentos` e `ai_read.atendimentos_historico` (#103) e catálogo do agente (#110) |

## 1. A pergunta

A Gerente de Atendimento (Camila Barreto) pede, na seção 4.2 do case: _"Tem que aparecer tudo numa tela só: quem é o cliente, o consumo dos últimos meses (...) e os chamados que ele já abriu."_ No bloco de chamados da Visão 360, o atendente vê os protocolos da UC com o assunto, a situação, a nota de satisfação e a linha do tempo das tratativas (`docs/overview_dados/perguntas_negocio.md`, seção 3).

## 2. Regras e decisões

### 2.1. Um protocolo por linha em `atendimentos`

A Silver já tem um protocolo por linha e o histórico como um array de etapas. A Gold copia o protocolo, a UC e o assunto, e deriva:

* **`aberto_em`**, de `data_abertura`;
* **`status`**: `ENCERRADO` quando há `data_fechamento`, e `EM ABERTO` quando não há. Hoje todos os 318.871 protocolos têm fechamento, e o arquivo foi carregado depois do último fechamento (10/07/2026);
* **`nota`**, de `nota_satisfacao`, como `decimal(2,1)`.

### 2.2. Nota de 1 a 5, nula quando o titular não avaliou

O contrato pedia um inteiro de 0 a 10, mas a nota da base vai de 1,3 a 5,0, com uma casa decimal. A #117 e o PR #118 mudaram o contrato para `numeric(2,1)` de 1 a 5. A Gold publica a nota sem arredondar, e a nota nula continua nula: 9.566 protocolos sem avaliação não viram zero nem entram em média.

### 2.3. Uma etapa por linha em `atendimentos_historico`

Cada elemento do array `historico` da Silver vira uma linha: `sequencia` e `data` vêm da etapa, e `descricao` vem da `acao` (`ABERTURA`, `ANALISE`, `DESPACHO`, `RETORNO AO CLIENTE` e `ENCERRAMENTO`). Cada protocolo tem de 1 a 3 etapas. A ordem das ações na base não segue um fluxo: há `ENCERRAMENTO` na sequência 1 e `DESPACHO` depois. A Gold preserva a ordem da `sequencia`, que é a ordem cronológica, sem reordenar as ações.

O contrato descreve a `sequencia` como ordem cronológica. A Gold confere isso por conta própria, sem depender da Silver: a sequência vai de 1 a n sem buracos, a data da etapa não diminui com a sequência e nenhuma etapa é anterior à abertura do protocolo. Datas iguais em etapas seguidas são aceitas: há 406 na base.

### 2.4. Datas sem fuso

A Silver guarda as datas do arquivo de origem como `TIMESTAMP`. A Gold as grava como `TIMESTAMP_NTZ`, como a Gold de continuidade, para a hora não mudar na exportação.

A conversão de `TIMESTAMP` para `TIMESTAMP_NTZ` usa o fuso da sessão do Spark. Por isso, o notebook fixa a sessão em `UTC` logo no início, que é o fuso em que a Silver foi gravada (o padrão do Serverless). Sem isso, rodar a Gold numa sessão com outro fuso deslocaria todas as horas, e nenhuma regra acusaria. Uma regra confere que a data e a hora de `aberto_em` são as mesmas da Silver no fuso fixado.

### 2.5. Assunto, subassunto e canal

O contrato tem só o `assunto` (6 valores), que é o que o catálogo do agente (#110) descreve. O `subassunto` (por exemplo, `FATURA / VALOR ALTO`) e o `canal` ficam na Silver e não entram na Gold do contrato (seção 8).

## 3. Dicionário de dados

### `` `v-energy`.gold.atendimentos `` (protocolo)

| Coluna | Tipo | Nulo | Descrição |
| :--- | :--- | :---: | :--- |
| `protocolo` | `string` | não | Protocolo do atendimento; chave da tabela |
| `id_uc` | `string` | não | UC atendida (`UC` + 6 dígitos), presente no cadastro |
| `aberto_em` | `timestamp_ntz` | não | Data e hora de abertura |
| `assunto` | `string` | não | `FALTA DE ENERGIA`, `FATURA`, `DANO ELETRICO`, `LIGACAO NOVA`, `GERACAO DISTRIBUIDA` ou `RELIGACAO` |
| `status` | `string` | não | `ENCERRADO` ou `EM ABERTO` (seção 2.1) |
| `nota` | `decimal(2,1)` | sim | Satisfação de 1 a 5, uma casa decimal; nula quando o titular não avaliou |

### `` `v-energy`.gold.atendimentos_historico `` (protocolo × sequência)

| Coluna | Tipo | Nulo | Descrição |
| :--- | :--- | :---: | :--- |
| `protocolo` | `string` | não | Protocolo, presente em `atendimentos` |
| `sequencia` | `int` | não | Ordem da etapa no protocolo, a partir de 1 |
| `data` | `timestamp_ntz` | não | Data e hora da etapa |
| `descricao` | `string` | não | Ação registrada na etapa |

## 4. Validações

Todas bloqueiam a carga. A Gold anterior continua intacta quando uma falha acontece antes da escrita.

**Na Silver, antes de montar a Gold:**
* colunas esperadas;
* protocolo preenchido e sem repetição;
* `id_uc` no padrão e presente na Silver de cadastro;
* assunto preenchido;
* abertura preenchida e fechamento depois da abertura;
* nota de 1 a 5 com no máximo uma casa decimal;
* em cada etapa, sequência a partir de 1, sem repetição no protocolo, data e ação preenchidas.

**Nas duas tabelas, em memória e de novo depois de gravar:**
* contrato: colunas, tipos e ordem do YAML, nulos, padrão do `id_uc`, domínio do `status` e faixa da nota;
* chaves: `protocolo` único, e `protocolo` × `sequencia` único;
* reconciliação com a Silver: as mesmas linhas, os mesmos protocolos, a mesma nota (inclusive as nulas), a mesma data e hora de abertura, os mesmos protocolos em aberto e as mesmas etapas;
* ordem das etapas: sequência de 1 a n sem buracos em cada protocolo, data que não diminui com a sequência e nenhuma etapa antes da abertura do protocolo;
* integridade: todo `protocolo` do histórico existe em `atendimentos`, e todo `id_uc` existe no cadastro.

**Publicação:** antes da primeira escrita, o notebook guarda a versão de cada tabela de destino. Se a escrita, a conferência do conteúdo gravado ou a validação sobre as tabelas gravadas falhar, ele volta cada tabela afetada com `RESTORE TABLE ... TO VERSION AS OF`, ou a remove se era a primeira carga.

## 5. Números da base atual

318.871 atendimentos e 636.857 etapas no histórico, de 44.940 das 45.000 UCs do cadastro. Todos os protocolos estão encerrados, e 9.566 (3,0%) não têm nota. A nota média é 4,04.

**Por assunto:**

| Assunto | Atendimentos | Nota média | Sem nota |
| :--- | ---: | :---: | :---: |
| `FALTA DE ENERGIA` | 101.306 | 4,04 | 3,0% |
| `FATURA` | 43.624 | 4,05 | 3,0% |
| `DANO ELETRICO` | 43.582 | 4,04 | 3,0% |
| `LIGACAO NOVA` | 43.520 | 4,04 | 3,0% |
| `GERACAO DISTRIBUIDA` | 43.499 | 4,05 | 2,9% |
| `RELIGACAO` | 43.340 | 4,04 | 3,0% |

**Julho de 2025:** é o mês do evento atípico de falta de energia (`docs/gold/continuidade.md`, seção 6). Nesse mês, os atendimentos triplicam e a nota cai em todos os assuntos:

| Competências | Atendimentos por mês | Nota média |
| :--- | :---: | :---: |
| Meses de 2025, exceto julho | cerca de 6.400 | 4,10 |
| 2025-07 | 18.061 | 3,11 |

Por ano de abertura, a nota média é 4,10 em todos os anos, menos em 2025 (3,90). Sem julho, 2025 também fica em 4,10. Uma análise de satisfação precisa separar esse mês, como a continuidade separa o evento atípico.

## 6. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| Nota decimal de 1 a 5, como na base | Inteiro de 0 a 10 (contrato original) | Converter 4,3 em 8,6 e arredondar inventa precisão e muda a escala da origem (#117) |
| Nota nula continua nula | Nota nula como zero | Zero puxaria a média para baixo; nulo é "não avaliou" |
| `status` pela existência de `data_fechamento` | Comparar o fechamento com uma data de referência | O arquivo foi carregado depois de todos os fechamentos, e o contrato não traz a data de referência |
| `assunto` com os 6 valores da Silver | `assunto / subassunto` numa coluna só | O catálogo do agente e as consultas usam os 6 valores; juntar quebraria os filtros |
| `descricao` = ação da etapa | Ação + canal | O contrato pede a tratativa; o canal fica na Silver |

## 7. Como executar no Databricks

1. **Pré-requisito:** as duas Silvers publicadas.

   ```sql
   SELECT COUNT(*) FROM `v-energy`.silver.tb_atendimentos;           -- esperado: 318871
   SELECT COUNT(*) FROM `v-energy`.silver.tb_unidades_consumidoras;  -- esperado: 45000
   ```

2. Importe o notebook, conecte ao **Serverless** e use **Run all**. O padrão `modo=validar` não grava nada. Para gravar, troque o widget para `modo=publicar` antes de executar. O Workflow do Databricks (#97) vai passar `modo=publicar`.
3. **O que conferir:**
   * todas as linhas `[OK   ]` em `(fontes)` e `(antes de gravar)`;
   * `Reconciliação: 318,871 atendimentos | 636,857 etapas no histórico | 9,566 sem nota | 0 em aberto`;
   * com `modo=validar`, a linha final `Validação concluída. Nenhum schema ou tabela foi gravado.`;
   * com `modo=publicar`, as linhas `[OK   ]` em `(tabela gravada)` e as duas linhas `Publicada: ...`.

Se uma validação falhar, a mensagem lista cada regra violada com a quantidade de linhas. Uma falha nas `(fontes)` aponta para a Silver de origem. Uma falha em `(tabela gravada)` já restaurou a Gold anterior.

## 8. Pendências

* **`dim_uc`:** a integridade do `id_uc` é conferida contra a Silver de cadastro, de onde sai a `dim_uc`. Quando a `dim_uc` for publicada, a exportação consolidada (#96) confere o `id_uc` das 12 tabelas contra ela.
* **Subassunto:** a pergunta "a conta veio alta" usa `FATURA / VALOR ALTO`. Se o portal ou o agente precisarem do subassunto, ele entra no contrato como coluna nova (decisão de quem consome a tabela).
* **Exportação para o banco local:** fica no passo único de exportação do Job (#96).
