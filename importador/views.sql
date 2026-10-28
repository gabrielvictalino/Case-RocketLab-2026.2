-- Identidade histórica preservada; origem desambigua IDs históricos e do portal.
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
GRANT SELECT ON ai_read.inspecoes, ai_read.ucs TO portal, ai_read;
