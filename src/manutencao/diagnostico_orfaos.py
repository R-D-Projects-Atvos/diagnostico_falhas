# -*- coding: utf-8 -*-
"""
Diagnostica por que 4 linhas do repeat da missao nao encontram o registro pai.

Uso: python C:\\temp\\diagnostico_orfaos.py
"""

import getpass
from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Table

PORTAL = "https://geoportal.atvos.com/portal"
USUARIO = "joao.fgromboni@ETH"

B = ("https://geoportal.atvos.com/server/rest/services/Hosted"
     "/service_ffb97edbaa524ba3872425369a9b214b/FeatureServer")

SUSPEITOS = [584, 585, 588, 589]

senha = getpass.getpass("Senha do Portal: ")
gis = GIS(PORTAL, USUARIO, senha)
print("conectado como:", gis.users.me.username)

pai = FeatureLayer(B + "/0", gis=gis)
fil = Table(B + "/1", gis=gis)

pais = pai.query(where="1=1",
                 out_fields="objectid,uniquerowid,cod_fazenda,cod_setor",
                 return_geometry=False).features

chaves = {}
sem_chave = []
for f in pais:
    a = f.attributes
    bruto = a.get("uniquerowid")
    if bruto:
        chaves[bruto.upper()] = a
    else:
        sem_chave.append(a["objectid"])

print("\npais no total: %d" % len(pais))
print("pais COM uniquerowid: %d" % len(chaves))
print("pais SEM uniquerowid: %d -> objectid %s" % (len(sem_chave), sem_chave))

print("\n--- linhas suspeitas do repeat ---")
onde = "objectid IN (%s)" % ",".join(str(x) for x in SUSPEITOS)
for f in fil.query(where=onde, out_fields="objectid,cod_talhao,parentrowid",
                   return_geometry=False).features:
    a = f.attributes
    p = a.get("parentrowid") or ""
    achou = p.upper() in chaves
    print("objectid %s | talhao %s | parentrowid %s | achou pai: %s"
          % (a["objectid"], a.get("cod_talhao"), repr(p), achou))
    if achou:
        d = chaves[p.upper()]
        print("    pai objectid %s | fazenda %s | setor %s"
              % (d["objectid"], d.get("cod_fazenda"), d.get("cod_setor")))

print("\n--- pai 78 (missao da fazenda 320127) ---")
for f in pai.query(where="objectid=78",
                   out_fields="objectid,uniquerowid,cod_fazenda,cod_setor",
                   return_geometry=False).features:
    print(f.attributes)
