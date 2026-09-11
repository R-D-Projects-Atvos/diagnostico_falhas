# -*- coding: utf-8 -*-
"""
Carga da view Operacao_Vant (BigQuery) para ATVOSPUBLICADOR.Status_Report_VANT.

Estrategia: substituicao total. A origem no BQ e a verdade; o SQL Server e
copia local para o relatorio e o painel nao dependerem do BigQuery em tempo
de consulta. Sao ~4.700 registros, roda em segundos.

O campo Layer JA E o chavesig de 14 digitos - nao ha concatenacao a fazer.
A origem so tem falhas; os campos de daninhas ficam nulos ate existirem la.

Conexao: a mesma do atualizar_base.py, no OneDrive do Joao - so funciona
nessa conta. A copia em D:\\GEO\\TALHOES trava esperando login. A tabela e
aberta pelo nome completo: listar as tabelas do gold_arcgis (ListTables)
tambem trava o arcpy.

Sem --gravar, so simula: le, confere e mostra o que mudaria.

Uso:
  propy -u src\\carga\\carga_status_report.py            (simula)
  propy -u src\\carga\\carga_status_report.py --gravar   (grava)

Codigo de saida: 0 = ok | 1 = nada gravado (conferencia ou erro)

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import sys

import arcpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protecao import motivo_para_nao_gravar, regravar  # noqa: E402

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DESTINO = SDE + r"\ATVOSPUBLICADOR.Status_Report_VANT"

BQ = (r"C:\Users\joao.fgromboni\OneDrive - Atvos\Documentos\ArcGIS\Projects"
      r"\gdb_atvos\BigQuery-dl-bq-prd-gold_arcgis.sde")
ORIGEM = BQ + r"\dl-bq-prd.gold_arcgis.Operacao_Vant"

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


def ler_origem():
    campos_bq = {f.name for f in arcpy.ListFields(ORIGEM)}
    faltando = [c for c in MAPA if c not in campos_bq]
    if faltando:
        raise RuntimeError("campos ausentes na origem: %s" % faltando)
    with arcpy.da.SearchCursor(ORIGEM, list(MAPA)) as cur:
        return [list(linha) for linha in cur]


def carregar(gravar):
    print("=" * 64)
    print(" PERCENTUAL OFICIAL (Operacao_Vant) - %s"
          % ("GRAVACAO" if gravar else "SIMULACAO (use --gravar para gravar)"))
    print("=" * 64)
    print("origem: %s" % ORIGEM)

    # le tudo ANTES de apagar: falha de conexao nao pode zerar a producao
    lidos = ler_origem()
    n_antes = int(arcpy.management.GetCount(DESTINO)[0])
    print("lidos do BQ: %d | no banco hoje: %d" % (len(lidos), n_antes))

    campos = list(MAPA)
    idx_layer, idx_data = campos.index("Layer"), campos.index("DATA_AMOSTRA")
    sem_layer = sum(1 for l in lidos if not l[idx_layer])
    fora_padrao = sum(1 for l in lidos
                      if l[idx_layer] and len(str(l[idx_layer])) != 14)
    if sem_layer:
        print("AVISO: %d registros sem Layer" % sem_layer)
    if fora_padrao:
        print("AVISO: %d registros com Layer fora de 14 digitos" % fora_padrao)
    datas = [l[idx_data] for l in lidos if l[idx_data]]
    if datas:
        print("publicacao no PIMS: %s a %s"
              % (min(datas).strftime("%d/%m/%Y"), max(datas).strftime("%d/%m/%Y")))

    motivo = motivo_para_nao_gravar(len(lidos), n_antes)
    if motivo:
        print("\nNADA FOI GRAVADO: %s" % motivo)
        return 1

    if not gravar:
        print("\nSIMULACAO: nada gravado. Com --gravar, a tabela passaria de %d "
              "para %d linhas." % (n_antes, len(lidos)))
        return 0

    agora = datetime.datetime.now()
    destino_campos = [MAPA[c] for c in campos] + ["DATA_CARGA"]
    print("regravando o destino...")
    inseridos = regravar(DESTINO, destino_campos, [l + [agora] for l in lidos])
    print("inseridos: %d" % inseridos)
    conferir()
    return 0


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
    print("\nreferencia (voo de 08/07/2026): ...0006 com 23,8 | ...0004 com 9,4 | "
          "...0005 com 16,1 | ...0007 com 11,3")


if __name__ == "__main__":
    sys.exit(carregar("--gravar" in sys.argv))
