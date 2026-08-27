/* ===========================================================================
   VW_RELATORIO_FALHAS
   Uma linha por talhao de inventario com tudo que o relatorio precisa.

   Fontes:
     Status_Report_VANT     percentual OFICIAL (PIMS via BigQuery) - base
     BASE_SAFRA             cadastro do inventario (pre-plantio) + geometria
     LINHAS_FALHA           detalhamento espacial das falhas (Bem Agro)
     STG_VOO_MISSAO         voo que gerou o processamento
     STG_PORTE_AVALIACAO    avaliacao que autorizou o voo

   Decisoes:
     - O percentual exibido e SEMPRE o FALHA_LINHA do PIMS. Os metros das
       linhas servem para m/ha, tamanho medio e mapa de calor, nunca para
       recalcular o percentual.
     - A area exibida e a do PIMS (Area_total de Status_Report_VANT), nao a
       do inventario: e o denominador do numero oficial.
     - Voo: missao de tipo Falhas, nao interrompida, mais recente ANTES da
       publicacao no PIMS.
     - Porte: ultima avaliacao APROVADA anterior ao voo - foi ela que o
       autorizou.
     - DPP do PIMS e ignorado (conta ate hoje, nao ate o voo). O DAP e
       calculado entre o plantio e a decolagem.

   Geotecnologia / Cartografia - Atvos
   =========================================================================== */

CREATE OR ALTER VIEW ATVOSPUBLICADOR.VW_RELATORIO_FALHAS AS
SELECT
    /* --- identificacao --- */
    s.Layer                       AS CHAVESIG,
    s.UNIDADE,
    s.CD_UPNIVEL1                 AS COD_FAZENDA,
    s.DE_UPNIVEL1                 AS FAZENDA,
    s.CD_UPNIVEL2                 AS SETOR,
    s.CD_UPNIVEL3                 AS TALHAO,
    b.Safra                       AS SAFRA_INVENTARIO,
    b.BLOCO,

    /* --- cadastro --- */
    s.Area_total                  AS AREA_HA,
    s.VARIEDADE,
    b.AMBIENTE,
    b.ESPAC                       AS ESPAC_COD,
    s.SIST_PLANTIO,
    s.ADMIN,
    s.FG_REPLANTIO,
    s.DT_PLANTIO,

    /* --- resultado oficial --- */
    s.FALHA_LINHA                 AS FALHA_PCT,
    s.DATA_AMOSTRA                AS DT_PUBLICACAO_PIMS,
    s.Status_Falha,

    CASE
        WHEN s.FALHA_LINHA IS NULL       THEN 'Sem resultado'
        WHEN s.FALHA_LINHA <= 4.2        THEN 'Dentro da meta'
        WHEN s.FALHA_LINHA <= 7.5        THEN 'Atencao'
        ELSE 'Critico'
    END                           AS STATUS_META,

    /* --- detalhamento espacial (linhas da Bem Agro) --- */
    f.QTD_FALHAS,
    f.METROS_FALHA,
    f.TAM_MEDIO_M,
    CASE WHEN s.Area_total > 0
         THEN CAST(f.METROS_FALHA / s.Area_total AS DECIMAL(10,1))
    END                           AS METROS_POR_HA,
    f.MAIOR_FALHA_M,
    CASE WHEN f.CHAVESIG IS NULL THEN 0 ELSE 1 END AS TEM_LINHAS,

    /* --- voo --- */
    v.DT_SAIDA                    AS DT_VOO,
    v.PILOTO                      AS PILOTO_VOO,
    v.VANT,
    v.DURACAO_H,
    v.RESULTADO_MISSAO,
    DATEDIFF(day, s.DT_PLANTIO, v.DT_SAIDA)   AS DAP_VOO,

    /* --- porte --- */
    p.DT_AVALIACAO                AS DT_PORTE,
    p.PILOTO                      AS PILOTO_PORTE,
    p.PORTE_ADEQUADO,
    DATEDIFF(day, p.DT_AVALIACAO, v.DT_SAIDA) AS DIAS_PORTE_ATE_VOO,

    b.Shape,
    b.OBJECTID                    AS OBJECTID

FROM ATVOSPUBLICADOR.Status_Report_VANT AS s

/* cadastro e geometria do inventario */
LEFT JOIN ATVOSPUBLICADOR.BASE_SAFRA AS b
       ON b.Chavesig = s.Layer

/* agregacao das linhas de falha */
LEFT JOIN (
    SELECT
        CHAVESIG,
        COUNT(*)                              AS QTD_FALHAS,
        CAST(SUM(COMP_OFI_M) AS DECIMAL(12,1)) AS METROS_FALHA,
        CAST(AVG(COMP_OFI_M) AS DECIMAL(6,2))  AS TAM_MEDIO_M,
        CAST(MAX(COMP_OFI_M) AS DECIMAL(6,2))  AS MAIOR_FALHA_M
    FROM ATVOSPUBLICADOR.LINHAS_FALHA
    WHERE CHAVESIG IS NOT NULL
    GROUP BY CHAVESIG
) AS f ON f.CHAVESIG = s.Layer

/* voo de falhas que originou o processamento */
OUTER APPLY (
    SELECT TOP 1 m.DT_SAIDA, m.PILOTO, m.VANT, m.DURACAO_H, m.RESULTADO_MISSAO
    FROM ATVOSPUBLICADOR.STG_VOO_MISSAO AS m
    WHERE m.CHAVESIG = s.Layer
      AND m.TIPO_MISSAO = 'Falhas'
      AND ISNULL(m.RESULTADO_MISSAO, '') <> 'Interrompido'
      AND (s.DATA_AMOSTRA IS NULL OR m.DT_SAIDA <= s.DATA_AMOSTRA)
    ORDER BY m.DT_SAIDA DESC
) AS v

/* avaliacao de porte que autorizou aquele voo */
OUTER APPLY (
    SELECT TOP 1 a.DT_AVALIACAO, a.PILOTO, a.PORTE_ADEQUADO
    FROM ATVOSPUBLICADOR.STG_PORTE_AVALIACAO AS a
    WHERE a.CHAVESIG = s.Layer
      AND a.PORTE_ADEQUADO = 'sim'
      AND (v.DT_SAIDA IS NULL OR a.DT_AVALIACAO <= v.DT_SAIDA)
    ORDER BY a.DT_AVALIACAO DESC
) AS p;
GO


/* ===========================================================================
   Conferencia da area piloto
   Esperado: 4 talhoes, o ...0006 com 23,8% e status Critico,
             DAP de 127 dias e 14 dias entre porte e voo.
   =========================================================================== */
SELECT CHAVESIG, TALHAO, AREA_HA, FALHA_PCT, STATUS_META,
       QTD_FALHAS, METROS_FALHA, TAM_MEDIO_M, METROS_POR_HA,
       DT_PLANTIO, DT_VOO, DAP_VOO, DT_PORTE, DIAS_PORTE_ATE_VOO
FROM ATVOSPUBLICADOR.VW_RELATORIO_FALHAS
WHERE COD_FAZENDA = '320127'
ORDER BY CAST(TALHAO AS INT);
GO


/* ===========================================================================
   Cobertura geral: quanto da base ja tem cada peca
   =========================================================================== */
SELECT
    COUNT(*)                                          AS talhoes,
    SUM(CASE WHEN FALHA_PCT   IS NOT NULL THEN 1 ELSE 0 END) AS com_percentual,
    SUM(TEM_LINHAS)                                   AS com_linhas_falha,
    SUM(CASE WHEN DT_VOO      IS NOT NULL THEN 1 ELSE 0 END) AS com_voo,
    SUM(CASE WHEN DT_PORTE    IS NOT NULL THEN 1 ELSE 0 END) AS com_porte,
    SUM(CASE WHEN Shape       IS NULL     THEN 1 ELSE 0 END) AS sem_geometria
FROM ATVOSPUBLICADOR.VW_RELATORIO_FALHAS;
GO
