# -*- coding: utf-8 -*-
"""
Recria ATVOSPUBLICADOR.Status_Report_VANT com o esquema corrigido.

Mudancas em relacao a tabela atual:
  - Layer passa de BigInteger para TEXT(14). Ele E o chavesig, e como numero
    perderia o zero a esquerda de fazendas cujo codigo comeca com zero,
    deixando de casar com a LINHAS_FALHA.
  - Campos de texto passam de 255 para tamanhos realistas.
  - Indice em Layer, que e a chave de todos os joins do relatorio.
  - Os tres campos de daninhas permanecem, ainda sem origem no BQ.

A tabela esta vazia hoje, entao nao ha dado a preservar. Ainda assim o
script aborta se encontrar registros, para nao apagar nada por engano.

Uso: python C:\\temp\\recriar_status_report.py

Geotecnologia / Cartografia - Atvos
"""

import arcpy

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
NOME = "Status_Report_VANT"
TABELA = SDE + "\\ATVOSPUBLICADOR." + NOME

CAMPOS = [
    # nome,            tipo,        tamanho, alias
    ("Layer",          "TEXT",      14,   "Chavesig"),
    ("UNIDADE",        "TEXT",      10,   "Unidade"),
    ("DA_EMPRESA",     "TEXT",      60,   "Empresa"),
    ("CD_MES",         "TEXT",      10,   "Mes"),
    ("DT_PLANTIO",     "DATE",      None, "Data de plantio"),
    ("NO_BOLETIM",     "DOUBLE",    None, "Boletim"),
    ("CD_UPNIVEL1",    "TEXT",      10,   "Codigo fazenda"),
    ("DE_UPNIVEL1",    "TEXT",      60,   "Nome fazenda"),
    ("CD_UPNIVEL2",    "TEXT",      10,   "Setor"),
    ("CD_UPNIVEL3",    "TEXT",      10,   "Talhao"),
    ("TIPO_PROPR",     "LONG",      None, "Tipo propriedade"),
    ("ADMIN",          "TEXT",      30,   "Administracao"),
    ("Area_total",     "DOUBLE",    None, "Area total (ha)"),
    ("FG_REPLANTIO",   "TEXT",      5,    "Replantio"),
    ("CD_SIST_PLAN",   "LONG",      None, "Cod sistema plantio"),
    ("SIST_PLANTIO",   "TEXT",      30,   "Sistema de plantio"),
    ("COD_VARIEDADE",  "DOUBLE",    None, "Cod variedade"),
    ("VARIEDADE",      "TEXT",      30,   "Variedade"),
    ("DPP",            "LONG",      None, "DPP (calculado ate hoje)"),
    ("FALHA_LINHA",    "DOUBLE",    None, "Falhas (%)"),
    ("DATA_AMOSTRA",   "DATE",      None, "Publicacao no PIMS"),
    ("Status_Falha",   "TEXT",      30,   "Status falha"),
    ("AreaDaninha",    "DOUBLE",    None, "Area daninha"),
    ("TalhaoDaninhaArea", "DOUBLE", None, "Area daninha do talhao"),
    ("Status_Daninhas", "TEXT",     30,   "Status daninhas"),
    ("DATA_CARGA",     "DATE",      None, "Data da carga do BQ"),
]


def recriar():
    if arcpy.Exists(TABELA):
        n = int(arcpy.management.GetCount(TABELA)[0])
        print("tabela existente com %d registros" % n)
        if n > 0:
            raise RuntimeError(
                "a tabela tem %d registros - abortado. Se a exclusao for "
                "mesmo desejada, esvazie antes com DeleteRows." % n)
        print("excluindo...")
        arcpy.management.Delete(TABELA)

    print("criando %s" % TABELA)
    arcpy.management.CreateTable(SDE, NOME)

    for nome, tipo, tam, alias in CAMPOS:
        if tam:
            arcpy.management.AddField(TABELA, nome, tipo,
                                      field_length=tam, field_alias=alias)
        else:
            arcpy.management.AddField(TABELA, nome, tipo, field_alias=alias)
        print("  + %s (%s)" % (nome, tipo))

    arcpy.management.AddIndex(TABELA, ["Layer"], "IDX_SRV_LAYER")
    arcpy.management.AddIndex(TABELA, ["CD_UPNIVEL1"], "IDX_SRV_FAZENDA")
    print("indices criados")

    print("\ncampos finais:")
    for f in arcpy.ListFields(TABELA):
        print("  %-22s %-10s %s" % (f.name, f.type, f.length or ""))


if __name__ == "__main__":
    recriar()
