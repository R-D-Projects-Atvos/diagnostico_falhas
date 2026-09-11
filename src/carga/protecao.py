# -*- coding: utf-8 -*-
"""
Protecoes comuns das cargas por substituicao total.

Toda carga que apaga e regrava uma tabela le a origem inteira antes. Aqui
fica a decisao de gravar ou nao a partir do que foi lido, e a regravacao que
nao deixa a tabela pela metade.

Geotecnologia / Cartografia - Atvos
"""

# Queda maxima aceita, em % das linhas que ja estao no banco. Uma origem que
# chega com menos da metade quase sempre e consulta interrompida ou permissao
# faltando, e nao mudanca real: a carga para e pede conferencia.
QUEDA_MAXIMA_PCT = 50.0


def motivo_para_nao_gravar(novas, atuais, queda_maxima_pct=QUEDA_MAXIMA_PCT):
    """None = pode gravar. Texto = por que nao."""
    if novas == 0:
        return "a origem veio vazia"
    if atuais and novas < atuais * (1 - queda_maxima_pct / 100.0):
        return ("a origem trouxe %d linhas e o banco tem %d - queda acima de "
                "%.0f%%" % (novas, atuais, queda_maxima_pct))
    return None


def regravar(destino, campos, novas):
    """Apaga e regrava. Se a insercao falhar no meio, devolve as linhas que
    havia antes e repassa o erro - a tabela nunca fica pela metade."""
    import arcpy

    anteriores = [list(r) for r in arcpy.da.SearchCursor(destino, campos)]
    arcpy.management.DeleteRows(destino)
    try:
        with arcpy.da.InsertCursor(destino, campos) as ins:
            for linha in novas:
                ins.insertRow(linha)
    except Exception:
        print("ERRO na gravacao - devolvendo as %d linhas anteriores" % len(anteriores))
        arcpy.management.DeleteRows(destino)
        with arcpy.da.InsertCursor(destino, campos) as ins:
            for linha in anteriores:
                ins.insertRow(linha)
        raise
    return len(novas)
