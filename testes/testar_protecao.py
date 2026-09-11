# -*- coding: utf-8 -*-
"""
Testes da protecao comum das cargas por substituicao total. Nenhum toca no
banco.

Uso: propy -u testes\\testar_protecao.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "carga"))
from protecao import motivo_para_nao_gravar  # noqa: E402

falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


print("motivo_para_nao_gravar")
confere("origem vazia: nao grava", motivo_para_nao_gravar(0, 4611) is not None)
confere("origem vazia com banco vazio: nao grava", motivo_para_nao_gravar(0, 0) is not None)
confere("banco vazio: grava", motivo_para_nao_gravar(10, 0) is None)
confere("origem maior que o banco: grava", motivo_para_nao_gravar(4695, 4611) is None)
confere("queda pequena (10%): grava", motivo_para_nao_gravar(4150, 4611) is None)
confere("queda de exatamente 50%: grava", motivo_para_nao_gravar(50, 100) is None)
confere("queda acima de 50%: nao grava", motivo_para_nao_gravar(49, 100) is not None)
confere("limite configuravel", motivo_para_nao_gravar(85, 100, queda_maxima_pct=10) is not None)

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
