-- Monitoramento diario das estacoes Zeus, agregado por estacao e dia.
--
-- E a consulta da planilha "monitoramento_pic - Monitoramento das estacoes
-- Zeus.xlsx" (Power Query, conexao ODBC ao BigQuery), que o Excel salva em
-- DIAGNOSTICO_FALHAS\ENTRADAS\CLIMA e o carga_monitoramento_zeus.py le.
--
-- Quando o servidor tiver acesso ao BigQuery, a carga passa a rodar esta
-- consulta direto. A ordem e os nomes das colunas sao os que a carga confere
-- (COLUNAS_ESPERADAS) - mudar aqui exige mudar la.
--
-- Traz o historico inteiro ate ONTEM: o dia corrente ainda esta incompleto.

SELECT
  picId,
  DATE(started, "America/Sao_Paulo") AS dia,

  -- Temperatura
  ROUND(MIN(temperatureMin), 2)  AS temp_min,
  ROUND(AVG(temperatureInst), 2) AS temp_media,
  ROUND(MAX(temperatureMax), 2)  AS temp_max,

  -- Umidade
  ROUND(MIN(humidityMin), 2)  AS umid_min,
  ROUND(AVG(humidityInst), 2) AS umid_media,
  ROUND(MAX(humidityMax), 2)  AS umid_max,

  -- Pressao atmosferica
  ROUND(MIN(atmosphericPressureMin), 2)  AS pressao_min,
  ROUND(AVG(atmosphericPressureInst), 2) AS pressao_media,
  ROUND(MAX(atmosphericPressureMax), 2)  AS pressao_max,

  -- Vento (so existe instantaneo/media, nao min/max)
  ROUND(AVG(windSpeedInst), 2)    AS vento_inst_media,
  ROUND(AVG(windSpeedAverage), 2) AS vento_media,
  ROUND(MAX(gustSpeed), 2)        AS rajada_max,

  -- Chuva (soma, nao media)
  ROUND(SUM(rain), 2) AS chuva_total,

  -- Irradiacao solar
  ROUND(AVG(solarIrradiation), 2) AS irradiacao_media

FROM `dl-bq-prd.bronze_zeus.monitoramento_pic`
WHERE started IS NOT NULL
  AND DATE(started, "America/Sao_Paulo") < CURRENT_DATE("America/Sao_Paulo")
GROUP BY picId, dia
ORDER BY picId, dia
