# -*- coding: utf-8 -*-
"""
Data de plantio de cada talhao, para o clima e para a epoca de plantio.

Vale a do PIMS (Status_Report_VANT.DT_PLANTIO). A do inventario (BASE_SAFRA)
so entra quando o PIMS nao tem o talhao.

O percentual, o DAP e a data que o relatorio mostra ja vinham do PIMS; o clima
e a epoca liam a BASE_SAFRA. As duas divergiam justamente nos talhoes com
resultado: em 11/09/2026, dos 4.695 talhoes publicados no PIMS, 176 nao estavam
no inventario vigente, 699 estavam nele sem data e 102 com outra data - quase
sempre a do plantio anterior, em area de reforma (PIMS 2026, inventario 2020).
Ver docs/adr/0011-data-de-plantio-do-pims.md.

Unidade e safra agrupam a media da unidade no clima. Continuam vindo do
inventario; o talhao que so o PIMS tem fica com a unidade do PIMS e com a
safra que o inventario tem para essa unidade.

Geotecnologia / Cartografia - Atvos
"""

import collections
import os

FONTE_PIMS = "PIMS"
FONTE_INVENTARIO = "INVENTARIO"


def como_data(valor):
    """datetime vira date; date e None passam direto."""
    if valor is not None and hasattr(valor, "date"):
        return valor.date()
    return valor


def texto(valor):
    if valor is None:
        return None
    return str(valor).strip() or None


def safra_por_unidade(inventario):
    """{unidade: safra mais frequente no inventario}"""
    contagem = collections.defaultdict(collections.Counter)
    for _, unidade, safra in inventario.values():
        if unidade and safra:
            contagem[unidade][safra] += 1
    return {u: c.most_common(1)[0][0] for u, c in contagem.items()}


def escolher(pims, inventario):
    """Junta as duas fontes.

    pims        {chavesig: (data, unidade)}
    inventario  {chavesig: (data, unidade, safra)}

    Devolve {chavesig: (data, fonte, unidade, safra)}. Talhao sem data nas
    duas fica de fora.
    """
    vigente = safra_por_unidade(inventario)
    datas = {}
    for chave, (data, unidade, safra) in inventario.items():
        if data is not None:
            datas[chave] = (como_data(data), FONTE_INVENTARIO, unidade, safra)
    for chave, (data, unidade) in pims.items():
        if data is None:
            continue
        _, unidade_inv, safra_inv = inventario.get(chave, (None, None, None))
        unidade = unidade_inv or unidade
        datas[chave] = (como_data(data), FONTE_PIMS, unidade,
                        safra_inv or vigente.get(unidade))
    return datas


def resumir(datas, inventario):
    do_pims = [c for c, d in datas.items() if d[1] == FONTE_PIMS]
    fora = sem_data = outra = 0
    for chave in do_pims:
        if chave not in inventario:
            fora += 1
        elif inventario[chave][0] is None:
            sem_data += 1
        elif como_data(inventario[chave][0]) != datas[chave][0]:
            outra += 1
    print("datas de plantio: %d talhoes - %d do PIMS, %d so do inventario"
          % (len(datas), len(do_pims), len(datas) - len(do_pims)), flush=True)
    print("  do PIMS e diferentes do inventario: fora dele %d | sem data nele %d "
          "| com outra data nele %d" % (fora, sem_data, outra), flush=True)
    if not do_pims:
        print("  AVISO: nenhuma data do PIMS - a Status_Report_VANT esta vazia? "
              "Ficou so a do inventario.", flush=True)


def ler(sde, fc_inventario):
    """{chavesig: (data, fonte, unidade, safra)} lido do banco."""
    import arcpy

    pims = {}
    tabela = os.path.join(sde, "ATVOSPUBLICADOR.Status_Report_VANT")
    with arcpy.da.SearchCursor(tabela, ["Layer", "DT_PLANTIO", "UNIDADE"]) as cur:
        for chave, data, unidade in cur:
            if chave:
                pims[str(chave).strip()] = (data, texto(unidade))

    inventario = {}
    campos = ["Chavesig", "DATA_PLANTIO", "EmpDesc", "Safra"]
    with arcpy.da.SearchCursor(fc_inventario, campos) as cur:
        for chave, data, unidade, safra in cur:
            if chave:
                inventario[str(chave).strip()] = (data, texto(unidade),
                                                  texto(safra))

    datas = escolher(pims, inventario)
    resumir(datas, inventario)
    return datas
