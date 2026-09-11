# -*- coding: utf-8 -*-
"""
Gera o relatorio de falhas de uma area: le a VW_RELATORIO_FALHAS, desenha o
mapa de calor e monta o HTML paginado.

Saida: uma pasta por area, com o HTML e o PNG do mapa.

O mapa e desenhado com matplotlib a partir do raster de densidade e dos
poligonos do inventario. Nao depende de um .aprx como molde: o layout fica
inteiro no codigo e nao quebra se alguem editar um projeto do Pro.

Escala do mapa de calor - quebras FIXAS, ancoradas no semaforo (espacamento
de 1,5 m => 6.667 m lineares por hectare):
    280 m/ha  = 4,2%  (meta)
    500 m/ha  = 7,5%  (atencao)
  1.000 m/ha  = 15%   (critico)

Uso: python -u C:\\temp\\gerar_relatorio_falhas.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import subprocess
import time
import arcpy
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Polygon as MplPolygon

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# O QUE GERAR
# ---------------------------------------------------------------------------

# Sem argumento na linha de comando, roda em LOTE: percorre as fazendas com
# resultado publicado e gera relatorio apenas para as que estao acima da meta.
# Com argumento, gera so aquela fazenda:  python gerar_relatorio_falhas.py 320127
FAZENDA = None

SO_COM_LINHAS = True          # no corpo do relatorio, so talhoes com linhas
GDB_RASTERS = r"D:\GEO\FALHAS\rasters.gdb"

PASTA_SAIDA = r"D:\GEO\FALHAS\relatorios"

# Navegadores que sabem imprimir HTML em PDF por linha de comando. O Edge
# existe em qualquer Windows, entao nao ha o que instalar. O @page do CSS e
# respeitado, e o PDF sai em A4 paisagem com as tres paginas.
NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
FC_ESTACOES = os.path.join(DATASET, "ATVOSPUBLICADOR.ESTACOES_ZEUS")
FC_LINHAS = os.path.join(DATASET, "ATVOSPUBLICADOR.LINHAS_FALHA")
TB_DIARIO = SDE + r"\ATVOSPUBLICADOR.MONITORAMENTO_ESTACAO"
TB_MATRIZ = "ATVOSPUBLICADOR.MATRIZ_PLANTIO"
VIEW = "ATVOSPUBLICADOR.VW_RELATORIO_FALHAS"

META_PCT = 4.2
JANELA_DIAS = 30          # dias apos o plantio no grafico
JANELA_PRE = 30           # dias ANTES do plantio no grafico
VERANICO_MM = 5.0
QUEBRAS = [280, 500, 1000]

# usado para desenhar quando nao ha raster de calor para herdar o SR
EPSG_MAPA = 31982
CORES = ["#2E7D5B", "#D79A26", "#C0392B", "#7B1E14"]
AZUL = "#33657F"

CAMPOS = [
    "CHAVESIG", "UNIDADE", "FAZENDA", "SETOR", "TALHAO", "SAFRA_INVENTARIO",
    "AREA_HA", "VARIEDADE", "AMBIENTE", "DT_PLANTIO",
    "FALHA_PCT", "STATUS_META", "DT_PUBLICACAO_PIMS",
    "QTD_FALHAS", "METROS_FALHA", "TAM_MEDIO_M", "METROS_POR_HA", "TEM_LINHAS",
    "DT_VOO", "PILOTO_VOO", "VANT", "DAP_VOO",
    "DT_PORTE", "PILOTO_PORTE", "DIAS_PORTE_ATE_VOO",
    "UNIDADE_MANEJO", "AGRUP_SOLOS", "TEXTURA_SOLO", "DECLIVIDADE_PCT",
    "FAIXA_DECLIVIDADE", "PERIODO_PLANTIO", "CLASSE_EPOCA", "EPOCA_CONDICAO",
    "EPOCA_CONFIANCA", "EPOCA_ALTERNATIVA",
    "ESTACAO", "ESTACAO_DIST_KM", "CLIMA_CONFIABILIDADE", "CLIMA_DIAS_SEM_DADO",
    "CHUVA_PRE_15", "CHUVA_PRE_30", "CHUVA_PRE_30_UNID",
    "CLIMA_DIAS_SEM_DADO_PRE", "CHUVA_PRE_VS_UNIDADE_PCT",
    "CHUVA_0_15", "CHUVA_0_15_UNID", "CHUVA_0_30", "CHUVA_0_30_UNID",
    "CHUVA_VS_UNIDADE_PCT", "DIAS_COM_CHUVA", "DIAS_CHUVA_UNID",
    "MAIOR_VERANICO", "VERANICO_UNID", "TMAX_MEDIA",
]


def fazendas_acima_da_meta():
    """Media da fazenda PONDERADA pela area, sobre todos os talhoes com
    resultado publicado - nao so os que tem linhas de falha carregadas.
    O criterio de selecao e sobre a fazenda inteira."""
    con = arcpy.ArcSDESQLExecute(SDE)
    sql = ("SELECT COD_FAZENDA, MAX(FAZENDA), "
           "       SUM(FALHA_PCT * AREA_HA) / NULLIF(SUM(AREA_HA), 0), "
           "       SUM(AREA_HA), COUNT(*) "
           "FROM %s "
           "WHERE FALHA_PCT IS NOT NULL AND AREA_HA > 0 "
           "GROUP BY COD_FAZENDA "
           "HAVING SUM(FALHA_PCT * AREA_HA) / NULLIF(SUM(AREA_HA), 0) > %s "
           "ORDER BY 3 DESC" % (VIEW, META_PCT))
    linhas = con.execute(sql)
    if not isinstance(linhas, list):
        return []
    if not isinstance(linhas[0], list):
        linhas = [linhas]
    return [{"cod": str(l[0]).strip(), "nome": (l[1] or "").strip(),
             "media": num(l[2]), "area": num(l[3]), "talhoes": int(l[4])}
            for l in linhas]


def localizar_raster(cod_fazenda):
    """Acha o raster de calor da fazenda na gdb, pelo padrao HEAT_<fazenda>_*.
    Se houver mais de um voo, usa o mais recente pelo sufixo de data."""
    if not arcpy.Exists(GDB_RASTERS):
        return None
    anterior = arcpy.env.workspace
    arcpy.env.workspace = GDB_RASTERS
    try:
        candidatos = arcpy.ListRasters("HEAT_%s_*" % cod_fazenda) or []
        candidatos = [c for c in candidatos if not c.startswith("HEAT_CLS")]
    finally:
        arcpy.env.workspace = anterior
    if not candidatos:
        return None
    return os.path.join(GDB_RASTERS, sorted(candidatos)[-1])


def ler_dados(fazenda, exigir_linhas=None):
    """Le os talhoes da fazenda.

    SO_COM_LINHAS restringe o corpo do relatorio aos talhoes que tem linhas
    de falha carregadas. Como a carga das linhas ainda cobre poucas areas,
    exigir isso deixaria quase toda fazenda sem relatorio - entao, quando
    nao houver nenhum talhao com linhas, o filtro cede e o relatorio sai com
    o percentual do PIMS, sem o detalhamento espacial.
    """
    if exigir_linhas is None:
        exigir_linhas = SO_COM_LINHAS
    con = arcpy.ArcSDESQLExecute(SDE)
    onde = "COD_FAZENDA = '%s'" % fazenda
    if exigir_linhas:
        onde += " AND TEM_LINHAS = 1"
    sql = ("SELECT %s FROM %s WHERE %s ORDER BY CAST(TALHAO AS INT)"
           % (", ".join(CAMPOS), VIEW, onde))
    linhas = con.execute(sql)
    if not isinstance(linhas, list):
        if exigir_linhas:
            print("  sem linhas de falha carregadas - relatorio sem o "
                  "detalhamento espacial")
            return ler_dados(fazenda, exigir_linhas=False)
        raise RuntimeError("nenhum talhao encontrado para a fazenda %s" % fazenda)
    if not isinstance(linhas[0], list):
        linhas = [linhas]
    registros = []
    for l in linhas:
        # campos char do SQL Server vem preenchidos com espacos
        registros.append({k: (v.strip() if isinstance(v, str) else v)
                          for k, v in zip(CAMPOS, l)})
    print("talhoes no relatorio: %d" % len(registros))
    return registros


def num(v):
    """Converte para float o que vier como texto, para as contas do resumo."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, str):
        try:
            return float(v.replace(",", "."))
        except ValueError:
            return 0.0
    return float(v)


def resumo(registros):
    """Indicadores da area. Percentual e media PONDERADA pela area - media
    simples daria peso igual a um talhao de 7 ha e a um de 32 ha."""
    area = sum(num(r["AREA_HA"]) for r in registros)
    falha_pond = (sum(num(r["FALHA_PCT"]) * num(r["AREA_HA"])
                      for r in registros) / area) if area else 0
    metros = sum(num(r["METROS_FALHA"]) for r in registros)
    qtd = sum(num(r["QTD_FALHAS"]) for r in registros)
    acima = sum(num(r["AREA_HA"]) for r in registros
                if num(r["FALHA_PCT"]) > META_PCT)
    return {
        "area": area,
        "falha": falha_pond,
        "metros": metros,
        "qtd": qtd,
        "m_ha": metros / area if area else 0,
        "tam_medio": metros / qtd if qtd else 0,
        "area_acima": acima,
        "pct_acima": 100.0 * acima / area if area else 0,
        "n_talhoes": len(registros),
        "n_criticos": sum(1 for r in registros if r["STATUS_META"] == "Critico"),
    }


def poligonos_utm(chaves, sr_destino):
    """Contorno dos talhoes na projecao do raster."""
    campo = arcpy.AddFieldDelimiters(FC_INVENTARIO, "Chavesig")
    onde = "%s IN (%s)" % (campo, ",".join("'%s'" % c for c in chaves))
    saida = []
    with arcpy.da.SearchCursor(FC_INVENTARIO, ["Chavesig", "TALHAO", "SHAPE@"],
                               onde) as cur:
        for chave, talhao, geom in cur:
            if geom is None:
                continue
            g = geom.projectAs(sr_destino)
            partes = []
            for parte in g:
                pontos = [(p.X, p.Y) for p in parte if p]
                if len(pontos) > 2:
                    partes.append(pontos)
            centro = g.trueCentroid
            saida.append((talhao, partes, (centro.X, centro.Y)))
    return saida


def desenhar_mapa(registros, destino_png, caminho_raster):
    print("desenhando o mapa de calor...")
    raster = arcpy.Raster(caminho_raster)
    sr = arcpy.Describe(caminho_raster).spatialReference
    ext = raster.extent
    arr = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan)
    arr = np.ma.masked_invalid(arr)

    limites = [0] + QUEBRAS + [max(QUEBRAS[-1] * 3, float(np.nanmax(arr)) + 1)]
    cmap = ListedColormap(CORES)
    norm = BoundaryNorm(limites, cmap.N)

    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=160)
    ax.imshow(arr, cmap=cmap, norm=norm, origin="upper",
              extent=(ext.XMin, ext.XMax, ext.YMin, ext.YMax),
              interpolation="nearest")

    por_talhao = {str(r["TALHAO"]): r for r in registros}
    for talhao, partes, centro in poligonos_utm(
            [r["CHAVESIG"] for r in registros], sr):
        for pontos in partes:
            ax.add_patch(MplPolygon(pontos, closed=True, fill=False,
                                    edgecolor="white", linewidth=1.6))
        reg = por_talhao.get(str(talhao))
        rotulo = ("T-%s\n%.1f%%" % (talhao, num(reg["FALHA_PCT"]))
                  if reg and reg["FALHA_PCT"] is not None else "T-%s" % talhao)
        ax.annotate(rotulo, centro, ha="center", va="center", fontsize=8,
                    color="#2F3336",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white",
                              ec="#D8DEE2", lw=0.6, alpha=0.9))

    ax.set_xticks([]); ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_edgecolor("#D8DEE2")
    ax.set_title("Densidade de falhas (m/ha) - escala fixa",
                 fontsize=10, color="#2F3336", pad=8)

    faixas = ["ate %d" % QUEBRAS[0],
              "%d a %d" % (QUEBRAS[0], QUEBRAS[1]),
              "%d a %d" % (QUEBRAS[1], QUEBRAS[2]),
              "acima de %d" % QUEBRAS[2]]
    handles = [plt.Rectangle((0, 0), 1, 1, fc=c) for c in CORES]
    ax.legend(handles, faixas, loc="lower center", ncol=4, frameon=False,
              bbox_to_anchor=(0.5, -0.09), fontsize=8)

    fig.tight_layout()
    fig.savefig(destino_png, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  %s" % destino_png)

    return distribuicao_classes(arr, raster)


def desenhar_linhas(registros, destino_png, sr_destino):
    """Desenha as linhas de falha da Bem Agro sobre o contorno dos talhoes.

    O mapa de calor mostra ONDE a falha se concentra; este mostra a falha
    como ela foi levantada, linha a linha. Sao coisas diferentes: o calor
    generaliza por densidade, este e o dado bruto.
    """
    from matplotlib.collections import LineCollection

    chaves = [r["CHAVESIG"] for r in registros]
    campo = arcpy.AddFieldDelimiters(FC_LINHAS, "CHAVESIG")
    onde = "%s IN (%s)" % (campo, ",".join("'%s'" % c for c in chaves))

    segmentos = []
    with arcpy.da.SearchCursor(FC_LINHAS, ["SHAPE@"], onde) as cur:
        for (geom,) in cur:
            if geom is None:
                continue
            g = geom.projectAs(sr_destino)
            for parte in g:
                pontos = [(p.X, p.Y) for p in parte if p]
                if len(pontos) > 1:
                    segmentos.append(pontos)

    if not segmentos:
        print("  sem linhas de falha para desenhar")
        return False
    print("  %d linhas de falha" % len(segmentos))

    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=160)

    for talhao, partes, centro in poligonos_utm(chaves, sr_destino):
        for pontos in partes:
            ax.add_patch(MplPolygon(pontos, closed=True,
                                    facecolor="#F7F9FA", edgecolor="#8FA9B8",
                                    linewidth=0.9))

    ax.add_collection(LineCollection(segmentos, colors="#C0392B",
                                     linewidths=0.35))

    for talhao, partes, centro in poligonos_utm(chaves, sr_destino):
        ax.annotate("T-%s" % talhao, centro, ha="center", va="center",
                    fontsize=8, color="#2F3336",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white",
                              ec="#D8DEE2", lw=0.6, alpha=0.9))

    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_edgecolor("#D8DEE2")
    ax.set_title("Falhas levantadas pelo VANT", fontsize=10,
                 color="#2F3336", pad=8)

    fig.tight_layout()
    fig.savefig(destino_png, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  %s" % destino_png)
    return True


def distribuicao_classes(arr, raster):
    """Quanto da area esta em cada faixa de densidade.

    Substitui o bloco 'onde esta a falha' do modelo: em vez de descrever
    regioes (terco sul, bordadura), que exigiria classificacao espacial que
    nao temos, mede a proporcao da area em cada faixa - sai do proprio raster.
    """
    validos = arr.compressed() if hasattr(arr, "compressed") else arr[~np.isnan(arr)]
    total = validos.size
    if not total:
        return []
    area_pixel = (raster.meanCellWidth * raster.meanCellHeight) / 10000.0
    limites = [0] + QUEBRAS + [float("inf")]
    rotulos = ["Dentro da meta (ate %d m/ha)" % QUEBRAS[0],
               "Atencao (%d a %d)" % (QUEBRAS[0], QUEBRAS[1]),
               "Critico (%d a %d)" % (QUEBRAS[1], QUEBRAS[2]),
               "Muito critico (acima de %d)" % QUEBRAS[2]]
    saida = []
    for i, rotulo in enumerate(rotulos):
        n = int(((validos >= limites[i]) & (validos < limites[i + 1])).sum())
        saida.append({"rotulo": rotulo, "cor": CORES[i],
                      "pct": 100.0 * n / total, "ha": n * area_pixel})
    return saida


def pic_id_da_estacao(nome):
    campo = arcpy.AddFieldDelimiters(FC_ESTACOES, "NOME")
    with arcpy.da.SearchCursor(FC_ESTACOES, ["PIC_ID"],
                               "%s = \'%s\'" % (campo, nome)) as cur:
        for (pic,) in cur:
            return pic
    return None


def grafico_chuva(nome_estacao, plantio, destino_png):
    """Chuva dia a dia, do periodo ANTES do plantio ate o fim da brotacao.

    A umidade do solo no dia do plantio depende do que choveu antes: solo que
    vinha seco nao germina bem nem com chuva boa depois. Por isso o grafico
    cobre as duas janelas, com o dia do plantio marcado no meio.
    """
    pic = pic_id_da_estacao(nome_estacao)
    if pic is None or plantio is None:
        return False
    inicio = plantio - datetime.timedelta(days=JANELA_PRE)
    fim = plantio + datetime.timedelta(days=JANELA_DIAS)
    # SQL Server nao aceita a sintaxe date 'aaaa-mm-dd' do PostgreSQL
    onde = ("PIC_ID = %s AND DIA >= '%s' AND DIA <= '%s'"
            % (pic, inicio.isoformat(), fim.isoformat()))
    dias, chuvas = [], []
    with arcpy.da.SearchCursor(TB_DIARIO, ["DIA", "CHUVA_TOTAL"], onde) as cur:
        for dia, chuva in sorted(cur):
            dias.append(dia.date() if hasattr(dia, "date") else dia)
            chuvas.append(chuva or 0.0)
    if not dias:
        return False

    fig, ax = plt.subplots(figsize=(7.5, 2.6), dpi=160)

    # antes do plantio em tom mais claro: e contexto, nao a janela critica
    cores = ["#9CB8C7" if d < plantio else AZUL for d in dias]
    ax.bar(dias, chuvas, color=cores, width=0.75)

    ax.axvline(plantio, color="#C0392B", lw=1.4)
    topo = max(chuvas) if chuvas else 1
    ax.annotate("plantio", (plantio, topo), fontsize=7.5, color="#C0392B",
                ha="center", va="bottom", xytext=(0, 3),
                textcoords="offset points", fontweight="bold")

    ax.axhline(VERANICO_MM, color="#7A5410", lw=1, ls="--", alpha=0.7)
    ax.annotate("limiar de veranico (%.0f mm)" % VERANICO_MM,
                (dias[0], VERANICO_MM), fontsize=7, color="#7A5410",
                va="bottom", xytext=(2, 2), textcoords="offset points")
    ax.set_ylabel("mm", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title("Chuva diaria: %d dias antes e %d dias depois do plantio"
                 % (JANELA_PRE, JANELA_DIAS), fontsize=8.5, pad=6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.autofmt_xdate(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(destino_png, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  %s" % destino_png)
    return True


def fmt(v, casas=1, sufixo=""):
    """Numeros podem vir como texto do SQL - converte antes de formatar."""
    if v is None or v == "":
        return "&mdash;"
    if isinstance(v, str):
        try:
            v = float(v.replace(",", "."))
        except ValueError:
            return v
    if isinstance(v, (int, float)):
        return ("%%.%df%s" % (casas, sufixo)) % v
    return str(v)


def data(v):
    """O ArcSDESQLExecute devolve data como texto, o cursor do arcpy devolve
    objeto. Aceita os dois."""
    if not v:
        return "&mdash;"
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y")
    texto = str(v).strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%d", "%d/%m/%Y",
                    "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(texto, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto[:10]


def to_date(v):
    """Mesma coisa, devolvendo objeto date - usado nas contas de janela."""
    if not v:
        return None
    if hasattr(v, "date"):
        return v.date()
    texto = str(v).strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d",
                    "%d/%m/%Y", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S",
                    "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def comparativo(rotulo, valor, media, unidade="", invertido=False):
    """Barra com o valor da area e o traco da media da unidade."""
    if valor is None:
        return ""
    valor, ref = num(valor), num(media)
    maximo = max(valor, ref) * 1.35 or 1
    largura = 100.0 * valor / maximo
    marca = 100.0 * ref / maximo
    pior = (valor > ref) if invertido else (valor < ref)
    cor = "#C0392B" if pior else "#2E7D5B"
    return """
    <div class="comp">
      <div class="top"><span>%s</span><span class="v" style="color:%s">%s%s</span></div>
      <div class="barra"><div class="preenche" style="width:%.1f%%;background:%s"></div>
        <div class="marca" style="left:%.1f%%"></div></div>
      <div class="leg">Media da unidade: %s%s</div>
    </div>""" % (rotulo, cor, fmt(valor), unidade, largura, cor, marca,
                 fmt(media), unidade)


def vazio(v):
    """O SQL devolve nulo como None ou como texto vazio, conforme o driver."""
    return v is None or (isinstance(v, str) and not v.strip())


def sem_registro(rotulo):
    """Linha no lugar da barra quando a estacao nao registrou a janela.

    Sem ela o indicador simplesmente sumiria do bloco, e quem le nao saberia
    se a janela foi ignorada ou se nao ha dado."""
    return """
    <div class="comp">
      <div class="top"><span>%s</span><span class="v" style="color:#6B7378">sem registro</span></div>
      <div class="leg">A estacao nao registrou nenhum dia desta janela.</div>
    </div>""" % rotulo


def leitura_clima(r0):
    """Os dois primeiros paragrafos da leitura da pagina 3.

    Janela sem registro ganha frase propria: formatado no meio da frase, o
    valor ausente virava "&mdash; mm", e antes disso a carga gravava 0,0 e o
    relatorio afirmava que nao tinha chovido."""
    # sem nenhuma das duas janelas o talhao nem tem estacao com serie: dizer
    # que "a estacao nao registrou" suporia uma estacao que nao existe
    if vazio(r0.get("CHUVA_PRE_30")) and vazio(r0.get("CHUVA_0_30")):
        return "<p>Nao ha dado climatico para a janela de plantio desta area.</p>"

    if vazio(r0.get("CHUVA_PRE_30")):
        antes = ("A estacao nao tem registro dos 30 dias que antecederam o "
                 "plantio: nao ha como dizer em que umidade o solo estava "
                 "quando foi plantado.")
    else:
        antes = ("Nos 30 dias que antecederam o plantio a area recebeu "
                 "<b>%s mm</b>, contra %s mm da media da unidade &mdash; e a "
                 "condicao de umidade em que o solo estava quando foi plantado."
                 % (fmt(r0.get("CHUVA_PRE_30")),
                    fmt(r0.get("CHUVA_PRE_30_UNID"))))

    if vazio(r0.get("CHUVA_0_30")):
        depois = "Nao ha dado climatico para os 30 dias apos o plantio."
    else:
        depois = ("Nos 30 dias seguintes recebeu <b>%s%%</b> da chuva media da "
                  "unidade, com temperatura maxima media de %s &deg;C."
                  % (fmt(r0.get("CHUVA_VS_UNIDADE_PCT"), 0),
                     fmt(r0.get("TMAX_MEDIA"))))

    return ('<p>%s</p>\n          <p style="margin-top:8px">%s</p>'
            % (antes, depois))


CORES_EPOCA = {
    "Favoravel": "#2E7D5B",
    "Favorável": "#2E7D5B",
    "Aceitavel": "#7A5410",
    "Aceitável": "#7A5410",
    "Restritivo": "#C0392B",
}


def bloco_epoca(r0):
    """A epoca de plantio ganha bloco proprio, com a faixa do ano ao lado.

    Como campo de texto no meio de doze outros, ela passava despercebida -
    justamente o indicador que aponta causa fora do clima.
    """
    classe = (r0.get("CLASSE_EPOCA") or "").strip()
    if not classe:
        return ""

    cor = cor_da_epoca(classe)
    faixa = faixa_do_ano(r0.get("UNIDADE_MANEJO"),
                         r0.get("FAIXA_DECLIVIDADE"),
                         r0.get("PERIODO_PLANTIO"))

    return """
    <div class="eyebrow" style="margin-top:14px">Epoca de plantio &mdash; Matriz de Plantio</div>
    <div class="epoca-bloco" style="border-left-color:%s">
      <div class="epoca-esq">
        <div class="epoca-classe" style="color:%s">%s</div>
        <div class="epoca-sub">plantio em <b>%s</b><br>UM %s &middot; declividade %s</div>
      </div>
      <div class="epoca-dir">%s%s</div>
    </div>""" % (
        cor, cor, classe,
        r0.get("PERIODO_PLANTIO") or "&mdash;",
        r0.get("UNIDADE_MANEJO") if r0.get("UNIDADE_MANEJO") is not None else "&mdash;",
        r0.get("FAIXA_DECLIVIDADE") or "&mdash;",
        faixa, nota_da_epoca(r0))


def cor_da_epoca(classe):
    """Favoravel com irrigacao fica neutro: e plantio de inverno, pratica
    deliberada, nao desvio. Pintar de vermelho passaria a ideia errada."""
    return CORES_EPOCA.get((classe or "").strip(), "#2F3336")


def nota_da_epoca(r0):
    """A matriz classifica supondo manejo de cobertura. Sem dizer isso, a
    classe afirma mais do que a matriz diz."""
    partes = []
    periodo = r0.get("PERIODO_PLANTIO")
    classe = (r0.get("CLASSE_EPOCA") or "").strip()
    if not classe:
        return ""

    if r0.get("EPOCA_CONDICAO"):
        partes.append("A classificacao pressupoe: %s." % r0["EPOCA_CONDICAO"])
    if classe.startswith("Favoravel com") or classe.startswith("Favorável com"):
        partes.append("Plantio de inverno: a matriz o considera adequado "
                      "quando ha irrigacao ou salvamento.")
    if (r0.get("EPOCA_CONFIANCA") or "") == "Ressalva":
        motivo = r0.get("EPOCA_MOTIVO_RESSALVA") or "classificacao incerta"
        alt = r0.get("EPOCA_ALTERNATIVA")
        texto = motivo
        if alt:
            texto += " (seria %s)" % alt
        partes.append("<b>Ressalva:</b> %s." % texto)

    return '<div class="epoca">%s</div>' % " ".join(partes)


MESES_ORDEM = ["Jan 1Q", "Jan 2Q", "Fev 1Q", "Fev 2Q", "Mar 1Q", "Mar 2Q",
               "Abr 1Q", "Abr 2Q", "Mai 1Q", "Mai 2Q", "Jun", "Jul", "Ago",
               "Set", "Out", "Nov", "Dez"]

CORES_FAIXA = {
    "Favoravel": "#2E7D5B", "Favorável": "#2E7D5B",
    "Aceitavel": "#D79A26", "Aceitável": "#D79A26",
    "Restritivo": "#C0392B",
    "Favoravel com irrigacao": "#7FA9C4",
    "Favorável com irrigação": "#7FA9C4",
}


def faixa_do_ano(unidade, faixa_decliv, periodo_plantio):
    """Desenha o ano inteiro conforme a matriz, com o plantio marcado.

    Um campo de texto dizendo "Restritivo" passa despercebido no meio de doze
    outros. A faixa mostra a janela recomendada inteira e onde o plantio caiu
    dentro dela - a leitura e imediata.
    """
    if unidade is None or not faixa_decliv:
        return ""

    con = arcpy.ArcSDESQLExecute(SDE)
    sql = ("SELECT PERIODO, CLASSE_EPOCA FROM %s "
           "WHERE NUM_MANEJO = %d AND FAIXA_DECLIV = '%s'"
           % (TB_MATRIZ, int(unidade), faixa_decliv))
    linhas = con.execute(sql)
    if not isinstance(linhas, list):
        return ""
    if not isinstance(linhas[0], list):
        linhas = [linhas]
    classes = {(l[0] or "").strip(): (l[1] or "").strip() for l in linhas}

    celulas, rotulos = "", ""
    for periodo in MESES_ORDEM:
        classe = classes.get(periodo, "")
        cor = CORES_FAIXA.get(classe, "#EDF1F3")
        atual = periodo == (periodo_plantio or "").strip()
        borda = "border:2px solid #22475A;" if atual else ""
        celulas += ('<div class="cel" style="background:%s;%s" title="%s: %s">'
                    '</div>' % (cor, borda, periodo, classe or "sem regra"))
        marca = "&#9650;" if atual else "&nbsp;"
        rotulos += '<div class="cel-rot">%s</div>' % marca

    nomes = ""
    for nome, span in [("Jan", 2), ("Fev", 2), ("Mar", 2), ("Abr", 2),
                       ("Mai", 2), ("Jun", 1), ("Jul", 1), ("Ago", 1),
                       ("Set", 1), ("Out", 1), ("Nov", 1), ("Dez", 1)]:
        nomes += ('<div class="cel-mes" style="grid-column:span %d">%s</div>'
                  % (span, nome))

    legenda = ""
    for classe in ["Favoravel", "Aceitavel", "Restritivo",
                   "Favoravel com irrigacao"]:
        legenda += ('<span class="leg-item"><i style="background:%s"></i>%s'
                    '</span>' % (CORES_FAIXA[classe], classe))

    return ("""
    <div class="ano">
      <div class="ano-grade">%s</div>
      <div class="ano-grade">%s</div>
      <div class="ano-grade ano-meses">%s</div>
      <div class="ano-leg">%s</div>
    </div>""" % (celulas, rotulos, nomes, legenda))


def linha_do_tempo(r0):
    marcos = [("Plantio", data(r0["DT_PLANTIO"])),
              ("Porte aprovado", data(r0["DT_PORTE"])),
              ("Voo de falhas", data(r0["DT_VOO"])),
              ("Resultado no PIMS", data(r0["DT_PUBLICACAO_PIMS"]))]
    itens = ""
    for rotulo, quando in marcos:
        itens += ('<div class="etapa"><div class="qdo">%s</div>'
                  '<div class="oq">%s</div></div>' % (quando, rotulo))
    return '<div class="linha-tempo">%s</div>' % itens


def bloco_distribuicao(classes):
    if not classes:
        return ""
    linhas = ""
    for c in classes:
        linhas += """
      <div class="faixa">
        <div class="top"><span><i style="background:%s"></i>%s</span>
          <span class="v">%.0f%%</span></div>
        <div class="barra"><div class="preenche" style="width:%.1f%%;background:%s"></div></div>
        <div class="leg">%.1f ha</div>
      </div>""" % (c["cor"], c["rotulo"], c["pct"], c["pct"], c["cor"], c["ha"])
    return linhas


def montar_html(registros, res, nome_png, classes, nome_chuva, nome_linhas):
    r0 = registros[0]
    cores_status = {"Dentro da meta": "t-ok", "Atencao": "t-at",
                    "Critico": "t-cr", "Sem resultado": "t-na"}

    linhas_tabela = ""
    for r in registros:
        linhas_tabela += """
        <tr%s>
          <td>%s</td><td class="num">%s ha</td><td class="num">%s%%</td>
          <td class="num">%s m</td><td class="num">%s</td>
          <td><span class="tag %s">%s</span></td>
        </tr>""" % (
            ' class="destaque"' if r["STATUS_META"] == "Critico" else "",
            r["TALHAO"], fmt(r["AREA_HA"], 2), fmt(r["FALHA_PCT"]),
            fmt(r["TAM_MEDIO_M"], 2), fmt(r["METROS_POR_HA"], 0),
            cores_status.get(r["STATUS_META"], "t-na"), r["STATUS_META"])

    clima = ""
    if r0["CHUVA_0_30"] is not None:
        if vazio(r0.get("CHUVA_PRE_30")):
            antes = sem_registro("Chuva 30 dias ANTES do plantio")
        else:
            antes = comparativo("Chuva 30 dias ANTES do plantio",
                                r0.get("CHUVA_PRE_30"),
                                r0.get("CHUVA_PRE_30_UNID"), " mm")
        clima = (antes
                 + comparativo("Chuva 0-15 DAP", r0["CHUVA_0_15"],
                             r0["CHUVA_0_15_UNID"], " mm")
                 + comparativo("Chuva 0-30 DAP", r0["CHUVA_0_30"],
                               r0["CHUVA_0_30_UNID"], " mm")
                 + comparativo("Dias com chuva", r0["DIAS_COM_CHUVA"],
                               r0["DIAS_CHUVA_UNID"], " dias")
                 + comparativo("Maior veranico", r0["MAIOR_VERANICO"],
                               r0["VERANICO_UNID"], " dias", invertido=True))
    else:
        clima = ('<div class="vazio">Sem dado climatico para a janela de '
                 'plantio desta area.</div>')

    ressalva = ""
    faltas = []
    if r0["CLIMA_DIAS_SEM_DADO"]:
        faltas.append("%d dias apos o plantio" % r0["CLIMA_DIAS_SEM_DADO"])
    # janela anterior inteira sem registro ja tem frase propria na leitura;
    # aqui entra so a falta parcial, que afeta o acumulado
    if r0.get("CLIMA_DIAS_SEM_DADO_PRE") and not vazio(r0.get("CHUVA_PRE_30")):
        faltas.append("%d dias antes" % r0["CLIMA_DIAS_SEM_DADO_PRE"])
    if faltas:
        ressalva = ("<p class='nota'>A estacao nao registrou %s. Os acumulados "
                    "podem estar subestimados.</p>" % " e ".join(faltas))

    contexto = {
        "azul": AZUL, "fazenda": r0["FAZENDA"], "unidade": r0["UNIDADE"],
        "setor": r0["SETOR"], "safra": r0["SAFRA_INVENTARIO"],
        "talhoes": ", ".join(str(r["TALHAO"]) for r in registros),
        "area": fmt(res["area"], 1), "falha": fmt(res["falha"]),
        "tam": fmt(res["tam_medio"], 2), "m_ha": fmt(res["m_ha"], 0),
        "pct_acima": fmt(res["pct_acima"], 0),
        "area_acima": fmt(res["area_acima"], 1),
        "n_criticos": res["n_criticos"], "n_talhoes": res["n_talhoes"],
        "cor_falha": ("#C0392B" if res["falha"] > META_PCT else "#2E7D5B"),
        "meta": META_PCT,
        "variedade": r0["VARIEDADE"] or "&mdash;",
        "ambiente": r0["AMBIENTE"] or "&mdash;",
        "plantio": data(r0["DT_PLANTIO"]), "voo": data(r0["DT_VOO"]),
        "dap": fmt(r0["DAP_VOO"], 0), "piloto_voo": r0["PILOTO_VOO"] or "&mdash;",
        "vant": r0["VANT"] or "&mdash;",
        "pims": data(r0["DT_PUBLICACAO_PIMS"]),
        "porte": data(r0["DT_PORTE"]),
        "piloto_porte": r0["PILOTO_PORTE"] or "&mdash;",
        "dias_porte": fmt(r0["DIAS_PORTE_ATE_VOO"], 0),
        "estacao": r0["ESTACAO"] or "&mdash;",
        "dist": fmt(r0["ESTACAO_DIST_KM"], 1),
        "tmax": fmt(r0["TMAX_MEDIA"]),
        "chuva_pct": fmt(r0["CHUVA_VS_UNIDADE_PCT"], 0),
        "manejo": ("UM %s" % r0["UNIDADE_MANEJO"]
                   if r0.get("UNIDADE_MANEJO") is not None else "&mdash;"),
        "declividade": (("%s%%  (%s)" % (fmt(r0.get("DECLIVIDADE_PCT")),
                                         r0.get("FAIXA_DECLIVIDADE")))
                        if r0.get("DECLIVIDADE_PCT") is not None else "&mdash;"),
        "bloco_epoca": bloco_epoca(r0),
        "leitura": leitura_clima(r0),
        "tabela": linhas_tabela, "clima": clima, "ressalva": ressalva,
        "mapa": ('<img class="mapa" src="%s" alt="Mapa de calor">' % nome_png)
                if nome_png else
                '<div class="reservado" style="height:36mm">Mapa de calor '
                'indisponivel: as linhas de falha desta area ainda nao foram '
                'carregadas.</div>',
        "mapa_linhas": ('<img class="mapa" src="%s" alt="Falhas levantadas">'
                        % nome_linhas) if nome_linhas else
                       '<div class="reservado" style="height:36mm">Linhas de '
                       'falha nao carregadas para esta area.</div>',
        "linha_tempo": linha_do_tempo(r0),
        "bloco_onde": ("""
        <div class="eyebrow" style="margin-top:14px">Onde esta a falha</div>
        %s
        <p style="font-size:9px;color:#6B7378">
          Proporcao da area em cada faixa de densidade, medida sobre o raster.</p>"""
                       % bloco_distribuicao(classes)) if classes else "",
        "grafico_chuva": ('<img class="mapa" src="%s" alt="Chuva diaria">'
                          % nome_chuva) if nome_chuva else
                         '<div class="vazio">Sem serie diaria para a janela.</div>',
        "gerado": datetime.datetime.now().strftime("%d/%m/%Y as %H:%M"),
    }
    return TEMPLATE % contexto


TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatorio de falhas - %(fazenda)s</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#EDF0F2;font-family:Tahoma,Verdana,sans-serif;color:#2F3336;font-size:11px;line-height:1.45}
.page{width:297mm;min-height:210mm;background:#fff;margin:0 auto 16px;position:relative;box-shadow:0 1px 4px rgba(0,0,0,.14)}
.cab{background:%(azul)s;color:#fff;padding:11px 18px;display:flex;justify-content:space-between;align-items:center}
.cab .marca{font-size:9px;letter-spacing:2.4px;color:#B7CEDB}
.cab h1{font-size:17px}
.cab .dir{text-align:right;font-size:10px;color:#CFE0E9}
.cab .dir b{color:#fff;font-size:12px}
.corpo{padding:14px 18px}
.eyebrow{font-size:9px;letter-spacing:2px;text-transform:uppercase;color:%(azul)s;font-weight:bold;padding-bottom:4px;border-bottom:2px solid #E7EEF2;margin:0 0 9px}
.grid{display:grid;gap:12px}.g2{grid-template-columns:1fr 1fr}.g4{grid-template-columns:repeat(4,1fr)}
.dados{display:grid;grid-template-columns:repeat(4,1fr);gap:7px 14px}
.rot{font-size:9px;color:#6B7378;text-transform:uppercase}
.val{font-size:12px;font-weight:bold}
.kpi{border:1px solid #D8DEE2;border-radius:3px;padding:9px 11px;background:#F7F9FA}
.kpi .num{font-size:26px;font-weight:bold;line-height:1}
.kpi .sub{font-size:9px;color:#6B7378;margin-top:3px}
table{width:100%%;border-collapse:collapse;font-size:10.5px}
th{background:#E7EEF2;color:#22475A;text-align:left;font-size:9px;text-transform:uppercase;padding:5px 7px}
td{padding:5px 7px;border-bottom:1px solid #EDF1F3}
td.num,th.num{text-align:right}
tr.destaque td{background:#FDF3F1}
.tag{display:inline-block;font-size:9px;font-weight:bold;padding:2px 8px;border-radius:9px;text-transform:uppercase}
.t-ok{background:#E4F0EA;color:#1F5B41}.t-at{background:#FAEEDA;color:#7A5410}
.t-cr{background:#F8E4E1;color:#8C2419}.t-na{background:#EDF1F3;color:#6B7378}
.comp{margin-bottom:10px}
.comp .top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px}
.comp .v{font-size:13px;font-weight:bold}
.comp .barra{position:relative;height:8px;background:#EDF1F3;border-radius:2px}
.comp .preenche{position:absolute;top:0;left:0;height:8px;border-radius:2px}
.comp .marca{position:absolute;top:-2px;width:2px;height:12px;background:#22475A}
.comp .leg{font-size:9px;color:#6B7378;margin-top:2px}
.caixa{border:1px solid #D8DEE2;border-radius:3px;padding:10px 12px}
.mapa{width:100%%;border:1px solid #D8DEE2;border-radius:3px;display:block}
/* imagem nao pode ser quebrada entre paginas: sem limite de altura o
   navegador empurra a figura inteira para a pagina seguinte */
img.mapa{max-height:56mm;object-fit:contain;break-inside:avoid;page-break-inside:avoid}
.grid > div{break-inside:avoid;page-break-inside:avoid}
.corpo{break-inside:avoid}
.faixa,.comp,.kpi,table{break-inside:avoid;page-break-inside:avoid}
.chuva img{max-height:52mm}
.epoca{font-size:9px;color:#6B7378;margin-top:6px;line-height:1.5}
.epoca-bloco{display:grid;grid-template-columns:46mm 1fr;gap:14px;border:1px solid #D8DEE2;border-left:4px solid #D8DEE2;border-radius:0;padding:9px 12px;align-items:center}
.epoca-classe{font-size:19px;font-weight:bold;line-height:1.1}
.epoca-sub{font-size:9.5px;color:#6B7378;margin-top:4px}
.ano-grade{display:grid;grid-template-columns:repeat(17,1fr);gap:2px}
.cel{height:15px;border-radius:2px}
.cel-rot{text-align:center;font-size:8px;color:#22475A;line-height:1}
.ano-meses{margin-top:2px}
.cel-mes{text-align:center;font-size:8px;color:#6B7378}
.ano-leg{margin-top:5px;font-size:8.5px;color:#6B7378}
.leg-item{margin-right:12px;white-space:nowrap}
.leg-item i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px}
.nota{font-size:10px;color:#7A5410;background:#FFF8E1;border-left:3px solid #D79A26;padding:7px 10px;margin-top:10px}
.vazio{font-size:11px;color:#6B7378;background:#F7F9FA;padding:12px;border-radius:3px}
.reservado{border:1px dashed #B9C4CB;border-radius:3px;background:repeating-linear-gradient(45deg,#F4F7F8,#F4F7F8 9px,#EDF1F3 9px,#EDF1F3 18px);display:flex;align-items:center;justify-content:center;text-align:center;color:#7C8991;font-size:10px;height:52mm}
.linha-tempo{display:flex;margin-top:4px}
.etapa{flex:1;position:relative;padding-top:16px;text-align:center}
.etapa:before{content:"";position:absolute;top:5px;left:0;right:0;height:2px;background:#E7EEF2}
.etapa:after{content:"";position:absolute;top:1px;left:50%%;transform:translateX(-50%%);width:10px;height:10px;border-radius:50%%;background:#fff;border:2px solid %(azul)s}
.etapa .qdo{font-size:9px;color:#6B7378}
.etapa .oq{font-size:10px;font-weight:bold}
.faixa{margin-bottom:8px}
.faixa .top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;font-size:10.5px}
.faixa i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.faixa .v{font-weight:bold}
.faixa .barra{height:7px;background:#EDF1F3;border-radius:2px}
.faixa .preenche{height:7px;border-radius:2px}
.faixa .leg{font-size:9px;color:#6B7378;margin-top:2px}
.rod{border-top:1px solid #D8DEE2;margin-top:14px;padding:6px 18px;font-size:9px;color:#6B7378;display:flex;justify-content:space-between}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;page-break-after:always}@page{size:A4 landscape;margin:0}}
</style></head><body>

<section class="page">
  <div class="cab">
    <div><div class="marca">ATVOS &middot; GEOTECNOLOGIA</div><h1>Relatorio de falhas de plantio</h1></div>
    <div class="dir"><b>Fazenda %(fazenda)s &middot; talhoes %(talhoes)s</b><br>
      Unidade %(unidade)s &middot; setor %(setor)s &middot; safra %(safra)s</div>
  </div>
  <div class="corpo">
    <div class="grid" style="grid-template-columns:1fr 105mm;margin-bottom:14px">
      <div>
    <div class="eyebrow">Identificacao</div>
    <div class="dados" style="grid-template-columns:repeat(3,1fr)">
      <div><div class="rot">Area analisada</div><div class="val">%(area)s ha</div></div>
      <div><div class="rot">Talhoes</div><div class="val">%(n_talhoes)s</div></div>
      <div><div class="rot">Variedade</div><div class="val">%(variedade)s</div></div>
      <div><div class="rot">Ambiente</div><div class="val">%(ambiente)s</div></div>
      <div><div class="rot">Data de plantio</div><div class="val">%(plantio)s</div></div>
      <div><div class="rot">Data do voo</div><div class="val">%(voo)s</div></div>
      <div><div class="rot">Dias apos o plantio</div><div class="val">%(dap)s DAP</div></div>
      <div><div class="rot">Publicado no PIMS</div><div class="val">%(pims)s</div></div>
      <div><div class="rot">Piloto do voo</div><div class="val">%(piloto_voo)s</div></div>
      <div><div class="rot">Aeronave</div><div class="val">%(vant)s</div></div>
      <div><div class="rot">Porte aprovado em</div><div class="val">%(porte)s</div></div>
      <div><div class="rot">Porte ate o voo</div><div class="val">%(dias_porte)s dias</div></div>
      <div><div class="rot">Unidade de manejo</div><div class="val">%(manejo)s</div></div>
      <div><div class="rot">Declividade</div><div class="val">%(declividade)s</div></div>
    </div>
      </div>
      <div>
        <div class="eyebrow">Ortomosaico</div>
        <div class="reservado">Espaco reservado para o ortomosaico do voo<br>
          <span style="font-size:9px">a definir: recorte da area em baixa resolucao</span></div>
      </div>
    </div>

    <div class="eyebrow">Resultado</div>
    <div class="grid g4">
      <div class="kpi"><div class="rot">Falhas na area</div>
        <div class="num" style="color:%(cor_falha)s">%(falha)s%%</div>
        <div class="sub">Fonte PIMS &middot; meta %(meta)s%%</div></div>
      <div class="kpi"><div class="rot">Tamanho medio</div>
        <div class="num">%(tam)s m</div><div class="sub">Media ponderada</div></div>
      <div class="kpi"><div class="rot">Metros por hectare</div>
        <div class="num">%(m_ha)s</div><div class="sub">Densidade de falha</div></div>
      <div class="kpi"><div class="rot">Area acima da meta</div>
        <div class="num">%(pct_acima)s%%</div>
        <div class="sub">%(area_acima)s ha &middot; %(n_criticos)s talhoes criticos</div></div>
    </div>

    %(bloco_epoca)s

    <div class="eyebrow" style="margin-top:14px">Linha do tempo da area</div>
    %(linha_tempo)s
  </div>
  <div class="rod"><span>Geotecnologia &middot; Cartografia e Operacao VANT</span><span>Pagina 1 de 3</span></div>
</section>

<section class="page">
  <div class="cab">
    <div><div class="marca">ATVOS &middot; GEOTECNOLOGIA</div><h1>Distribuicao das falhas</h1></div>
    <div class="dir"><b>Fazenda %(fazenda)s</b><br>voo de %(voo)s</div>
  </div>
  <div class="corpo">
    <div class="grid g2">
      <div>
        <div class="eyebrow">Falhas levantadas</div>
        %(mapa_linhas)s
        <p style="font-size:9px;color:#6B7378;margin:5px 0 10px">
          Cada linha vermelha e uma falha medida pelo VANT, como veio da
          Bem Agro. E o dado bruto do levantamento.</p>

        <div class="eyebrow">Mapa de calor</div>
        %(mapa)s
        <p style="font-size:9px;color:#6B7378;margin-top:5px">
          A mesma falha vista por densidade, em metros por hectare. Escala
          fixa: comparavel entre areas e safras.</p>
      </div>
      <div>
        <div class="eyebrow">Resultado por talhao</div>
        <table>
          <thead><tr><th>Talhao</th><th class="num">Area</th><th class="num">Falhas</th>
            <th class="num">Tam. medio</th><th class="num">m/ha</th><th>Situacao</th></tr></thead>
          <tbody>%(tabela)s</tbody>
        </table>
        <p style="font-size:9px;color:#6B7378;margin-top:8px">
          O percentual e o publicado no PIMS. Os metros, o tamanho medio e o
          mapa vem das linhas de falha e servem ao diagnostico espacial.</p>

        %(bloco_onde)s
      </div>
    </div>
  </div>
  <div class="rod"><span>Percentual oficial conforme PIMS</span><span>Pagina 2 de 3</span></div>
</section>

<section class="page">
  <div class="cab">
    <div><div class="marca">ATVOS &middot; GEOTECNOLOGIA</div><h1>Diagnostico climatico</h1></div>
    <div class="dir"><b>Estacao %(estacao)s</b><br>a %(dist)s km &middot; janela 0-30 DAP</div>
  </div>
  <div class="corpo">
    <div class="grid g2">
      <div>
        <div class="eyebrow">Area x media da unidade</div>
        %(clima)s
      </div>
      <div>
        <div class="eyebrow">Chuva diaria apos o plantio</div>
        <div class="chuva">%(grafico_chuva)s</div>
        <div class="eyebrow" style="margin-top:14px">Leitura</div>
        <div class="caixa">
          %(leitura)s
          <p style="margin-top:8px">O percentual de falhas ficou em
          <b>%(falha)s%%</b>, contra meta de %(meta)s%%. Compare os dois: chuva
          proxima da media com falha alta aponta para causa operacional,
          nao climatica.</p>
        </div>
        %(ressalva)s
      </div>
    </div>
  </div>
  <div class="rod"><span>Estacoes meteorologicas Atvos &middot; gerado em %(gerado)s</span><span>Pagina 3 de 3</span></div>
</section>
</body></html>
"""


def gerar_pdf(caminho_html):
    """Imprime o HTML em PDF usando o navegador em modo headless."""
    navegador = next((n for n in NAVEGADORES if os.path.isfile(n)), None)
    if not navegador:
        print("AVISO: Edge/Chrome nao encontrado - PDF nao gerado.")
        print("       O HTML pode ser impresso manualmente com Ctrl+P.")
        return None

    destino = os.path.splitext(caminho_html)[0] + ".pdf"
    if os.path.exists(destino):
        os.remove(destino)

    for modo in ("--headless=new", "--headless"):
        comando = [
            navegador, modo, "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer",
            "--print-to-pdf=%s" % destino,
            "file:///%s" % caminho_html.replace("\\", "/"),
        ]
        try:
            subprocess.run(comando, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            print("AVISO: o navegador demorou demais - PDF nao gerado")
            return None
        # o navegador escreve o arquivo depois de encerrar; espera um pouco
        for _ in range(10):
            if os.path.exists(destino) and os.path.getsize(destino) > 0:
                print("  %s" % destino)
                return destino
            time.sleep(0.5)

    print("AVISO: o navegador nao produziu o PDF")
    return None


def gerar_uma(fazenda):
    registros = ler_dados(fazenda)
    res = resumo(registros)

    pasta = os.path.join(PASTA_SAIDA, "%s_%s" % (
        fazenda, datetime.date.today().strftime("%Y%m%d")))
    if not os.path.isdir(pasta):
        os.makedirs(pasta)

    raster = localizar_raster(fazenda)
    nome_png, classes, sr_mapa = None, [], None
    if raster:
        nome_png = "mapa_calor_%s.png" % fazenda
        classes = desenhar_mapa(registros, os.path.join(pasta, nome_png), raster)
        sr_mapa = arcpy.Describe(raster).spatialReference
    else:
        print("  sem raster de calor para a fazenda %s - relatorio sem mapa"
              % fazenda)

    nome_linhas = "linhas_falha_%s.png" % fazenda
    if sr_mapa is None:
        sr_mapa = arcpy.SpatialReference(EPSG_MAPA)
    if not desenhar_linhas(registros, os.path.join(pasta, nome_linhas), sr_mapa):
        nome_linhas = None

    nome_chuva = "chuva_diaria_%s.png" % fazenda
    r0 = registros[0]
    if not grafico_chuva(r0["ESTACAO"], to_date(r0["DT_PLANTIO"]),
                         os.path.join(pasta, nome_chuva)):
        nome_chuva = None

    html = montar_html(registros, res, nome_png, classes, nome_chuva,
                       nome_linhas)
    destino = os.path.join(pasta, "relatorio_falhas_%s.html" % fazenda)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)

    print("gerando o PDF...")
    pdf = gerar_pdf(destino)

    print("\n=== resumo da area ===")
    print("  talhoes        : %d (%d criticos)" % (res["n_talhoes"], res["n_criticos"]))
    print("  area           : %.1f ha" % res["area"])
    print("  falhas         : %.2f%% (ponderada pela area)" % res["falha"])
    print("  metros/ha      : %.0f" % res["m_ha"])
    print("  tamanho medio  : %.2f m" % res["tam_medio"])
    print("  HTML: %s" % destino)
    if pdf:
        print("  PDF : %s" % pdf)
    return destino


def gerar_lote():
    """Gera relatorio apenas para as fazendas acima da meta."""
    fazendas = fazendas_acima_da_meta()
    print("fazendas acima da meta de %.1f%%: %d\n" % (META_PCT, len(fazendas)))
    if not fazendas:
        print("nenhuma fazenda acima da meta - nada a gerar")
        return

    print("%-10s %-28s %8s %9s %8s" %
          ("FAZENDA", "NOME", "FALHA %", "AREA HA", "TALHOES"))
    for f in fazendas:
        print("%-10s %-28s %7.2f%% %9.1f %8d"
              % (f["cod"], f["nome"][:28], f["media"], f["area"], f["talhoes"]))

    gerados, falhas = 0, []
    for f in fazendas:
        print("\n--- %s (%s) ---" % (f["cod"], f["nome"]))
        try:
            gerar_uma(f["cod"])
            gerados += 1
        except Exception as erro:
            print("  ERRO: %s" % erro)
            falhas.append(f["cod"])

    print("\n=== lote concluido ===")
    print("  relatorios gerados: %d de %d" % (gerados, len(fazendas)))
    if falhas:
        print("  falharam: %s" % ", ".join(falhas))


if __name__ == "__main__":
    import sys
    alvo = FAZENDA or (sys.argv[1] if len(sys.argv) > 1 else None)
    if alvo:
        print("gerando relatorio da fazenda %s" % alvo)
        gerar_uma(alvo)
    else:
        gerar_lote()