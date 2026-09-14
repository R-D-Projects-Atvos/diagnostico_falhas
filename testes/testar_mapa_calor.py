# -*- coding: utf-8 -*-
"""
Testes do mapa de calor que nao tocam no banco: ler fazenda e data do nome do
raster, que preenchem FAZENDA e DATA_GERACAO no mosaico.

Uso: propy -u testes\\testar_mapa_calor.py
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "processamento"))
from mapa_calor_falhas import campos_do_nome  # noqa: E402

falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


dt = datetime.datetime
print("campos_do_nome")
confere("nome com data e hora da geracao",
        campos_do_nome("HEAT_320127_20260914_082311") == ("320127", dt(2026, 9, 14, 8, 23, 11)))
confere("nome antigo, so com a data do voo",
        campos_do_nome("HEAT_320127_20260708") == ("320127", dt(2026, 7, 8)))
confere("raster classificado antigo nao e raster de calor",
        campos_do_nome("HEAT_CLS_320127_20260708") is None)
confere("fazenda sem 6 digitos", campos_do_nome("HEAT_32012_20260708") is None)
confere("data invalida", campos_do_nome("HEAT_320127_20261399") is None)
confere("outro nome qualquer", campos_do_nome("FALHAS") is None)

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
