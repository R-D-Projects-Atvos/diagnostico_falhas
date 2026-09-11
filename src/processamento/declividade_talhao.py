# -*- coding: utf-8 -*-
"""
Calcula a declividade media de cada talhao e classifica na faixa da Matriz
de Plantio.

O modelo de elevacao vem do Copernicus DEM GLO-30, do bucket publico da AWS
(https://copernicus-dem-30m.s3.amazonaws.com). Sao GeoTIFF em tiles de 1x1
grau, acesso livre, sem credencial.

Por que Copernicus e nao SRTM: mesma resolucao de 30 m, mas erro vertical de
2 a 4 m contra 6 a 16 m do SRTM, e imageamento de 2011-2015 contra 2000. Na
faixa que a matriz mais discrimina - a fronteira de 2,5% - o SRTM opera no
limite do proprio ruido.

Ressalva que fica registrada no resultado: o Copernicus e modelo de
SUPERFICIE, inclui vegetacao. Cana alta no momento do imageamento vira
relevo. Por isso o script suaviza o MDE antes do Slope e usa a MEDIANA da
declividade no talhao, nao a media - a mediana ignora os pixels espurios que
a vegetacao gera.

Grava na TALHAO_MANEJO: DECLIV_MEDIANA, DECLIV_MEDIA, DECLIV_DESVIO,
FAIXA_DECLIV (no texto exato da matriz) e DECLIV_CONFIANCA.

Uso: python -u C:\\temp\\declividade_talhao.py

Requer a extensao Spatial Analyst.

Geotecnologia / Cartografia - Atvos
"""

import functools
import math
import os
import urllib.request
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

NOME_CAMADA_SOLOS = "SOLOS_ATVOS"
FC_SOLOS = os.path.join(DATASET, "ATVOSPUBLICADOR." + NOME_CAMADA_SOLOS)
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
FC_DATABASE = os.path.join(DATASET, "ATVOSPUBLICADOR.TALHOES_DATABASE")
TB_MANEJO = SDE + r"\ATVOSPUBLICADOR.TALHAO_MANEJO"

PASTA_DEM = r"D:\GEO\DEM"
GDB_TRABALHO = r"D:\GEO\DEM\declividade.gdb"

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"

# SIRGAS 2000 / UTM 22S - mesmo SR usado no vinculo com a mancha de solos
EPSG_AREA = 31982
CELULA_M = 30

# faixas da Matriz de Plantio - o texto tem que bater exatamente com a matriz
FAIXAS = [(2.5, "< 2,5%"), (5.0, "2,5 a 5%"), (float("inf"), "> 5%")]

# quando a mediana cai a menos disso de uma fronteira, a faixa e incerta
MARGEM_FRONTEIRA = 0.5

CAMPOS_NOVOS = [
    ("DECLIV_MEDIANA", "DOUBLE", None),
    ("DECLIV_MEDIA", "DOUBLE", None),
    ("DECLIV_DESVIO", "DOUBLE", None),
    ("FAIXA_DECLIV", "TEXT", 12),
    ("DECLIV_CONFIANCA", "TEXT", 12),
    ("DECLIV_FONTE", "TEXT", 30),
]


def preparar():
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("extensao Spatial Analyst indisponivel")
    arcpy.CheckOutExtension("Spatial")
    for pasta in (PASTA_DEM,):
        if not os.path.isdir(pasta):
            os.makedirs(pasta)
    if not arcpy.Exists(GDB_TRABALHO):
        arcpy.management.CreateFileGDB(os.path.dirname(GDB_TRABALHO),
                                       os.path.basename(GDB_TRABALHO))


def tiles_necessarios():
    """Descobre os tiles de 1x1 grau que cobrem a area de interesse.

    A area de interesse e a mancha de solos: declividade so serve onde existe
    unidade de manejo para consultar na matriz.
    """
    sr4326 = arcpy.SpatialReference(4326)
    temp = r"memory\solos_geo"
    arcpy.management.Project(FC_SOLOS, temp, sr4326)
    ext = arcpy.Describe(temp).extent
    arcpy.management.Delete(temp)

    print("area de interesse: lon %.3f a %.3f | lat %.3f a %.3f"
          % (ext.XMin, ext.XMax, ext.YMin, ext.YMax))

    tiles = []
    for lat in range(int(math.floor(ext.YMin)), int(math.floor(ext.YMax)) + 1):
        for lon in range(int(math.floor(ext.XMin)), int(math.floor(ext.XMax)) + 1):
            ns = "N%02d" % lat if lat >= 0 else "S%02d" % abs(lat)
            ew = "E%03d" % lon if lon >= 0 else "W%03d" % abs(lon)
            tiles.append("Copernicus_DSM_COG_10_%s_00_%s_00_DEM" % (ns, ew))
    return tiles


def baixar(tiles):
    """Baixa os tiles que ainda nao estao em disco."""
    locais = []
    for nome in tiles:
        destino = os.path.join(PASTA_DEM, nome + ".tif")
        if os.path.isfile(destino) and os.path.getsize(destino) > 0:
            print("  ja em disco: %s" % nome)
            locais.append(destino)
            continue

        url = "%s/%s/%s.tif" % (BUCKET, nome, nome)
        print("  baixando %s ..." % nome)
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, \
                 open(destino, "wb") as saida:
                saida.write(resp.read())
            locais.append(destino)
        except Exception as erro:
            # tile inexistente (oceano) e normal; falha de rede nao e
            if os.path.exists(destino):
                os.remove(destino)
            print("     nao baixou: %s" % erro)

    if not locais:
        raise RuntimeError(
            "nenhum tile baixado.\\nSe o erro for de conexao, a rede "
            "corporativa pode estar bloqueando o bucket. Nesse caso baixe os "
            "arquivos manualmente e coloque em %s" % PASTA_DEM)
    return locais


def preparar_raster(tiles_locais):
    """Mosaica, projeta, suaviza e calcula a declividade em porcentagem."""
    from arcpy.sa import FocalStatistics, NbrRectangle, Slope

    sr = arcpy.SpatialReference(EPSG_AREA)

    print("mosaicando %d tile(s)..." % len(tiles_locais))
    mosaico = os.path.join(GDB_TRABALHO, "DEM_MOSAICO")
    arcpy.management.MosaicToNewRaster(
        tiles_locais, GDB_TRABALHO, "DEM_MOSAICO",
        pixel_type="32_BIT_FLOAT", number_of_bands=1)

    print("projetando para UTM (%d m)..." % CELULA_M)
    projetado = os.path.join(GDB_TRABALHO, "DEM_UTM")
    arcpy.management.ProjectRaster(mosaico, projetado, sr, "BILINEAR", CELULA_M)

    # suavizacao antes do slope: reduz o ruido pixel a pixel, que numa
    # encosta de 2,5% e da mesma ordem do sinal que queremos medir
    print("suavizando (media 3x3)...")
    suave = FocalStatistics(projetado, NbrRectangle(3, 3, "CELL"), "MEAN")
    suave.save(os.path.join(GDB_TRABALHO, "DEM_SUAVE"))

    print("calculando a declividade em porcentagem...")
    decliv = Slope(suave, "PERCENT_RISE")
    caminho = os.path.join(GDB_TRABALHO, "DECLIVIDADE_PCT")
    decliv.save(caminho)
    return caminho


def zonas():
    """Talhoes como zona, sem chave repetida.

    Inventario e database podem ter o mesmo Chavesig; o zonal statistics
    exige zona unica, entao dissolve por chave antes.
    """
    sr = arcpy.SpatialReference(EPSG_AREA)
    partes = []
    for fc, marca in ((FC_INVENTARIO, "inv"), (FC_DATABASE, "db")):
        if not arcpy.Exists(fc):
            continue
        destino = r"memory\z_%s" % marca
        arcpy.management.Project(fc, destino, sr)
        partes.append(destino)

    unido = r"memory\zonas_merge"
    if len(partes) == 1:
        arcpy.management.CopyFeatures(partes[0], unido)
    else:
        arcpy.management.Merge(partes, unido)

    print("dissolvendo por Chavesig...")
    dissolvido = os.path.join(GDB_TRABALHO, "ZONAS_TALHAO")
    arcpy.management.Dissolve(unido, dissolvido, ["Chavesig"])
    n = int(arcpy.management.GetCount(dissolvido)[0])
    print("  %d zonas" % n)
    return dissolvido


def estatisticas(raster, zonas_fc):
    from arcpy.sa import ZonalStatisticsAsTable
    print("rodando o zonal statistics...")
    tabela = os.path.join(GDB_TRABALHO, "ZONAL_DECLIV")
    ZonalStatisticsAsTable(zonas_fc, "Chavesig", raster, tabela,
                           "DATA", "ALL")
    campos = {f.name.upper() for f in arcpy.ListFields(tabela)}
    if "MEDIAN" not in campos:
        raise RuntimeError("zonal sem MEDIAN - rode com statistics_type ALL")

    valores = {}
    with arcpy.da.SearchCursor(
            tabela, ["Chavesig", "MEDIAN", "MEAN", "STD"]) as cur:
        for chave, mediana, media, desvio in cur:
            if chave is None:
                continue
            valores[chave.strip()] = (mediana, media, desvio)
    print("  %d talhoes com declividade" % len(valores))
    return valores


def faixa(mediana):
    for limite, rotulo in FAIXAS:
        if mediana < limite:
            return rotulo
    return FAIXAS[-1][1]


def confianca(mediana):
    """Perto da fronteira entre faixas, a classificacao e fragil."""
    for limite, _ in FAIXAS[:-1]:
        if abs(mediana - limite) <= MARGEM_FRONTEIRA:
            return "Ressalva"
    return "Boa"


def gravar(valores):
    presentes = {f.name.upper() for f in arcpy.ListFields(TB_MANEJO)}
    for nome, tipo, tam in CAMPOS_NOVOS:
        if nome.upper() in presentes:
            continue
        print("  acrescentando campo %s" % nome)
        if tam:
            arcpy.management.AddField(TB_MANEJO, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(TB_MANEJO, nome, tipo)

    campos = ["CHAVESIG"] + [c[0] for c in CAMPOS_NOVOS]
    atualizados, sem_dado, ressalvas = 0, 0, 0
    from collections import Counter
    por_faixa = Counter()

    with arcpy.da.UpdateCursor(TB_MANEJO, campos) as cur:
        for linha in cur:
            chave = (linha[0] or "").strip()
            v = valores.get(chave)
            if not v or v[0] is None:
                sem_dado += 1
                continue
            mediana, media, desvio = v
            f = faixa(mediana)
            c = confianca(mediana)
            linha[1] = round(mediana, 2)
            linha[2] = round(media, 2) if media is not None else None
            linha[3] = round(desvio, 2) if desvio is not None else None
            linha[4] = f
            linha[5] = c
            linha[6] = "Copernicus GLO-30"
            cur.updateRow(linha)
            atualizados += 1
            por_faixa[f] += 1
            if c == "Ressalva":
                ressalvas += 1

    return atualizados, sem_dado, ressalvas, por_faixa


def executar():
    preparar()
    tiles = tiles_necessarios()
    print("tiles necessarios: %d" % len(tiles))
    locais = baixar(tiles)
    raster = preparar_raster(locais)
    zonas_fc = zonas()
    valores = estatisticas(raster, zonas_fc)

    if not valores:
        raise RuntimeError("nenhuma estatistica gerada - abortando")

    atualizados, sem_dado, ressalvas, por_faixa = gravar(valores)

    print("\n=== resultado ===")
    print("  talhoes com declividade : %d" % atualizados)
    print("  sem declividade         : %d" % sem_dado)
    print("  perto da fronteira      : %d (%.1f%%)"
          % (ressalvas, 100.0 * ressalvas / atualizados if atualizados else 0))
    print("\n  distribuicao por faixa:")
    for _, rotulo in FAIXAS:
        print("    %-10s %5d" % (rotulo, por_faixa.get(rotulo, 0)))
    print("\ntabela: %s" % TB_MANEJO)
    print("com unidade de manejo + declividade + data de plantio,")
    print("a Matriz de Plantio ja pode ser consultada.")

    arcpy.management.Delete("memory")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    executar()
