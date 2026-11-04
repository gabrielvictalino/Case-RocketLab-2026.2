-- Executado uma vez pelo entrypoint do PostgreSQL. Alembic assume cargas depois.
CREATE ROLE portal LOGIN PASSWORD :'portal_password';
CREATE ROLE ai_read LOGIN PASSWORD :'ai_password';
CREATE ROLE importador LOGIN PASSWORD :'importador_password';
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO portal, ai_read, importador',
              current_database()) \gexec
SELECT format('GRANT CREATE ON DATABASE %I TO importador', current_database()) \gexec
CREATE SCHEMA analytics AUTHORIZATION importador;
CREATE SCHEMA ai_read AUTHORIZATION importador;
CREATE SCHEMA operations;
GRANT USAGE ON SCHEMA analytics, ai_read, operations TO portal;
GRANT USAGE ON SCHEMA ai_read TO ai_read;
GRANT USAGE ON SCHEMA operations TO importador;
ALTER ROLE ai_read SET default_transaction_read_only = on;
ALTER ROLE ai_read SET statement_timeout = '5s';
ALTER ROLE ai_read SET search_path = ai_read, pg_catalog;
-- Sem essas funções, a IA não troca parâmetros da sessão por SELECT nem prende conexões.
-- O SET continua possível; por isso o agente encerra cada consulta com ROLLBACK.
REVOKE EXECUTE ON FUNCTION pg_catalog.set_config(text, text, boolean),
  pg_catalog.pg_sleep(double precision), pg_catalog.pg_sleep_for(interval),
  pg_catalog.pg_sleep_until(timestamp with time zone) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pg_catalog.set_config(text, text, boolean),
  pg_catalog.pg_sleep(double precision), pg_catalog.pg_sleep_for(interval),
  pg_catalog.pg_sleep_until(timestamp with time zone) TO portal, importador;
-- O ROLLBACK não solta um advisory lock de sessão: com o lock das cargas, a IA travaria
-- o importador. Só o importador usa advisory lock.
REVOKE EXECUTE ON FUNCTION pg_catalog.pg_advisory_lock(bigint),
  pg_catalog.pg_advisory_lock(integer, integer), pg_catalog.pg_advisory_lock_shared(bigint),
  pg_catalog.pg_advisory_lock_shared(integer, integer),
  pg_catalog.pg_try_advisory_lock(bigint), pg_catalog.pg_try_advisory_lock(integer, integer),
  pg_catalog.pg_try_advisory_lock_shared(bigint),
  pg_catalog.pg_try_advisory_lock_shared(integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_advisory_lock(bigint),
  pg_catalog.pg_advisory_lock(integer, integer), pg_catalog.pg_advisory_lock_shared(bigint),
  pg_catalog.pg_advisory_lock_shared(integer, integer),
  pg_catalog.pg_try_advisory_lock(bigint), pg_catalog.pg_try_advisory_lock(integer, integer),
  pg_catalog.pg_try_advisory_lock_shared(bigint),
  pg_catalog.pg_try_advisory_lock_shared(integer, integer) TO importador;
ALTER DEFAULT PRIVILEGES FOR ROLE importador IN SCHEMA analytics
  GRANT SELECT ON TABLES TO portal;
CREATE TABLE operations.cargas (
  id uuid PRIMARY KEY,
  batch_id text NOT NULL,
  versao_contrato text NOT NULL,
  sintetica boolean NOT NULL,
  periodo_inicio date NOT NULL,
  periodo_fim date NOT NULL,
  carregado_em timestamptz NOT NULL DEFAULT now(),
  manifesto jsonb NOT NULL
);
GRANT INSERT ON operations.cargas TO importador;
GRANT SELECT ON operations.cargas TO portal;
