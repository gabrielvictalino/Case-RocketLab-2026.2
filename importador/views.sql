-- Identidade histórica preservada; origem desambigua IDs históricos e do portal.
CREATE OR REPLACE VIEW portal_read.inspecoes AS
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'historica'::text AS origem FROM analytics.inspecoes_historicas
 UNION ALL
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'portal'::text AS origem FROM operations.inspecoes;
GRANT SELECT ON portal_read.inspecoes TO portal;
-- A IA vê só as views abaixo, recriadas do zero a cada carga: view ou grant que sai
-- deste arquivo some do banco. Um DROP só para todas não depende da ordem, mesmo com uma
-- view de ai_read lendo outra. Sem CASCADE, uma dependência de fora aborta a carga.
DO $$
DECLARE views text;
BEGIN
  SELECT string_agg(format('ai_read.%I', viewname), ', ') INTO views
  FROM pg_views WHERE schemaname = 'ai_read';
  IF views IS NOT NULL THEN
    EXECUTE 'DROP VIEW ' || views;
  END IF;
END $$;
-- Colunas listadas uma a uma: coluna nova no contrato só chega à IA depois de revisão.
-- A projeção da IA é independente da view do portal.
CREATE VIEW ai_read.inspecoes AS
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'historica'::text AS origem FROM analytics.inspecoes_historicas
 UNION ALL
 SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
        'portal'::text AS origem FROM operations.inspecoes;
GRANT SELECT ON ai_read.inspecoes TO ai_read;
-- Não expõe titular, documento ou endereço.
CREATE VIEW ai_read.ucs AS
 SELECT id_uc,municipio,bairro,classe,alimentador,flag_gd,flag_irregularidade_confirmada
 FROM analytics.dim_uc;
GRANT SELECT ON ai_read.ucs TO ai_read;
CREATE VIEW ai_read.receita_volume_mensal AS
 SELECT competencia,municipio,bairro,classe,grupo_uc,volume_faturado_kwh,receita,
        receita_arrecadada,componente_tarifa_reais,componente_bandeira_reais
 FROM analytics.receita_volume_mensal;
GRANT SELECT ON ai_read.receita_volume_mensal TO ai_read;
CREATE VIEW ai_read.uc_consumo_faturamento_mensal AS
 SELECT id_uc,competencia,consumo_kwh_original,consumo_kwh_analitico,metodo_consumo,
        tipo_leitura,flag_troca_medidor,id_fatura,volume_faturado_kwh,valor_total,
        valor_arrecadado,tarifa_base,adicional_bandeira,bandeira,status_pagamento,
        data_vencimento,grupo_uc
 FROM analytics.uc_consumo_faturamento_mensal;
GRANT SELECT ON ai_read.uc_consumo_faturamento_mensal TO ai_read;
CREATE VIEW ai_read.gd_uc AS
 SELECT id_uc,potencia_kw,data_conexao FROM analytics.gd_uc;
GRANT SELECT ON ai_read.gd_uc TO ai_read;
CREATE VIEW ai_read.medidores_historico AS
 SELECT id_medidor,id_uc,data_instalacao,data_retirada,tipo_medidor
 FROM analytics.medidores_historico;
GRANT SELECT ON ai_read.medidores_historico TO ai_read;
CREATE VIEW ai_read.continuidade_alimentador_mensal AS
 SELECT alimentador,competencia,numero_ucs,chi_horas,interrupcoes,dec,fec,causa,
        flag_evento_atipico
 FROM analytics.continuidade_alimentador_mensal;
GRANT SELECT ON ai_read.continuidade_alimentador_mensal TO ai_read;
CREATE VIEW ai_read.ocorrencias_uc AS
 SELECT id_ocorrencia,id_uc,alimentador,data_abertura,data_encerramento,duracao_min,
        duracao_efetiva_min,causa,flag_sobreposicao
 FROM analytics.ocorrencias_uc;
GRANT SELECT ON ai_read.ocorrencias_uc TO ai_read;
CREATE VIEW ai_read.atendimentos AS
 SELECT protocolo,id_uc,aberto_em,assunto,status,nota FROM analytics.atendimentos;
GRANT SELECT ON ai_read.atendimentos TO ai_read;
-- Só as datas das tratativas. A descrição é texto livre do cliente.
CREATE VIEW ai_read.atendimentos_historico AS
 SELECT protocolo,sequencia,data FROM analytics.atendimentos_historico;
GRANT SELECT ON ai_read.atendimentos_historico TO ai_read;
CREATE VIEW ai_read.fila_inspecao AS
 SELECT id_uc,score,motivos,energia_recuperar_kwh,energia_recuperar_reais
 FROM analytics.fila_inspecao;
GRANT SELECT ON ai_read.fila_inspecao TO ai_read;
