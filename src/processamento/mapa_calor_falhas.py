# -*- coding: utf-8 -*-
"""
Gera o mapa de calor das falhas de uma fazenda a partir de
ATVOSPUBLICADOR.LINHAS_FALHA.

Fluxo:
    LINHAS_FALHA (talhoes da fazenda) -> ponto medio de cada falha, pesado
      por COMP_OFI_M
      -> projeta para UTM 21S (densidade em graus nao significa nada)
      -> Kernel Density -> m de falha por hectare
      -> recorta pelos talhoes do inventario
      -> salva o raster continuo e uma versao classificada com quebras fixas

Usa todas as linhas da fazenda que estao no banco. A carga troca as linhas
talhao a talhao (ADR 0012), entao o mapa e o da fazenda como ela esta agora,
mesmo que os talhoes tenham vindo de entregas diferentes.

As quebras sao FIXAS de proposito: escala relativa a cada area impediria
comparar um talhao com outro e entre safras.

Os rasters sao .tif numa pasta, e nao uma file gdb: qualquer conta liberada
para o relatorio sob demanda precisa conseguir gravar, e numa gdb os arquivos
internos pertencem a quem a criou. O gerador procura aqui e na rasters.gdb
antiga, e usa o mais recente.

Roda sozinho depois de cada carga de linhas (carga_linhas_falha.py). A mao:
  propy -u src\\processamento\\mapa_calor_falhas.py 320127

Requer: extensao Spatial Analyst.

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

PASTA_SAIDA = r"D:\GEO\FALHAS\rasters_calor"  # mesma do gerador do relatorio

SR_METRICO = arcpy.SpatialReference(31981)   # SIRGAS 2000 / UTM 21S

CELULA_M = 2          # tamanho da celula do raster
RAIO_M = 40           # raio de busca do kernel

# Quebras fixas da escala, em metros de falha por hectare.
QUEBRAS = [300, 600, 900]

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


def gerar(fazenda, sufixo=None):
    """Gera HEAT_<fazenda>_<sufixo>.tif e devolve o caminho."""
    fazenda = str(fazenda).strip()
    if not (fazenda.isdigit() and len(fazenda) == 6):
        raise ValueError("fazenda invalida: %r" % fazenda)
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst indisponivel nesta conta")
    from arcpy.sa import ExtractByMask, KernelDensity, Reclassify, RemapRange

    sufixo = sufixo or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(PASTA_SAIDA, exist_ok=True)
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

        saida_cont = os.path.join(PASTA_SAIDA, "HEAT_%s_%s.tif" % (fazenda, sufixo))
        recortado.save(saida_cont)
        print("raster continuo: %s" % saida_cont)

        remap = RemapRange([
            [0, QUEBRAS[0], 1],
            [QUEBRAS[0], QUEBRAS[1], 2],
            [QUEBRAS[1], QUEBRAS[2], 3],
            [QUEBRAS[2], 100000, 4],
        ])
        classificado = Reclassify(recortado, "VALUE", remap, "NODATA")
        saida_cls = os.path.join(PASTA_SAIDA, "HEAT_CLS_%s_%s.tif" % (fazenda, sufixo))
        classificado.save(saida_cls)
        print("raster classificado: %s" % saida_cls)

        maximo = arcpy.management.GetRasterProperties(recortado, "MAXIMUM")
        print("densidade maxima observada: %.0f m/ha" % float(maximo.getOutput(0)))

        arcpy.management.Delete(pontos)
        arcpy.management.Delete(mascara)
        return saida_cont
    finally:
        # o extent fica no ambiente do processo e cortaria o que vier depois,
        # como o desenho do relatorio
        arcpy.env.extent = None
        arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: propy -u src\\processamento\\mapa_calor_falhas.py <fazenda>")
        sys.exit(1)
    gerar(sys.argv[1])
