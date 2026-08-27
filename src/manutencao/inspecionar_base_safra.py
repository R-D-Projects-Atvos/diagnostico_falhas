# -*- coding: utf-8 -*-
"""
Inspeciona a BASE_SAFRA para preparar a carga das linhas de falha.

Imprime: sistema de referencia, lista de campos, contagem, e uma amostra
dos talhoes da fazenda piloto (320127).

Uso: python C:\\temp\\inspecionar_base_safra.py
"""

import arcpy

SDE = r"C:\conexoes\atvospublicador.sde"      # ajuste para a sua conexao
FC = SDE + r"\ATVOSPUBLICADOR.BASE_SAFRA"     # ajuste se o nome for outro

FAZENDA_PILOTO = "320127"

d = arcpy.Describe(FC)
sr = d.spatialReference

print("=== FEATURE CLASS ===")
print("caminho:", FC)
print("tipo:", d.shapeType)
print()
print("=== SISTEMA DE REFERENCIA ===")
print("nome :", sr.name)
print("WKID :", sr.factoryCode)
print("unid.:", sr.linearUnitName)
print()
print("=== CAMPOS ===")
for f in arcpy.ListFields(FC):
    print("  %-28s %-12s %-6s  %s"
          % (f.name, f.type, f.length if f.length else "", f.aliasName))

print()
print("total de feicoes:", arcpy.management.GetCount(FC)[0])

# amostra da fazenda piloto -- ajuste o nome do campo de chave se necessario
campos_chave = [f.name for f in arcpy.ListFields(FC)
                if f.name.upper() in ("CHAVESIG", "CHAVE_SIG", "CHAVEZONA")]
if not campos_chave:
    print("\nnenhum campo de chave reconhecido -- veja a lista acima")
else:
    chave = campos_chave[0]
    onde = "%s LIKE '%s%%'" % (arcpy.AddFieldDelimiters(FC, chave), FAZENDA_PILOTO)
    nomes = [f.name for f in arcpy.ListFields(FC)
             if f.type not in ("Geometry", "Blob", "Raster")]
    print("\n=== AMOSTRA fazenda %s (campo %s) ===" % (FAZENDA_PILOTO, chave))
    print(" | ".join(nomes))
    n = 0
    with arcpy.da.SearchCursor(FC, nomes, onde) as cur:
        for linha in cur:
            print(" | ".join("" if v is None else str(v) for v in linha))
            n += 1
            if n >= 15:
                break
    if n == 0:
        print("(nenhuma feicao encontrada -- a fazenda piloto pode estar no HISTORICO_SAFRA)")
