# -*- coding: utf-8 -*-
"""
Carga da view Operacao_Vant (BigQuery) para ATVOSPUBLICADOR.Status_Report_VANT.

Estrategia: substituicao total. A origem no BQ e a verdade; o SQL Server e
copia local para o relatorio e o painel nao dependerem do BigQuery em tempo
de consulta. Sao ~4.600 registros, roda em segundos.

O campo Layer JA E o chavesig de 14 digitos - nao ha concatenacao a fazer.
A origem so tem falhas; os campos de daninhas ficam nulos ate existirem la.

Uso: python C:\\temp\\carga_status_report.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import arcpy

arcpy.env.overwriteOutput = True

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DESTINO = SDE + r"\ATVOSPUBLICADOR.Status_Report_VANT"

BQ = r"D:\GEO\TALHOES\BigQuery-dl-bq-prd-gold_arcgis.sde"
ORIGEM_NOME = "Operacao_Vant"

# origem no BQ -> destino no SQL Server
MAPA = {
    "Layer": "Layer",
    "UNIDADE": "UNIDADE",
    "DA_EMPRESA": "DA_EMPRESA",
    "CD_MES": "CD_MES",
    "DT_PLANTIO": "DT_PLANTIO",
    "NO_BOLETIM": "NO_BOLETIM",
    "CD_UPNIVEL1": "CD_UPNIVEL1",
    "DE_UPNIVEL1": "DE_UPNIVEL1",
    "CD_UPNIVEL2": "CD_UPNIVEL2",
    "CD_UPNIVEL3": "CD_UPNIVEL3",
    "TIPO_PROPR": "TIPO_PROPR",
    "ADMIN": "ADMIN",
    "Area_total": "Area_total",
    "FG_REPLANTIO": "FG_REPLANTIO",
    "CD_SIST_PLAN": "CD_SIST_PLAN",
    "SIST_PLANTIO": "SIST_PLANTIO",
    "COD_VARIEDADE": "COD_VARIEDADE",
    "VARIEDADE": "VARIEDADE",
    "DPP": "DPP",
    "FALHA_LINHA": "FALHA_LINHA",
    "DATA_AMOSTRA": "DATA_AMOSTRA",
    "Status": "Status_Falha",
}

PILOTO = ["32012700010004", "32012700010005",
          "32012700010006", "32012700010007"]


def localizar_origem():
    arcpy.env.workspace = BQ
    tabelas = arcpy.ListTables() or []
    for t in tabelas:
        if t.split(".")[-1].lower() == ORIGEM_NOME.lower():
            return BQ + "\\" + t
    raise RuntimeError("nao achei %s no BQ. disponiveis: %s"
                       % (ORIGEM_NOME, tabelas))


def carregar():
    origem = localizar_origem()
    print("origem: %s" % origem)

    campos_bq = {f.name for f in arcpy.ListFields(origem)}
    faltando = [c for c in MAPA if c not in campos_bq]
    if faltando:
        raise RuntimeError("campos ausentes na origem: %s" % faltando)

    n_antes = int(arcpy.management.GetCount(DESTINO)[0])
    print("registros atuais no destino: %d" % n_antes)

    origem_campos = list(MAPA.keys())
    destino_campos = [MAPA[c] for c in origem_campos] + ["DATA_CARGA"]

    lidos = []
    with arcpy.da.SearchCursor(origem, origem_campos) as cur:
        for linha in cur:
            lidos.append(list(linha))
    print("lidos do BQ: %d" % len(lidos))

    # le tudo ANTES de apagar: falha de conexao nao pode zerar a producao
    if not lidos:
        raise RuntimeError("origem vazia - carga abortada para nao zerar o destino")

    idx_layer = origem_campos.index("Layer")
    sem_layer = sum(1 for l in lidos if not l[idx_layer])
    fora_padrao = sum(1 for l in lidos
                      if l[idx_layer] and len(str(l[idx_layer])) != 14)
    if sem_layer:
        print("AVISO: %d registros sem Layer" % sem_layer)
    if fora_padrao:
        print("AVISO: %d registros com Layer fora de 14 digitos" % fora_padrao)

    print("limpando o destino...")
    arcpy.management.DeleteRows(DESTINO)

    agora = datetime.datetime.now()
    inseridos = 0
    with arcpy.da.InsertCursor(DESTINO, destino_campos) as ins:
        for linha in lidos:
            ins.insertRow(linha + [agora])
            inseridos += 1

    print("inseridos: %d" % inseridos)
    conferir()


def conferir():
    campo = arcpy.AddFieldDelimiters(DESTINO, "Layer")
    onde = "%s IN (%s)" % (campo, ",".join("'%s'" % p for p in PILOTO))

    print("\n=== conferencia da area piloto ===")
    print("%-16s %9s %10s %12s" % ("Layer", "falha %", "area ha", "amostra"))
    achou = 0
    with arcpy.da.SearchCursor(
            DESTINO, ["Layer", "FALHA_LINHA", "Area_total", "DATA_AMOSTRA"],
            onde) as cur:
        for layer, falha, area, amostra in sorted(cur, key=lambda r: r[0]):
            achou += 1
            print("%-16s %9s %10s %12s"
                  % (layer, falha, area,
                     amostra.strftime("%d/%m/%Y") if amostra else "-"))
    if achou == 0:
        print("(nada encontrado - o Layer pode nao estar com 14 digitos)")
    print("\nesperado: ...0006 com 23,8 | ...0004 com 9,4 | "
          "...0005 com 16,1 | ...0007 com 11,3")


if __name__ == "__main__":
    carregar()
