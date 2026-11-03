# Segurança da IA (F10)

Requisito do case: as funcionalidades de IA não podem alterar dados nem ser manipuladas
para agir fora do seu papel. O agente não depende de o modelo obedecer às instruções.
Cada camada abaixo barra sozinha os casos que cobre, e os testes provam isso com o LLM
simulado devolvendo o SQL malicioso.

## Caminho de uma pergunta

```
usuário → Nginx → POST /api/v1/assistente/perguntas → plano do LLM → guarda de SQL
        → executor (role ai_read, ROLLBACK) → redação do LLM → validação dos números
        → auditoria (role portal)
```

## Camadas

| # | Camada | Onde | O que bloqueia |
|---|---|---|---|
| 1 | Fronteira da API | `backend/app/modules/assistente/schemas.py`, `app/core/limites.py`, Nginx | Pergunta sem token, vazia ou com mais de 1.000 caracteres; `tela` fora das telas do portal; recortes fora da lista ou com aspas, quebras de linha, `<` e `>`; mais de 20 perguntas por minuto ou a cota diária de tokens por usuário; o limite por IP do Nginx |
| 2 | Instruções | `ai-agent/src/venergy_ai/instrucoes.py` | A pergunta vai entre `<pergunta>` e `</pergunta>`, limpa até não sobrar tag. O contexto da tela (`<contexto>`) e a conversa (`<conversa>`) vão como JSON com `<` e `>` escapados. As instruções mandam tratar esses blocos e os textos dos dados como dado. É a camada mais fraca, e por isso nenhuma das seguintes depende dela |
| 3 | Guarda de SQL | `ai-agent/src/venergy_ai/guarda_sql.py` | Tudo que não é um único `SELECT` (com ou sem `WITH`): escrita, DDL, `SET`, `COPY`, várias instruções. Tabelas fora das views de `ai_read` do catálogo, como `operations` e `analytics`. Funções fora da lista permitida, como `set_config`, `pg_sleep` e os advisory locks. `SELECT INTO`, `FOR UPDATE`. Garante `LIMIT 1000`. Executa-se o SQL regenerado da árvore conferida, nunca o texto do modelo |
| 4 | Executor | `ai-agent/src/venergy_ai/executor.py` | Cada consulta roda numa transação encerrada com `ROLLBACK`: um `SET` não sobrevive na conexão do pool. O driver aceita uma instrução por vez. Banco fora do ar vira `503`, sem nova tentativa |
| 5 | Role `ai_read` | `infra/postgres/init.sql`, `importador/views.sql` | Só `USAGE` no schema `ai_read` e `SELECT` nas views: sem acesso a `operations` (usuários, ordens, auditoria) nem a `analytics`. `default_transaction_read_only = on`. `statement_timeout = 5s`. Sem `EXECUTE` em `set_config`, na família `pg_sleep` e nos advisory locks de sessão. Não é dona de nada: não altera nem apaga as views |
| 6 | Views sem dado pessoal | `importador/views.sql` | As views listam as colunas uma a uma, sem titular, documento, endereço nem o texto livre dos atendimentos. O tipo de irregularidade escrito no portal só chega como um dos cinco tipos da Silver ou `OUTRO`. Uma pergunta por esses dados vira "não sei" |
| 7 | Validação de saída | `ai-agent/src/venergy_ai/numeros.py` | Todo número do texto precisa estar nas linhas que o redator recebeu. Um número inventado, ou ditado por um texto dentro dos dados, vira "não sei" |
| 8 | Auditoria | `backend/migrations/versions/0003_agente_auditoria.py` | Toda pergunta fica registrada pela role `portal`, também as que falham: pergunta, contexto, SQL gerado e executado, linhas, resposta, modelo, tokens e erro. A `ai_read` não lê nem escreve a auditoria |

## Insights

Os insights da Visão Geral e da Receita não geram SQL: o backend calcula os fatos com os
serviços da tela e o modelo só redige. Valem as camadas 1 (limite por usuário, que conta
só o que vai ao modelo, e a cota diária de tokens), 2 (os fatos e os recortes vão como
JSON escapado num bloco `<fatos>`, tratado como dado, e o recorte da URL só vale com
valores da carga) e 7 (cada número da observação precisa estar nos fatos, na mesma
unidade; a observação com número de fora é descartada, e com menos de 3 válidas não há
insight). Testes:
`ai-agent/tests/test_redator_insights.py` e `backend/tests/test_insights.py`.

## Testes

`backend/tests/test_seguranca_ia.py` roda cada ataque pela rota real, com o LLM simulado
devolvendo o SQL malicioso:

- **Guarda ligada:** a guarda rejeita os 12 ataques nas duas tentativas, e o executor
  não recebe nada.
- **Guarda desligada:** o mesmo ataque vai ao banco, e o id do teste nomeia a camada que
  barra.

| Ataque | Camada do banco que barra | Erro do Postgres |
|---|---|---|
| `DROP VIEW`, `CREATE TABLE AS` | transação só leitura da role | `cannot execute ... in a read-only transaction` |
| `UPDATE`, `DELETE` nas views | privilégio da role | `permission denied for view ucs` |
| `INSERT` e leitura em `operations` | privilégio da role | `permission denied for schema operations` |
| Leitura de `analytics` | privilégio da role | `permission denied for schema analytics` |
| Várias instruções | driver (uma instrução por consulta preparada) | `cannot insert multiple commands into a prepared statement` |
| `set_config`, `pg_sleep`, `pg_advisory_lock` | `REVOKE EXECUTE` | `permission denied for function ...` |
| `COPY ... TO PROGRAM` | privilégio da role | `permission denied to COPY to or from an external program` |
| `SET statement_timeout = 0`, `SET default_transaction_read_only = off` | `ROLLBACK` da execução | a consulta seguinte, na mesma conexão, segue com `5s` e só leitura |
| Consulta longa | `statement_timeout` da role | `canceling statement due to statement timeout` |

O mesmo arquivo cobre também:

- sem o modo só leitura, a falta de privilégio ainda barra o DDL;
- uma pergunta por nome, CPF ou endereço vira "não sei", e esses dados não aparecem na
  resposta nem na auditoria;
- uma instrução escrita dentro dos dados chega ao redator como dado. Se ele obedecer,
  a validação de números barra a resposta.

Outros testes das camadas:

| Camada | Testes |
|---|---|
| Fronteira da API | `backend/tests/test_assistente.py` (validação e auditoria), `backend/tests/test_limites.py` |
| Instruções | `ai-agent/tests/test_agente.py` (delimitador, recortes e conversa) |
| Guarda de SQL | `ai-agent/tests/test_guarda_sql.py`, `ai-agent/tests/test_guarda_sql_postgres.py` |
| Executor | `ai-agent/tests/test_agente_postgres.py` |
| Role `ai_read` | `backend/tests/test_database_permissions.py` |
| Validação de saída | `ai-agent/tests/test_numeros.py` |
