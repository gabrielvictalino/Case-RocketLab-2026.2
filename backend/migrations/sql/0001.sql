CREATE TABLE operations.usuarios (
  id uuid PRIMARY KEY,
  login text NOT NULL UNIQUE,
  nome text NOT NULL,
  cargo text NOT NULL CHECK (cargo IN
    ('diretoria','comercial','atendimento','perdas','operacao')),
  senha_hash text NOT NULL,
  ativo boolean NOT NULL DEFAULT true
);
CREATE TABLE operations.ordens_inspecao (
  id uuid PRIMARY KEY,
  id_uc text NOT NULL,
  status text NOT NULL DEFAULT 'ABERTA'
    CHECK (status IN ('ABERTA','EM_CAMPO','CONCLUIDA','CANCELADA')),
  score numeric(12,4) NOT NULL,
  motivos jsonb NOT NULL,
  energia_recuperar_kwh numeric(18,2) NOT NULL CHECK (energia_recuperar_kwh >= 0),
  energia_recuperar_reais numeric(18,2) NOT NULL CHECK (energia_recuperar_reais >= 0),
  inspetor text CHECK (inspetor ~ '^INSP-(00[1-9]|0[1-3][0-9]|040)$'),
  resultado text CHECK (resultado IN ('IRREGULARIDADE CONFIRMADA','SEM IRREGULARIDADE')),
  tipo_irregularidade text,
  kwh_recuperado numeric(18,2),
  motivo_cancelamento text,
  criado_por uuid NOT NULL REFERENCES operations.usuarios,
  atualizado_por uuid NOT NULL REFERENCES operations.usuarios,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'EM_CAMPO' OR inspetor IS NOT NULL),
  CHECK (status <> 'CONCLUIDA' OR (inspetor IS NOT NULL AND resultado IS NOT NULL
    AND kwh_recuperado IS NOT NULL AND (
    (resultado = 'IRREGULARIDADE CONFIRMADA' AND
      nullif(btrim(tipo_irregularidade),'') IS NOT NULL AND kwh_recuperado > 0)
    OR (resultado = 'SEM IRREGULARIDADE' AND
      tipo_irregularidade IS NULL AND kwh_recuperado = 0)))),
  CHECK (status <> 'CANCELADA' OR nullif(btrim(motivo_cancelamento),'') IS NOT NULL)
);
CREATE UNIQUE INDEX uq_ordem_ativa ON operations.ordens_inspecao(id_uc)
  WHERE status IN ('ABERTA','EM_CAMPO');
CREATE TABLE operations.ordem_eventos (
  id uuid PRIMARY KEY,
  id_ordem uuid NOT NULL REFERENCES operations.ordens_inspecao,
  tipo text NOT NULL,
  autor uuid NOT NULL REFERENCES operations.usuarios,
  data timestamptz NOT NULL DEFAULT now(),
  dados jsonb NOT NULL
);
CREATE INDEX ix_eventos_ordem ON operations.ordem_eventos(id_ordem, data);
CREATE TABLE operations.inspecoes (
  id_inspecao text PRIMARY KEY,
  id_uc text NOT NULL,
  data date NOT NULL,
  inspetor text NOT NULL CHECK (inspetor ~ '^INSP-(00[1-9]|0[1-3][0-9]|040)$'),
  resultado text NOT NULL CHECK
    (resultado IN ('IRREGULARIDADE CONFIRMADA','SEM IRREGULARIDADE')),
  tipo_irregularidade text,
  kwh_recuperado numeric(18,2) NOT NULL,
  id_ordem uuid NOT NULL UNIQUE REFERENCES operations.ordens_inspecao,
  CHECK ((resultado = 'IRREGULARIDADE CONFIRMADA' AND
    nullif(btrim(tipo_irregularidade),'') IS NOT NULL AND kwh_recuperado > 0)
    OR (resultado = 'SEM IRREGULARIDADE' AND tipo_irregularidade IS NULL
      AND kwh_recuperado = 0))
);
CREATE INDEX ix_inspecoes_uc ON operations.inspecoes(id_uc, data);
GRANT SELECT, INSERT, UPDATE ON operations.usuarios TO portal;
GRANT SELECT, INSERT, UPDATE ON operations.ordens_inspecao TO portal;
GRANT SELECT, INSERT ON operations.ordem_eventos, operations.inspecoes TO portal;
GRANT SELECT ON operations.inspecoes TO importador;
