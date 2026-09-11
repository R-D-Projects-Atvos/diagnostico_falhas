# -*- coding: utf-8 -*-
"""
Testes da conferencia do carga_monitoramento_zeus.py. Nenhum toca no banco.

As regras que decidem se a carga apaga e regrava a tabela sao as que mais
podem causar dano sem erro: por isso sao testadas isoladas, com planilhas de
mentira.

Uso: propy -u testes\\testar_carga_monitoramento.py
"""

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "carga"))
import carga_monitoramento_zeus as carga  # noqa: E402

D = datetime.date
falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


def base(estacoes=(1, 2), inicio=D(2025, 7, 21), dias=10):
    return [(e, inicio + datetime.timedelta(days=i))
            for e in estacoes for i in range(dias)]


print("resumo")
r = carga.resumo(base())
confere("conta linhas, estacoes e periodo",
        (r["linhas"], r["estacoes"], r["inicio"], r["fim"], r["repetidos"])
        == (20, 2, D(2025, 7, 21), D(2025, 7, 30), 0))
confere("aceita datetime e date misturados",
        carga.resumo([(1, datetime.datetime(2025, 7, 21)), (1, D(2025, 7, 21))])["repetidos"] == 1)

print("\nmotivos_para_nao_gravar")
atual = carga.resumo(base())
confere("planilha igual ao banco: grava",
        carga.motivos_para_nao_gravar(carga.resumo(base()), atual) == [])
confere("planilha com dias novos: grava",
        carga.motivos_para_nao_gravar(carga.resumo(base(dias=15)), atual) == [])
confere("banco vazio: grava",
        carga.motivos_para_nao_gravar(carga.resumo(base()), carga.resumo([])) == [])
confere("planilha vazia: nao grava",
        len(carga.motivos_para_nao_gravar(carga.resumo([]), atual)) == 1)
confere("comeca depois do banco: nao grava",
        any("dias antigos" in m for m in carga.motivos_para_nao_gravar(
            carga.resumo(base(inicio=D(2025, 7, 25), dias=20)), atual)))
confere("termina antes do banco: nao grava",
        any("antes do banco" in m for m in carga.motivos_para_nao_gravar(
            carga.resumo(base(dias=5)), atual)))
confere("estacao a menos: nao grava",
        any("estacoes" in m for m in carga.motivos_para_nao_gravar(
            carga.resumo(base(estacoes=(1,), dias=40)), atual)))
confere("menos linhas no mesmo periodo: nao grava",
        any("linhas" in m for m in carga.motivos_para_nao_gravar(
            carga.resumo(base()[:-3] + [(2, D(2025, 7, 30))]), atual)))
confere("estacao+dia repetido: nao grava",
        any("repetidos" in m for m in carga.motivos_para_nao_gravar(
            carga.resumo(base() + [(1, D(2025, 7, 21))]), atual)))

print("\narquivo_de_entrada")
with tempfile.TemporaryDirectory() as pasta:
    try:
        carga.arquivo_de_entrada(pasta)
        confere("pasta sem planilha: erro", False)
    except RuntimeError:
        confere("pasta sem planilha: erro", True)
    for nome, atraso in (("antiga.xlsx", 100), ("nova.xlsx", 0), ("~$nova.xlsx", -10)):
        caminho = os.path.join(pasta, nome)
        open(caminho, "w").close()
        t = datetime.datetime.now().timestamp() - atraso
        os.utime(caminho, (t, t))
    confere("usa a mais recente e ignora o ~$ do Excel",
            os.path.basename(carga.arquivo_de_entrada(pasta)) == "nova.xlsx")

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
