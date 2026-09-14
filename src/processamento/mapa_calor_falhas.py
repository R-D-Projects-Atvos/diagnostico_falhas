# -*- coding: utf-8 -*-
"""
Gera o mapa de calor das falhas de uma fazenda a partir de
ATVOSPUBLICADOR.LINHAS_FALHA e o poe no mosaic dataset
ATVOSPUBLICADOR.MAPA_CALOR_FALHAS.

Fluxo:
    LINHAS_FALHA (talhoes da fazenda) -> ponto medio de cada falha, pesado
      por COMP_OFI_M
      -> projeta para UTM 21S (densidade em graus nao significa nada)
      -> Kernel Density -> m de falha por hectare
      -> recorta pelos talhoes do inventario
      -> HEAT_<fazenda>_<AAAAMMDD_HHMMSS>.tif em D:\\GEO\\FALHAS\\mapa_calor_falhas
      -> entra no mosaic dataset; os rasters anteriores da fazenda saem

O mosaic dataset e uma camada so, com um raster por fazenda: os pixels ficam
no .tif, no disco do servidor, e o SQL Server guarda o indice. Cada geracao
ganha um arquivo com nome novo, em vez de regravar o anterior - no servidor,
uma conta nao consegue sobrescrever arquivo criado por outra.

Usa todas as linhas da fazenda que estao no banco. A carga troca as linhas
talhao a talhao (ADR 0012), entao o mapa e o da fazenda como ela esta agora.

O raster e continuo, em m/ha. As faixas de cor (quebras fixas, ADR 0007) sao
aplicadas pelo gerador do relatorio no desenho.

Roda sozinho depois de cada carga de linhas (carga_linhas_falha.py). A mao:
  propy -u src\\processamento\\mapa_calor_falhas.py 320127

Requer: extensao Spatial Analyst e ArcGIS Pro Standard ou Advanced (mosaic
dataset em geodatabase corporativo).

Geotecnologia / Cartografia - Atvos
"""

import datetime
import os
import sys

import arcpy

arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_FALHAS = os.path.join(DATASET, "ATVOSPUBLICADOR.LINHAS_FALHA")
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")

# os mesmos do gerador do relatorio
NOME_MOSAICO = "MAPA_CALOR_FALHAS"
MOSAICO = os.path.join(SDE, "ATVOSPUBLICADOR." + NOME_MOSAICO)
PASTA_TIF = r"D:\GEO\FALHAS\mapa_calor_falhas"

SR_METRICO = arcpy.SpatialReference(31981)   # SIRGAS 2000 / UTM 21S

CELULA_M = 2          # tamanho da celula do raster
RAIO_M = 40           # raio de busca do kernel

# ---------------------------------------------------------------------------


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
        raise RuntimeError("nenhuma falha carregada para %s" % onde)
    return saida


def mascara_talhoes(onde):
    """Talhoes do inventario que tem linhas, em UTM."""
    chaves = set()
    with arcpy.da.SearchCursor(FC_FALHAS, ["CHAVESIG"], onde) as cur:
        for (c,) in cur:
            if c:
                chaves.add(c)
    print("talhoes com linhas: %d" % len(chaves))

    lista = ",".join("'%s'" % c for c in sorted(chaves))
    campo = arcpy.AddFieldDelimiters(FC_INVENTARIO, "Chavesig")
    camada = "lyr_mask"
    arcpy.management.MakeFeatureLayer(FC_INVENTARIO, camada,
                                      "%s IN (%s)" % (campo, lista))
    mascara = r"memory\mask_utm"
    arcpy.management.Project(camada, mascara, SR_METRICO)
    arcpy.management.Delete(camada)
    return mascara


def criar_mosaico():
    if arcpy.Exists(MOSAICO):
        return
    print("criando o mosaic dataset %s..." % MOSAICO)
    arcpy.management.CreateMosaicDataset(SDE, NOME_MOSAICO, SR_METRICO,
                                         num_bands=1, pixel_type="32_BIT_FLOAT")


def publicar(fazenda, tif):
    """Poe o raster novo no mosaico e so depois tira os anteriores da fazenda:
    o mosaico nunca fica sem o mapa dela."""
    criar_mosaico()
    nome = os.path.splitext(os.path.basename(tif))[0]
    arcpy.management.AddRastersToMosaicDataset(
        MOSAICO, "Raster Dataset", tif,
        update_cellsize_ranges="UPDATE_CELL_SIZES",
        update_boundary="UPDATE_BOUNDARY",
        update_overviews="NO_OVERVIEWS",
        duplicate_items_action="EXCLUDE_DUPLICATES",
        calculate_statistics="CALCULATE_STATISTICS")

    onde = "Name LIKE 'HEAT_%s_%%' AND Name <> '%s'" % (fazenda, nome)
    with arcpy.da.SearchCursor(MOSAICO, ["Name"], onde) as cur:
        anteriores = sorted(n for (n,) in cur)
    if anteriores:
        arcpy.management.RemoveRastersFromMosaicDataset(
            MOSAICO, where_clause=onde, update_boundary="UPDATE_BOUNDARY")
        print("saiu do mosaico: %s" % ", ".join(anteriores))

    # arquivo anterior: apaga se esta conta puder; se for de outra conta, fica
    for arquivo in sorted(os.listdir(PASTA_TIF)):
        base, ext = os.path.splitext(arquivo)
        if ext.lower() == ".tif" and base.startswith("HEAT_%s_" % fazenda) and base != nome:
            try:
                arcpy.management.Delete(os.path.join(PASTA_TIF, arquivo))
            except Exception:
                print("  (arquivo anterior ficou no disco, de outra conta: %s)" % arquivo)


def gerar(fazenda, sufixo=None):
    """Gera o mapa de calor da fazenda, publica no mosaico e devolve o .tif."""
    fazenda = str(fazenda).strip()
    if not (fazenda.isdigit() and len(fazenda) == 6):
        raise ValueError("fazenda invalida: %r" % fazenda)
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst indisponivel nesta conta")
    from arcpy.sa import ExtractByMask, KernelDensity

    sufixo = sufixo or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(PASTA_TIF, exist_ok=True)
    onde = "CHAVESIG LIKE '%s%%'" % fazenda

    arcpy.CheckOutExtension("Spatial")
    try:
        pontos = pontos_medios(onde)
        mascara = mascara_talhoes(onde)

        arcpy.env.extent = arcpy.Describe(mascara).extent
        arcpy.env.snapRaster = None

        print("rodando kernel density (celula %d m, raio %d m)..." % (CELULA_M, RAIO_M))
        densidade = KernelDensity(pontos, "COMP_OFI_M", CELULA_M, RAIO_M,
                                  "HECTARES", "DENSITIES", "GEODESIC")
        recortado = ExtractByMask(densidade, mascara)

        tif = os.path.join(PASTA_TIF, "HEAT_%s_%s.tif" % (fazenda, sufixo))
        recortado.save(tif)
        maximo = arcpy.management.GetRasterProperties(recortado, "MAXIMUM")
        print("raster: %s (densidade maxima %.0f m/ha)"
              % (tif, float(maximo.getOutput(0))))

        arcpy.management.Delete(pontos)
        arcpy.management.Delete(mascara)
    finally:
        # o extent fica no ambiente do processo e cortaria o que vier depois,
        # como o desenho do relatorio
        arcpy.env.extent = None
        arcpy.CheckInExtension("Spatial")

    publicar(fazenda, tif)
    print("mosaico: %s" % MOSAICO)
    return tif


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: propy -u src\\processamento\\mapa_calor_falhas.py <fazenda>")
        sys.exit(1)
    gerar(sys.argv[1])
