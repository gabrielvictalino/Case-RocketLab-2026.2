-- Identidade histórica preservada; origem desambigua IDs históricos e do portal.
CREATE OR REPLACE VIEW portal_read.inspecoes AS
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'historica'::text AS origem FROM analytics.inspecoes_historicas
 UNION ALL
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'portal'::text AS origem FROM operations.inspecoes;
GRANT SELECT ON portal_read.inspecoes TO portal;
-- A projeção da IA é independente da view do portal; novas colunas exigem revisão.
CREATE OR REPLACE VIEW ai_read.inspecoes AS
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'historica'::text AS origem FROM analytics.inspecoes_historicas
 UNION ALL
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'portal'::text AS origem FROM operations.inspecoes;
-- Allowlist explícita. Não expõe titular, documento ou endereço detalhado.
CREATE OR REPLACE VIEW ai_read.ucs AS
 SELECT id_uc,municipio,bairro,classe,alimentador,flag_gd,flag_irregularidade_confirmada
 FROM analytics.dim_uc;
REVOKE ALL ON ai_read.inspecoes FROM portal;
GRANT SELECT ON ai_read.inspecoes TO ai_read;
GRANT SELECT ON ai_read.ucs TO portal, ai_read;
