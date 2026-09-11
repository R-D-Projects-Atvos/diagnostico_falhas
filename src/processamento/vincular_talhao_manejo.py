# -*- coding: utf-8 -*-
"""
Vincula cada talhao a uma unidade de manejo de solo, pela mancha PREDOMINANTE
em area.

Um talhao pode cair sobre mais de uma mancha. A regra adotada e a unidade que
ocupa a MAIOR AREA dentro do talhao. O percentual dessa unidade tambem e
gravado (PCT_AREA), para que o relatorio saiba quando o vinculo e limpo (100%)
e quando o talhao e dividido entre solos diferentes.

Por que a intersecao roda em UTM: o dataset esta em GCS_WGS_1984, onde area
sai em graus quadrados e nao serve para comparar manchas. A intersecao e feita
numa copia projetada, em memoria.

Saida: ATVOSPUBLICADOR.TALHAO_MANEJO (sem geometria, sem archiving).

Uso: python -u C:\\temp\\vincular_talhao_manejo.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

# precisa casar com NOME_CAMADA do carga_mancha_solos.py
NOME_CAMADA_SOLOS = "SOLOS_ATVOS"
FC_SOLOS = os.path.join(DATASET, "ATVOSPUBLICADOR." + NOME_CAMADA_SOLOS)
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
FC_DATABASE = os.path.join(DATASET, "ATVOSPUBLICADOR.TALHOES_DATABASE")

TB_SAIDA = SDE + r"\ATVOSPUBLICADOR.TALHAO_MANEJO"

# SIRGAS 2000 / UTM 22S - o mesmo SR nativo do shapefile de solos
EPSG_AREA = 31982

# abaixo disso o talhao mal encosta na mancha; provavelmente e borda
PCT_MINIMO_ALERTA = 60.0

CAMPOS = [
    ("CHAVESIG", "TEXT", 20),
    ("ORIGEM_TALHAO", "TEXT", 12),
    ("NUM_MANEJO", "SHORT", None),
    ("MANEJO", "TEXT", 254),
    ("SOLO", "TEXT", 254),
    ("TEXTURA", "TEXT", 30),
    ("AMB_ATVOS", "TEXT", 5),
    ("PCT_AREA", "DOUBLE", None),
    ("QTD_MANCHAS", "SHORT", None),
    ("DATA_CALCULO", "DATE", None),
]


def criar():
    if arcpy.Exists(TB_SAIDA):
        return
    print("criando a tabela %s..." % TB_SAIDA)
    arcpy.management.CreateTable(SDE, "TALHAO_MANEJO")
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(TB_SAIDA, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(TB_SAIDA, nome, tipo)
    arcpy.management.AddIndex(TB_SAIDA, ["CHAVESIG"], "IDX_TMJ_CHAVESIG")


def talhoes_projetados():
    """Une inventario e database numa camada projetada em memoria.

    O inventario e o que o relatorio de falhas usa; a database entra para que
    o vinculo sirva tambem a outras analises. Chave repetida fica com a origem
    marcada como AMBAS.
    """
    sr = arcpy.SpatialReference(EPSG_AREA)
    print("projetando os talhoes para UTM...")

    origens = []
    for fc, marca in ((FC_INVENTARIO, "INVENTARIO"), (FC_DATABASE, "DATABASE")):
        if not arcpy.Exists(fc):
            print("  AVISO: %s nao encontrada - ignorando" % fc)
            continue
        destino = r"memory\proj_%s" % marca.lower()
        arcpy.management.Project(fc, destino, sr)
        arcpy.management.AddField(destino, "ORIGEM_TALHAO", "TEXT", field_length=12)
        arcpy.management.CalculateField(
            destino, "ORIGEM_TALHAO", "'%s'" % marca, "PYTHON3")
        n = int(arcpy.management.GetCount(destino)[0])
        print("  %-12s %d feicoes" % (marca, n))
        origens.append(destino)

    if not origens:
        raise RuntimeError("nenhuma camada de talhao disponivel")

    unido = r"memory\talhoes_utm"
    if len(origens) == 1:
        arcpy.management.CopyFeatures(origens[0], unido)
    else:
        arcpy.management.Merge(origens, unido)
    return unido


def intersectar(talhoes):
    """Intersecao talhao x mancha, com a area de cada pedaco."""
    sr = arcpy.SpatialReference(EPSG_AREA)
    solos_utm = r"memory\solos_utm"
    arcpy.management.Project(FC_SOLOS, solos_utm, sr)

    print("intersectando talhoes com as manchas de solo...")
    saida = r"memory\talhao_x_solo"
    arcpy.analysis.Intersect([talhoes, solos_utm], saida, "ALL")
    n = int(arcpy.management.GetCount(saida)[0])
    print("  %d pedacos gerados" % n)
    return saida


def achar_campo(fc, *candidatos):
    """Descobre o nome real de um campo na saida do Intersect.

    O Intersect renomeia campos quando ha conflito entre as camadas de
    entrada (acrescenta sufixo _1, prefixo da origem, etc). Em vez de supor
    o nome, procura por correspondencia sem diferenciar maiuscula, e depois
    por prefixo/sufixo.
    """
    nomes = [f.name for f in arcpy.ListFields(fc)]
    mapa = {n.upper(): n for n in nomes}
    for c in candidatos:
        if c.upper() in mapa:
            return mapa[c.upper()]
    for c in candidatos:
        alvo = c.upper()
        for n in nomes:
            u = n.upper()
            if u.startswith(alvo) or u.endswith(alvo) or alvo in u:
                return n
    raise RuntimeError(
        "campo nao encontrado (tentei %s). Campos disponiveis: %s"
        % (", ".join(candidatos), ", ".join(nomes)))


def consolidar(intersecao):
    """Soma a area por talhao+mancha e escolhe a predominante."""
    print("  campos da intersecao: %s"
          % ", ".join(f.name for f in arcpy.ListFields(intersecao)
                      if f.type not in ("OID", "Geometry")))

    c_chave = achar_campo(intersecao, "Chavesig", "CHAVESIG")
    c_origem = achar_campo(intersecao, "ORIGEM_TALHAO")
    c_um = achar_campo(intersecao, "NUM_MANEJO", "Num_Manejo")
    c_manejo = achar_campo(intersecao, "MANEJO", "Manejo")
    c_solo = achar_campo(intersecao, "SOLO", "solo")
    c_textura = achar_campo(intersecao, "TEXTURA", "Textura")
    c_amb = achar_campo(intersecao, "AMB_ATVOS", "Amb_Atvos")

    campos = [c_chave, c_origem, c_um, c_manejo, c_solo, c_textura, c_amb,
              "SHAPE@AREA"]

    por_talhao = {}
    with arcpy.da.SearchCursor(intersecao, campos) as cur:
        for chave, origem, um, manejo, solo, textura, amb, area in cur:
            if not chave or um is None:
                continue
            chave = chave.strip()
            reg = por_talhao.setdefault(chave, {"origens": set(), "manchas": {}})
            reg["origens"].add(origem)
            m = reg["manchas"].setdefault(
                int(um), {"area": 0.0, "manejo": manejo, "solo": solo,
                          "textura": textura, "amb": amb})
            m["area"] += area or 0.0

    print("  talhoes com pelo menos uma mancha: %d" % len(por_talhao))

    linhas, divididos, fracos = [], 0, 0
    agora = datetime.datetime.now()
    for chave, reg in por_talhao.items():
        total = sum(m["area"] for m in reg["manchas"].values())
        if total <= 0:
            continue
        um, dados = max(reg["manchas"].items(), key=lambda kv: kv[1]["area"])
        pct = 100.0 * dados["area"] / total
        qtd = len(reg["manchas"])
        if qtd > 1:
            divididos += 1
        if pct < PCT_MINIMO_ALERTA:
            fracos += 1
        origens = reg["origens"]
        origem = "AMBAS" if len(origens) > 1 else list(origens)[0]
        linhas.append([chave, origem, um, dados["manejo"], dados["solo"],
                       dados["textura"], dados["amb"], round(pct, 1), qtd, agora])

    return linhas, divididos, fracos


def gravar(linhas):
    print("regravando a tabela...")
    arcpy.management.TruncateTable(TB_SAIDA)
    campos = [c[0] for c in CAMPOS]
    with arcpy.da.InsertCursor(TB_SAIDA, campos) as ins:
        for l in linhas:
            ins.insertRow(l)


def executar():
    criar()
    talhoes = talhoes_projetados()
    intersecao = intersectar(talhoes)
    linhas, divididos, fracos = consolidar(intersecao)

    if not linhas:
        raise RuntimeError("nenhum vinculo gerado - abortando sem gravar")

    gravar(linhas)

    from collections import Counter
    por_um = Counter(l[2] for l in linhas)

    print("\n=== resultado ===")
    print("  talhoes vinculados : %d" % len(linhas))
    print("  sobre mais de uma mancha: %d (%.1f%%)"
          % (divididos, 100.0 * divididos / len(linhas)))
    print("  mancha predominante abaixo de %.0f%%: %d"
          % (PCT_MINIMO_ALERTA, fracos))
    print("\n  distribuicao por unidade de manejo:")
    for um in sorted(por_um):
        print("    UM %-3d %6d talhoes" % (um, por_um[um]))

    print("\ntabela: %s" % TB_SAIDA)
    print("falta a declividade para consultar a Matriz de Plantio.")

    arcpy.management.Delete("memory")


if __name__ == "__main__":
    executar()