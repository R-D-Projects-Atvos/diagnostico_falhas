# -*- coding: utf-8 -*-
"""
Carga das linhas de falha da Bem Agro para ATVOSPUBLICADOR.LINHAS_FALHA.

Fluxo:
    FALHAS.shp (WGS84 geografico)
      -> spatial join contra a base de inventario (BASE_SAFRA), por centro da feicao
      -> grava chavesig, safra do inventario e metadados do voo
      -> apaga carga anterior do mesmo lote (idempotencia)
      -> imprime o percentual por talhao para conferir com o PIMS

Observacoes:
  - O dataset AGRICOLA_ATVOS esta em GCS_WGS_1984 (4326), igual ao shapefile
    da Bem Agro, entao nao ha reprojecao no join.
  - A area do denominador vem de Area_total (ha) do inventario. Shape.STArea()
    esta em graus quadrados e NAO serve.
  - O percentual usa LengthComp, que e o campo que a Bem Agro usa no PIMS.

Geotecnologia / Cartografia - Atvos
"""

import os
import datetime
import arcpy

arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO DA ENTREGA
# ---------------------------------------------------------------------------

SHP_ENTRADA = r"C:\temp\vectors-gaps\FALHAS.shp"

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_DESTINO = os.path.join(DATASET, "ATVOSPUBLICADOR.LINHAS_FALHA")

# Camada de inventario: BASE_SAFRA para a safra vigente,
# HISTORICO_SAFRA para areas de safras anteriores.
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
NOME_INVENTARIO = "BASE_SAFRA"

DATA_VOO = "2026-07-08"          # do Registro de Missao (Survey123)
LOTE = "320127_20260708"         # identificador da entrega

# Espacamento entre linhas de plantio, em metros.
# O campo ESPAC do inventario vem codificado ("99"), entao usamos parametro
# ate existir o de-para dos codigos do PIMS.
ESPACAMENTO_M = 1.5

# ---------------------------------------------------------------------------

CAMPOS = [
    ("CHAVESIG",   "TEXT",   20),
    ("SAFRA_INV",  "TEXT",   10),
    ("CAMADA_INV", "TEXT",   30),
    ("TALHAO_KML", "TEXT",    5),
    ("COMP_M",     "DOUBLE", None),
    ("COMP_OFI_M", "DOUBLE", None),
    ("CLASSE_TAM", "TEXT",   12),
    ("DATA_VOO",   "DATE",  None),
    ("LOTE",       "TEXT",   60),
    ("DATA_CARGA", "DATE",  None),
]


def classe_tamanho(m):
    if m < 0.5:
        return "< 0,5 m"
    if m < 1.0:
        return "0,5 a 1 m"
    if m < 2.0:
        return "1 a 2 m"
    if m < 5.0:
        return "2 a 5 m"
    return "> 5 m"


def criar_destino():
    if arcpy.Exists(FC_DESTINO):
        return
    print("criando %s" % FC_DESTINO)
    sr = arcpy.Describe(FC_INVENTARIO).spatialReference
    arcpy.management.CreateFeatureclass(DATASET, "LINHAS_FALHA", "POLYLINE",
                                        spatial_reference=sr)
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(FC_DESTINO, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(FC_DESTINO, nome, tipo)
    arcpy.management.AddIndex(FC_DESTINO, ["CHAVESIG"], "IDX_LF_CHAVESIG")
    arcpy.management.AddIndex(FC_DESTINO, ["LOTE"], "IDX_LF_LOTE")


def limpar_lote():
    camada = "lyr_lote"
    arcpy.management.MakeFeatureLayer(FC_DESTINO, camada,
                                      "LOTE = '%s'" % LOTE)
    n = int(arcpy.management.GetCount(camada)[0])
    if n:
        print("removendo %d feicoes da carga anterior deste lote" % n)
        arcpy.management.DeleteFeatures(camada)
    arcpy.management.Delete(camada)


def carregar():
    criar_destino()
    limpar_lote()

    # so os talhoes que interessam, para o join nao varrer a base inteira
    talhoes = "lyr_talhoes"
    arcpy.management.MakeFeatureLayer(FC_INVENTARIO, talhoes)
    arcpy.management.SelectLayerByLocation(talhoes, "INTERSECT", SHP_ENTRADA)
    n_talhoes = int(arcpy.management.GetCount(talhoes)[0])
    print("talhoes do inventario na area da entrega: %d" % n_talhoes)
    if n_talhoes == 0:
        raise RuntimeError("nenhum talhao encontrado - confira a camada de inventario")

    juncao = r"in_memory\falhas_join"
    arcpy.analysis.SpatialJoin(
        SHP_ENTRADA, talhoes, juncao,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="HAVE_THEIR_CENTER_IN")

    agora = datetime.datetime.now()
    data_voo = datetime.datetime.strptime(DATA_VOO, "%Y-%m-%d")

    origem = ["SHAPE@", "Field", "Length", "LengthComp", "Chavesig", "Safra"]
    destino = ["SHAPE@", "CHAVESIG", "SAFRA_INV", "CAMADA_INV", "TALHAO_KML",
               "COMP_M", "COMP_OFI_M", "CLASSE_TAM", "DATA_VOO", "LOTE",
               "DATA_CARGA"]

    resumo, sem_talhao, total = {}, 0, 0

    with arcpy.da.InsertCursor(FC_DESTINO, destino) as ins:
        with arcpy.da.SearchCursor(juncao, origem) as cur:
            for geom, kml, comp, comp_ofi, chavesig, safra in cur:
                if not chavesig:
                    sem_talhao += 1
                ins.insertRow([geom, chavesig, safra, NOME_INVENTARIO, kml,
                               comp, comp_ofi, classe_tamanho(comp_ofi),
                               data_voo, LOTE, agora])
                total += 1
                chave = chavesig or "(sem talhao)"
                acc = resumo.setdefault(chave, {"n": 0, "m": 0.0, "kml": set()})
                acc["n"] += 1
                acc["m"] += comp_ofi or 0.0
                acc["kml"].add(kml)

    arcpy.management.Delete(juncao)
    arcpy.management.Delete(talhoes)

    print("\ncarregadas %d feicoes (%d sem talhao)" % (total, sem_talhao))
    relatorio(resumo)


def relatorio(resumo):
    # area do inventario por chavesig
    areas = {}
    with arcpy.da.SearchCursor(FC_INVENTARIO, ["Chavesig", "TALHAO",
                                               "Area_total", "ESPAC"]) as cur:
        for chave, talhao, area, espac in cur:
            if chave in resumo:
                areas[chave] = (talhao, area, espac)

    print("\n=== percentual por talhao (LengthComp / espacamento %.2f m) ==="
          % ESPACAMENTO_M)
    print("%-16s %-7s %9s %11s %9s %8s" %
          ("chavesig", "talhao", "area ha", "m de falha", "m/ha", "falhas %"))

    tot_m, tot_area = 0.0, 0.0
    for chave in sorted(resumo):
        acc = resumo[chave]
        if chave not in areas:
            print("%-16s %-7s %9s %11.0f %9s %8s   (KML %s)"
                  % (chave, "-", "-", acc["m"], "-", "-",
                     ",".join(sorted(acc["kml"]))))
            continue
        talhao, area, _ = areas[chave]
        linear = area * 10000.0 / ESPACAMENTO_M
        pct = 100.0 * acc["m"] / linear if linear else 0.0
        print("%-16s %-7s %9.2f %11.0f %9.0f %7.2f%%   (KML %s)"
              % (chave, talhao, area, acc["m"], acc["m"] / area, pct,
                 ",".join(sorted(acc["kml"]))))
        tot_m += acc["m"]
        tot_area += area

    if tot_area:
        linear = tot_area * 10000.0 / ESPACAMENTO_M
        print("%-16s %-7s %9.2f %11.0f %9.0f %7.2f%%"
              % ("TOTAL", "", tot_area, tot_m, tot_m / tot_area,
                 100.0 * tot_m / linear))
        print("\nespacamento implicito para fechar o valor oficial:")
        print("  informe o %% do PIMS e compare: espac = %%_pims * area_ha * 10000 / metros")


if __name__ == "__main__":
    carregar()
