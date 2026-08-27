# -*- coding: utf-8 -*-
"""
Inspeciona a Status_Report_VANT, origem do percentual oficial de falhas.

Imprime: lista de campos, contagem, amostra dos talhoes da area piloto e
uma varredura de preenchimento dos campos (quanto de cada um esta nulo).

Uso: python C:\\temp\\inspecionar_status_report.py
"""

import arcpy

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
TABELA = SDE + r"\ATVOSPUBLICADOR.Status_Report_VANT"   # ajuste se estiver em dataset

PILOTO = ["32012700010004", "32012700010005",
          "32012700010006", "32012700010007"]

d = arcpy.Describe(TABELA)
print("=== %s ===" % TABELA)
print("tipo:", d.dataType)
print()

campos = [f for f in arcpy.ListFields(TABELA)]
print("=== CAMPOS ===")
for f in campos:
    print("  %-28s %-12s %-6s  %s"
          % (f.name, f.type, f.length if f.length else "", f.aliasName))

total = int(arcpy.management.GetCount(TABELA)[0])
print("\ntotal de registros:", total)

# --- amostra da area piloto ---
nomes = [f.name for f in campos if f.type not in ("Geometry", "Blob", "Raster")]
chave = next((f.name for f in campos
              if f.name.upper() in ("CHAVESIG", "CHAVE_SIG")), None)

if chave:
    lista = ",".join("'%s'" % c for c in PILOTO)
    onde = "%s IN (%s)" % (arcpy.AddFieldDelimiters(TABELA, chave), lista)
    print("\n=== AMOSTRA area piloto (campo %s) ===" % chave)
    n = 0
    with arcpy.da.SearchCursor(TABELA, nomes, onde) as cur:
        for linha in cur:
            n += 1
            print("\n--- registro %d ---" % n)
            for nome, valor in zip(nomes, linha):
                if valor not in (None, ""):
                    print("  %-24s %s" % (nome, valor))
    if n == 0:
        print("(nenhum registro para a area piloto)")
else:
    print("\nnenhum campo de chave reconhecido - veja a lista de campos acima")

# --- preenchimento de cada campo ---
print("\n=== PREENCHIMENTO (amostra de ate 5000 registros) ===")
contagem = {n: 0 for n in nomes}
lidos = 0
with arcpy.da.SearchCursor(TABELA, nomes) as cur:
    for linha in cur:
        lidos += 1
        for nome, valor in zip(nomes, linha):
            if valor not in (None, ""):
                contagem[nome] += 1
        if lidos >= 5000:
            break

for nome in nomes:
    pct = 100.0 * contagem[nome] / lidos if lidos else 0
    marca = "" if pct > 90 else ("  <-- pouco preenchido" if pct < 50 else "")
    print("  %-28s %6.1f%%%s" % (nome, pct, marca))
