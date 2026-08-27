# -*- coding: utf-8 -*-
"""
Gera o mapa de calor das falhas a partir de ATVOSPUBLICADOR.LINHAS_FALHA.

Fluxo:
    LINHAS_FALHA (lote) -> ponto medio de cada falha, pesado por COMP_OFI_M
      -> projeta para UTM 21S (densidade em graus nao significa nada)
      -> Kernel Density -> m de falha por hectare
      -> recorta pelos talhoes do inventario
      -> salva o raster continuo e uma versao classificada com quebras fixas

As quebras sao FIXAS de proposito: escala relativa a cada area impediria
comparar um talhao com outro e entre safras.

Requer: extensao Spatial Analyst.

Geotecnologia / Cartografia - Atvos
"""

import os
import arcpy
from arcpy.sa import KernelDensity, ExtractByMask, Reclassify, RemapRange

arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_FALHAS = os.path.join(DATASET, "ATVOSPUBLICADOR.LINHAS_FALHA")
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")

LOTE = "320127_20260708"

GDB_SAIDA = r"D:\GEO\FALHAS\rasters.gdb"     # file gdb para os rasters

SR_METRICO = arcpy.SpatialReference(31981)   # SIRGAS 2000 / UTM 21S

CELULA_M = 2          # tamanho da celula do raster
RAIO_M = 40           # raio de busca do kernel

# Quebras fixas da escala, em metros de falha por hectare.
QUEBRAS = [300, 600, 900]

# ---------------------------------------------------------------------------


def preparar_saida():
    if not arcpy.Exists(GDB_SAIDA):
        pasta, nome = os.path.split(GDB_SAIDA)
        if not os.path.isdir(pasta):
            os.makedirs(pasta)
        arcpy.management.CreateFileGDB(pasta, nome)


def pontos_medios(onde):
    """Cada falha vira um ponto no seu meio, pesado pelo comprimento oficial.

    Kernel Density sobre linhas ja usa o comprimento da geometria, o que
    impediria usar COMP_OFI_M como peso sem contar o comprimento duas vezes.
    Como a falha media tem ~1,3 m e o raio de busca e de 40 m, representar
    cada falha pelo ponto medio e preciso e deixa o peso explicito.
    """
    saida = r"memory\falhas_pto"
    arcpy.management.CreateFeatureclass(
        "memory", "falhas_pto", "POINT", spatial_reference=SR_METRICO)
    arcpy.management.AddField(saida, "COMP_OFI_M", "DOUBLE")
    arcpy.management.AddField(saida, "CHAVESIG", "TEXT", field_length=20)

    n = 0
    with arcpy.da.InsertCursor(saida, ["SHAPE@", "COMP_OFI_M", "CHAVESIG"]) as ins:
        with arcpy.da.SearchCursor(
                FC_FALHAS, ["SHAPE@", "COMP_OFI_M", "CHAVESIG"], onde,
                spatial_reference=SR_METRICO) as cur:
            for geom, comp, chave in cur:
                if geom is None or not comp:
                    continue
                ins.insertRow([geom.positionAlongLine(0.5, True), comp, chave])
                n += 1
    print("pontos gerados: %d" % n)
    if n == 0:
        raise RuntimeError("nenhuma falha encontrada para o lote %s" % LOTE)
    return saida


def mascara_talhoes(onde):
    """Talhoes do inventario que aparecem neste lote, em UTM."""
    chaves = set()
    with arcpy.da.SearchCursor(FC_FALHAS, ["CHAVESIG"], onde) as cur:
        for (c,) in cur:
            if c:
                chaves.add(c)
    if not chaves:
        raise RuntimeError("nenhum chavesig no lote - carga incompleta?")
    print("talhoes no lote: %s" % ", ".join(sorted(chaves)))

    lista = ",".join("'%s'" % c for c in sorted(chaves))
    campo = arcpy.AddFieldDelimiters(FC_INVENTARIO, "Chavesig")
    camada = "lyr_mask"
    arcpy.management.MakeFeatureLayer(FC_INVENTARIO, camada,
                                      "%s IN (%s)" % (campo, lista))
    mascara = r"memory\mask_utm"
    arcpy.management.Project(camada, mascara, SR_METRICO)
    arcpy.management.Delete(camada)
    return mascara


def gerar():
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst indisponivel")
    arcpy.CheckOutExtension("Spatial")

    preparar_saida()
    onde = "LOTE = '%s'" % LOTE

    pontos = pontos_medios(onde)
    mascara = mascara_talhoes(onde)

    arcpy.env.extent = arcpy.Describe(mascara).extent
    arcpy.env.snapRaster = None

    print("rodando kernel density (celula %d m, raio %d m)..." % (CELULA_M, RAIO_M))
    densidade = KernelDensity(pontos, "COMP_OFI_M", CELULA_M, RAIO_M,
                              "HECTARES", "DENSITIES", "GEODESIC")

    recortado = ExtractByMask(densidade, mascara)

    sufixo = LOTE.replace("-", "_")
    saida_cont = os.path.join(GDB_SAIDA, "HEAT_%s" % sufixo)
    recortado.save(saida_cont)
    print("raster continuo: %s" % saida_cont)

    remap = RemapRange([
        [0, QUEBRAS[0], 1],
        [QUEBRAS[0], QUEBRAS[1], 2],
        [QUEBRAS[1], QUEBRAS[2], 3],
        [QUEBRAS[2], 100000, 4],
    ])
    classificado = Reclassify(recortado, "VALUE", remap, "NODATA")
    saida_cls = os.path.join(GDB_SAIDA, "HEAT_CLS_%s" % sufixo)
    classificado.save(saida_cls)
    print("raster classificado: %s" % saida_cls)
    print("  classe 1: ate %d m/ha" % QUEBRAS[0])
    print("  classe 2: %d a %d" % (QUEBRAS[0], QUEBRAS[1]))
    print("  classe 3: %d a %d" % (QUEBRAS[1], QUEBRAS[2]))
    print("  classe 4: acima de %d" % QUEBRAS[2])

    minimo = arcpy.management.GetRasterProperties(recortado, "MINIMUM")
    maximo = arcpy.management.GetRasterProperties(recortado, "MAXIMUM")
    print("\ndensidade observada: %.0f a %.0f m/ha"
          % (float(minimo.getOutput(0)), float(maximo.getOutput(0))))
    print("(se o maximo passar de %d, reveja as quebras)" % QUEBRAS[-1])

    arcpy.management.Delete(pontos)
    arcpy.management.Delete(mascara)
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    gerar()
