# -*- coding: utf-8 -*-
"""
Testes da escolha da data de plantio (PIMS antes do inventario). Nenhum toca
no banco.

Uso: propy -u testes\\testar_data_plantio.py
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "processamento"))
from data_plantio import (FONTE_INVENTARIO, FONTE_PIMS, como_data,  # noqa: E402
                          escolher, safra_por_unidade)

falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


d = datetime.date
dt = datetime.datetime

inventario = {
    "A": (dt(2026, 3, 3), "USL", "22627"),    # mesma data no PIMS
    "B": (dt(2020, 9, 17), "UEL", "22627"),   # reforma: PIMS tem a nova
    "C": (None, "USL", "22627"),              # sem data no inventario
    "D": (dt(2026, 2, 10), "USL", "22627"),   # so no inventario
    "E": (None, "UCP", "22627"),              # sem data em lugar nenhum
    "F": (dt(2026, 1, 5), "USL", "22728"),
}
pims = {
    "A": (dt(2026, 3, 3), "USL"),
    "B": (dt(2026, 7, 28), "UEL"),
    "C": (dt(2026, 8, 1), "USL"),
    "G": (dt(2026, 8, 20), "USL"),            # fora do inventario
    "H": (None, "UAT"),                       # PIMS sem data, fora do inventario
    "I": (dt(2026, 8, 21), "UMV"),            # unidade que o inventario nao tem
}
datas = escolher(pims, inventario)

print("escolher")
confere("PIMS e inventario com a mesma data: fonte PIMS",
        datas["A"] == (d(2026, 3, 3), FONTE_PIMS, "USL", "22627"))
confere("reforma: vale a data do PIMS", datas["B"][0] == d(2026, 7, 28))
confere("inventario sem data: vem do PIMS",
        datas["C"][:2] == (d(2026, 8, 1), FONTE_PIMS))
confere("so no inventario: fonte INVENTARIO",
        datas["D"] == (d(2026, 2, 10), FONTE_INVENTARIO, "USL", "22627"))
confere("sem data nas duas: fica de fora", "E" not in datas and "H" not in datas)
confere("fora do inventario: unidade do PIMS e safra vigente da unidade",
        datas["G"] == (d(2026, 8, 20), FONTE_PIMS, "USL", "22627"))
confere("unidade sem safra no inventario: safra nula", datas["I"][3] is None)
confere("datetime vira date", all(isinstance(v[0], d) and not isinstance(v[0], dt)
                                  for v in datas.values()))
confere("PIMS vazio: fica so o inventario",
        set(escolher({}, inventario)) == {"A", "B", "D", "F"})

print("\nsafra_por_unidade")
confere("safra mais frequente por unidade",
        safra_por_unidade(inventario) == {"USL": "22627", "UEL": "22627",
                                          "UCP": "22627"})

print("\ncomo_data")
confere("None continua None", como_data(None) is None)
confere("date continua date", como_data(d(2026, 1, 1)) == d(2026, 1, 1))

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
