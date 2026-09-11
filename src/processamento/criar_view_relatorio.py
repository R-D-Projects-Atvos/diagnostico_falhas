# -*- coding: utf-8 -*-
"""
Cria a view VW_RELATORIO_FALHAS no SDE e confere a area piloto.

Uma linha por talhao de inventario com tudo que o relatorio precisa.

Fontes:
  Status_Report_VANT    percentual OFICIAL (PIMS via BigQuery) - base da view
  BASE_SAFRA            cadastro do inventario (pre-plantio) + geometria
  LINHAS_FALHA          detalhamento espacial das falhas (Bem Agro)
  STG_VOO_MISSAO        voo que gerou o processamento
  STG_PORTE_AVALIACAO   avaliacao que autorizou o voo
  INDICADORES_CLIMA_TALHAO  chuva, veranico e temperatura na janela 0-30 DAP
  TALHAO_MANEJO             unidade de manejo de solo e declividade do talhao
  EPOCA_PLANTIO_TALHAO      classe da epoca de plantio segundo a matriz

Decisoes:
  - O percentual exibido e SEMPRE o FALHA_LINHA do PIMS. Os metros das linhas
    servem para m/ha, tamanho medio e mapa de calor, nunca para recalcular
    o percentual.
  - A area exibida e a do PIMS, nao a do inventario: e o denominador do
    numero oficial, e as duas divergem levemente.
  - Voo: missao de tipo Falhas, nao interrompida, mais recente ANTES da
    publicacao no PIMS.
  - Porte: ultima avaliacao APROVADA anterior ao voo.
  - O DPP do PIMS e ignorado (conta ate hoje). O DAP e calculado entre o
    plantio e a decolagem.
  - A BASE_SAFRA tem archiving: o join filtra GDB_TO_DATE para pegar so a
    linha vigente. Qualquer consulta SQL direta a essa camada precisa do
    mesmo filtro.
  - Cada indicador climatico vem com a media da unidade ao lado. O relatorio
    deve exibir os dois: chuva de 96 mm so significa algo ao lado dos 147 mm
    que o resto da unidade recebeu.
  - Ha duas janelas: PRE (-30 a -1 DAP), que diz em que condicao de umidade o
    solo estava no plantio, e POS (0 a 30 DAP), a brotacao.
  - CLIMA_DIAS_SEM_DADO diz quantos dias da janela a estacao nao registrou.
    Valor alto pede desconfianca dos acumulados.

O DDL vai direto ao SQL Server pela conexao SDE (ArcSDESQLExecute). A
ferramenta CreateDatabaseView remonta a definicao por dentro e quebra com
OUTER APPLY e subconsultas com alias.

Uso: python -u C:\\temp\\criar_view_relatorio.py

Geotecnologia / Cartografia - Atvos
"""

import functools
import arcpy

print = functools.partial(print, flush=True)

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
NOME_VIEW = "VW_RELATORIO_FALHAS"
CAMINHO = SDE + "\\ATVOSPUBLICADOR." + NOME_VIEW

META_PCT = 4.2
LIMITE_ATENCAO = 7.5

SQL = """
SELECT
    s.Layer                       AS CHAVESIG,
    s.UNIDADE                     AS UNIDADE,
    s.CD_UPNIVEL1                 AS COD_FAZENDA,
    s.DE_UPNIVEL1                 AS FAZENDA,
    s.CD_UPNIVEL2                 AS SETOR,
    s.CD_UPNIVEL3                 AS TALHAO,
    b.Safra                       AS SAFRA_INVENTARIO,
    b.BLOCO                       AS BLOCO,

    s.Area_total                  AS AREA_HA,
    s.VARIEDADE                   AS VARIEDADE,
    b.AMBIENTE                    AS AMBIENTE,
    b.ESPAC                       AS ESPAC_COD,
    s.SIST_PLANTIO                AS SIST_PLANTIO,
    s.ADMIN                       AS ADMINISTRACAO,
    s.FG_REPLANTIO                AS FG_REPLANTIO,
    s.DT_PLANTIO                  AS DT_PLANTIO,

    s.FALHA_LINHA                 AS FALHA_PCT,
    s.DATA_AMOSTRA                AS DT_PUBLICACAO_PIMS,
    s.Status_Falha                AS STATUS_FALHA,

    CASE
        WHEN s.FALHA_LINHA IS NULL THEN 'Sem resultado'
        WHEN s.FALHA_LINHA <= {meta} THEN 'Dentro da meta'
        WHEN s.FALHA_LINHA <= {atencao} THEN 'Atencao'
        ELSE 'Critico'
    END                           AS STATUS_META,

    f.QTD_FALHAS                  AS QTD_FALHAS,
    f.METROS_FALHA                AS METROS_FALHA,
    f.TAM_MEDIO_M                 AS TAM_MEDIO_M,
    CASE WHEN s.Area_total > 0
         THEN CAST(f.METROS_FALHA / s.Area_total AS DECIMAL(10,1))
    END                           AS METROS_POR_HA,
    f.MAIOR_FALHA_M               AS MAIOR_FALHA_M,
    CASE WHEN f.CHAVESIG IS NULL THEN 0 ELSE 1 END AS TEM_LINHAS,

    v.DT_SAIDA                    AS DT_VOO,
    v.PILOTO                      AS PILOTO_VOO,
    v.VANT                        AS VANT,
    v.DURACAO_H                   AS DURACAO_H,
    v.RESULTADO_MISSAO            AS RESULTADO_MISSAO,
    DATEDIFF(day, s.DT_PLANTIO, v.DT_SAIDA)   AS DAP_VOO,

    p.DT_AVALIACAO                AS DT_PORTE,
    p.PILOTO                      AS PILOTO_PORTE,
    p.PORTE_ADEQUADO              AS PORTE_ADEQUADO,
    DATEDIFF(day, p.DT_AVALIACAO, v.DT_SAIDA) AS DIAS_PORTE_ATE_VOO,

    c.ESTACAO_NOME                AS ESTACAO,
    c.DISTANCIA_KM                AS ESTACAO_DIST_KM,
    c.CONFIABILIDADE              AS CLIMA_CONFIABILIDADE,
    c.DIAS_SEM_DADO               AS CLIMA_DIAS_SEM_DADO,
    c.CHUVA_PRE_15                AS CHUVA_PRE_15,
    c.CHUVA_PRE_30                AS CHUVA_PRE_30,
    c.CHUVA_PRE_30_UNID           AS CHUVA_PRE_30_UNID,
    c.DIAS_SEM_DADO_PRE           AS CLIMA_DIAS_SEM_DADO_PRE,
    c.CHUVA_0_15                  AS CHUVA_0_15,
    c.CHUVA_0_15_UNID             AS CHUVA_0_15_UNID,
    c.CHUVA_0_30                  AS CHUVA_0_30,
    c.CHUVA_0_30_UNID             AS CHUVA_0_30_UNID,
    c.DIAS_COM_CHUVA              AS DIAS_COM_CHUVA,
    c.DIAS_CHUVA_UNID             AS DIAS_CHUVA_UNID,
    c.MAIOR_VERANICO              AS MAIOR_VERANICO,
    c.VERANICO_UNID               AS VERANICO_UNID,
    c.TMAX_MEDIA                  AS TMAX_MEDIA,
    c.DIAS_TMAX_ALTA              AS DIAS_TMAX_ALTA,

    /* chuva da area em relacao a media da unidade, em % - e essa razao,
       nao o valor absoluto, que diz se a area foi penalizada */
    CASE WHEN c.CHUVA_0_30_UNID > 0
         THEN CAST(100.0 * c.CHUVA_0_30 / c.CHUVA_0_30_UNID AS DECIMAL(6,1))
    END                           AS CHUVA_VS_UNIDADE_PCT,

    CASE WHEN c.CHUVA_PRE_30_UNID > 0
         THEN CAST(100.0 * c.CHUVA_PRE_30 / c.CHUVA_PRE_30_UNID AS DECIMAL(6,1))
    END                           AS CHUVA_PRE_VS_UNIDADE_PCT,

    /* --- solo e epoca de plantio (Matriz de Plantio) ------------------- */
    m.NUM_MANEJO                  AS UNIDADE_MANEJO,
    m.MANEJO                      AS AGRUP_SOLOS,
    m.TEXTURA                     AS TEXTURA_SOLO,
    m.PCT_AREA                    AS MANEJO_PCT_AREA,
    m.DECLIV_MEDIANA              AS DECLIVIDADE_PCT,
    m.FAIXA_DECLIV                AS FAIXA_DECLIVIDADE,
    e.PERIODO_PLANTIO             AS PERIODO_PLANTIO,
    e.CLASSE_EPOCA                AS CLASSE_EPOCA,

    /* a matriz classifica supondo manejo de cobertura; sem isso a classe
       afirma mais do que a matriz diz - por isso a condicao vem junto */
    e.CONDICAO                    AS EPOCA_CONDICAO,
    e.EPOCA_CONFIANCA             AS EPOCA_CONFIANCA,
    e.CLASSE_ALTERNATIVA          AS EPOCA_ALTERNATIVA,
    e.MOTIVO_RESSALVA             AS EPOCA_MOTIVO_RESSALVA,

    /* atalho para o semaforo do relatorio: plantio fora da epoca indicada.
       "Favoravel com irrigacao" NAO entra aqui - e plantio de inverno, que
       e pratica deliberada, e a matriz o considera adequado quando ha
       irrigacao ou salvamento. Somar os dois exageraria o problema. */
    CASE WHEN e.CLASSE_EPOCA = 'Restritivo' THEN 1
         WHEN e.CLASSE_EPOCA IS NULL THEN NULL
         ELSE 0 END               AS EPOCA_FORA_DA_INDICADA,

    b.Shape                       AS Shape,
    b.OBJECTID                    AS OBJECTID

FROM ATVOSPUBLICADOR.Status_Report_VANT AS s

/* A BASE_SAFRA tem ARCHIVING ligado: cada edicao cria uma linha nova e
   aposenta a anterior. O ArcGIS filtra isso sozinho, o SQL direto nao -
   sem o filtro abaixo a view multiplica por ~137 (uma copia por dia de
   execucao da rotina). GDB_TO_DATE no maximo = linha vigente. */
LEFT JOIN ATVOSPUBLICADOR.BASE_SAFRA AS b
       ON b.Chavesig = s.Layer
      AND b.GDB_TO_DATE = '9999-12-31 23:59:59'

LEFT JOIN (
    SELECT
        CHAVESIG,
        COUNT(*)                               AS QTD_FALHAS,
        CAST(SUM(COMP_OFI_M) AS DECIMAL(12,1)) AS METROS_FALHA,
        CAST(AVG(COMP_OFI_M) AS DECIMAL(6,2))  AS TAM_MEDIO_M,
        CAST(MAX(COMP_OFI_M) AS DECIMAL(6,2))  AS MAIOR_FALHA_M
    FROM ATVOSPUBLICADOR.LINHAS_FALHA
    WHERE CHAVESIG IS NOT NULL
    GROUP BY CHAVESIG
) AS f ON f.CHAVESIG = s.Layer

OUTER APPLY (
    SELECT TOP 1 m.DT_SAIDA, m.PILOTO, m.VANT, m.DURACAO_H, m.RESULTADO_MISSAO
    FROM ATVOSPUBLICADOR.STG_VOO_MISSAO AS m
    WHERE m.CHAVESIG = s.Layer
      AND m.TIPO_MISSAO = 'Falhas'
      AND ISNULL(m.RESULTADO_MISSAO, '') <> 'Interrompido'
      AND (s.DATA_AMOSTRA IS NULL OR m.DT_SAIDA <= s.DATA_AMOSTRA)
    ORDER BY m.DT_SAIDA DESC
) AS v

OUTER APPLY (
    SELECT TOP 1 a.DT_AVALIACAO, a.PILOTO, a.PORTE_ADEQUADO
    FROM ATVOSPUBLICADOR.STG_PORTE_AVALIACAO AS a
    WHERE a.CHAVESIG = s.Layer
      AND a.PORTE_ADEQUADO = 'sim'
      AND (v.DT_SAIDA IS NULL OR a.DT_AVALIACAO <= v.DT_SAIDA)
    ORDER BY a.DT_AVALIACAO DESC
) AS p

/* indicadores da janela 0-30 DAP, ja com a media da unidade ao lado */
LEFT JOIN ATVOSPUBLICADOR.INDICADORES_CLIMA_TALHAO AS c
       ON c.CHAVESIG = s.Layer

/* solo: uma linha por talhao, ja resolvida pela unidade predominante */
LEFT JOIN ATVOSPUBLICADOR.TALHAO_MANEJO AS m
       ON m.CHAVESIG = s.Layer

/* epoca: depende de manejo + declividade + data de plantio */
LEFT JOIN ATVOSPUBLICADOR.EPOCA_PLANTIO_TALHAO AS e
       ON e.CHAVESIG = s.Layer
""".format(meta=META_PCT, atencao=LIMITE_ATENCAO)


def conexao():
    return arcpy.ArcSDESQLExecute(SDE)


def criar(con):
    print("removendo versao anterior, se existir...")
    con.execute("IF OBJECT_ID('ATVOSPUBLICADOR.%s', 'V') IS NOT NULL "
                "DROP VIEW ATVOSPUBLICADOR.%s" % (NOME_VIEW, NOME_VIEW))

    print("criando %s ..." % NOME_VIEW)
    con.execute("CREATE VIEW ATVOSPUBLICADOR.%s AS %s" % (NOME_VIEW, SQL))
    print("criada: ATVOSPUBLICADOR.%s" % NOME_VIEW)


def conferir_piloto(con):
    campos = ["CHAVESIG", "TALHAO", "FALHA_PCT", "STATUS_META",
              "METROS_POR_HA", "DAP_VOO", "ESTACAO", "ESTACAO_DIST_KM",
              "CHUVA_0_30", "CHUVA_0_30_UNID", "CHUVA_VS_UNIDADE_PCT",
              "MAIOR_VERANICO", "VERANICO_UNID", "CLIMA_DIAS_SEM_DADO"]
    consulta = ("SELECT %s FROM ATVOSPUBLICADOR.%s WHERE COD_FAZENDA = '320127' "
                "ORDER BY CAST(TALHAO AS INT)"
                % (", ".join(campos), NOME_VIEW))

    print("\n=== area piloto (fazenda 320127) ===")
    print(" | ".join(campos))
    resultado = con.execute(consulta)
    if not isinstance(resultado, list):
        print("(nada encontrado)")
    else:
        for linha in resultado:
            print(" | ".join("-" if v is None else str(v) for v in linha))
    print("\nesperado: talhao 6 com 23,8% | chuva 96,4 contra 146,8 da unidade "
          "(66%) | veranico 8 contra 10,2")


def checar_duplicidade(con):
    """A view tem que ter exatamente uma linha por talhao."""
    linha = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT CHAVESIG) FROM ATVOSPUBLICADOR.%s"
        % NOME_VIEW)
    if isinstance(linha[0], list):
        linha = linha[0]
    total, distintos = linha
    print("\n=== integridade ===")
    print("  linhas na view    : %s" % total)
    print("  chavesig distintos: %s" % distintos)
    if total != distintos:
        print("  ATENCAO: ha duplicacao - %d linhas a mais que talhoes"
              % (total - distintos))
    else:
        print("  ok: uma linha por talhao")


def cobertura(con):
    consulta = """
        SELECT COUNT(*),
               SUM(CASE WHEN FALHA_PCT IS NOT NULL THEN 1 ELSE 0 END),
               SUM(TEM_LINHAS),
               SUM(CASE WHEN DT_VOO   IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN DT_PORTE IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN CHUVA_0_30 IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN CLIMA_CONFIABILIDADE = 'Ressalva' THEN 1 ELSE 0 END),
               SUM(CASE WHEN Shape    IS NULL     THEN 1 ELSE 0 END)
        FROM ATVOSPUBLICADOR.%s""" % NOME_VIEW
    linha = con.execute(consulta)
    if isinstance(linha[0], list):
        linha = linha[0]

    rotulos = ["talhoes na view", "com percentual PIMS", "com linhas de falha",
               "com voo vinculado", "com porte vinculado", "com clima",
               "clima com ressalva", "sem geometria"]
    print("\n=== cobertura da base ===")
    for rotulo, valor in zip(rotulos, linha):
        print("  %-22s: %s" % (rotulo, valor))


if __name__ == "__main__":
    con = conexao()
    criar(con)
    checar_duplicidade(con)
    conferir_piloto(con)
    cobertura(con)
    print("\nPara publicar como camada, registre a view com o geodatabase "
          "pelo Catalog (ela precisa de campo de ID e indice espacial).")