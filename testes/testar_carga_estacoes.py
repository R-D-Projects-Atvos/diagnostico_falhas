# -*- coding: utf-8 -*-
"""
Testes da carga do cadastro das estacoes que nao tocam no banco: ler unidade e
fazenda do nome, e comparar a origem com o que esta no banco.

Uso: propy -u testes\\testar_carga_estacoes.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "carga"))
from carga_estacoes_zeus import diferencas, partes_do_nome  # noqa: E402

falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


print("partes_do_nome")
confere("padrao UNIDADE_FAZENDA", partes_do_nome("USL_320013") == ("USL", "320013"))
confere("tolera sufixo", partes_do_nome("URC_219053 II") == ("URC", "219053"))
confere("minuscula vira maiuscula", partes_do_nome("usl_320013")[0] == "USL")
confere("sem underline", partes_do_nome("ESTACAO 1") == (None, None))
confere("vazio", partes_do_nome(None) == (None, None))
confere("sem digitos depois do underline", partes_do_nome("USL_SEDE") == ("USL", None))


def estacao(nome, status, lat, lon):
    return {"NOME": nome, "STATUS": status, "LAT": lat, "LON": lon}


atuais = {
    1: estacao("USL_320121", "OK", -21.0, -51.0),
    2: estacao("UCR_430080", "INTERMITTENT", -18.0, -53.0),
    3: estacao("URC_210017", "FAIL", -22.0, -50.0),
    4: estacao("UEL_310240", "OK", -20.0, -49.0),       # some da origem
    5: estacao("UCP_120442", "OK", -19.0, -52.0),
}
novas = {
    1: estacao("USL_320121", "OK", -21.0, -51.0),        # igual
    2: estacao("UCR_430080", "OK", -18.0, -53.0),        # status
    3: estacao("URC_210017", "OK", -22.0, -50.0),        # status
    5: estacao("UCP_120442", "OK", -19.00002, -52.0),    # mudou de lugar
    6: estacao("UAT_420033", "OK", -17.5, -53.3),        # nova
    7: estacao("UAE_449203 II", "OK", -17.2, -52.9),     # nova
}
d = diferencas(novas, atuais)

print("\ndiferencas")
confere("estacao nova", d["novas"] == ["UAT_420033", "UAE_449203 II"])
confere("estacao que saiu", d["sumiram"] == ["UEL_310240"])
confere("mudanca de status", d["status"] == [("UCR_430080", "INTERMITTENT", "OK"),
                                             ("URC_210017", "FAIL", "OK")])
confere("mudanca de lugar acima da tolerancia",
        [i[0] for i in d["posicao"]] == ["UCP_120442"])
confere("estacao igual nao aparece",
        all("USL_320121" not in str(v) for v in d.values()))
confere("diferenca menor que a tolerancia e ignorada",
        diferencas({1: estacao("USL_320121", "OK", -21.000001, -51.0)},
                   {1: atuais[1]})["posicao"] == [])
confere("mudanca de nome", diferencas({1: estacao("USL_320122", "OK", -21.0, -51.0)},
                                      {1: atuais[1]})["nome"]
        == [("USL_320121", "USL_320122")])
confere("banco vazio: tudo novo", len(diferencas(novas, {})["novas"]) == len(novas))
confere("nada muda", all(not v for v in diferencas(atuais, atuais).values()))

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
