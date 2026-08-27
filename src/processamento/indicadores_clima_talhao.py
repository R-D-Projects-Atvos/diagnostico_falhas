# -*- coding: utf-8 -*-
"""
Calcula os indicadores climaticos da janela de brotacao por talhao.

Cria/atualiza:
  ATVOSPUBLICADOR.INDICADORES_CLIMA_TALHAO   uma linha por chavesig

A janela e de 0 a 30 dias apos o plantio - e nela que a maior parte da falha
se origina. Os indicadores sao os que dependem SO de precipitacao e
temperatura; balanco hidrico (ARM/CAD) fica para quando houver CAD do solo.

Cada indicador vem acompanhado da media da UNIDADE na mesma safra. Numero
sozinho nao diagnostica nada: 18 mm de chuva so significa alguma coisa ao
lado dos 76 mm que o resto da unidade recebeu.

Confiabilidade: ate 15 km a estacao representa bem o talhao; acima disso o
dado e exibido com ressalva (1,9% dos talhoes).

IMPORTANTE: nao habilite archiving nesta tabela - ela e reescrita todo dia.

Uso: python -u C:\\temp\\indicadores_clima_talhao.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
TB_VINCULO = SDE + r"\ATVOSPUBLICADOR.TALHAO_ESTACAO"
TB_DIARIO = SDE + r"\ATVOSPUBLICADOR.MONITORAMENTO_ESTACAO"
TB_SAIDA = SDE + r"\ATVOSPUBLICADOR.INDICADORES_CLIMA_TALHAO"

JANELA_DIAS = 30          # janela de brotacao
JANELA_CURTA = 15         # sub-janela critica
VERANICO_MM = 5.0         # dia "seco": chuva abaixo disso
TMAX_QUENTE = 35.0        # dia de calor extremo
RAIO_CONFIAVEL_KM = 15.0

CAMPOS = [
    ("CHAVESIG", "TEXT", 14), ("UNIDADE", "TEXT", 10), ("SAFRA", "TEXT", 10),
    ("DT_PLANTIO", "DATE", None),
    ("PIC_ID", "LONG", None), ("ESTACAO_NOME", "TEXT", 40),
    ("DISTANCIA_KM", "DOUBLE", None), ("CONFIABILIDADE", "TEXT", 12),
    ("CHUVA_0_15", "DOUBLE", None), ("CHUVA_0_30", "DOUBLE", None),
    ("DIAS_COM_CHUVA", "LONG", None), ("MAIOR_VERANICO", "LONG", None),
    ("TMAX_MEDIA", "DOUBLE", None), ("DIAS_TMAX_ALTA", "LONG", None),
    ("UMID_MEDIA", "DOUBLE", None), ("DIAS_SEM_DADO", "LONG", None),
    ("CHUVA_0_15_UNID", "DOUBLE", None), ("CHUVA_0_30_UNID", "DOUBLE", None),
    ("DIAS_CHUVA_UNID", "DOUBLE", None), ("VERANICO_UNID", "DOUBLE", None),
    ("DATA_CALCULO", "DATE", None),
]


def criar():
    if arcpy.Exists(TB_SAIDA):
        return
    print("criando INDICADORES_CLIMA_TALHAO")
    arcpy.management.CreateTable(SDE, "INDICADORES_CLIMA_TALHAO")
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(TB_SAIDA, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(TB_SAIDA, nome, tipo)
    arcpy.management.AddIndex(TB_SAIDA, ["CHAVESIG"], "IDX_ICT_CHAVESIG")


def ler_diario():
    """{pic_id: {data: (chuva, tmax, umid_media)}}"""
    dados = {}
    campos = ["PIC_ID", "DIA", "CHUVA_TOTAL", "TEMP_MAX", "UMID_MEDIA"]
    with arcpy.da.SearchCursor(TB_DIARIO, campos) as cur:
        for pic, dia, chuva, tmax, umid in cur:
            if pic is None or dia is None:
                continue
            dados.setdefault(pic, {})[dia.date()] = (chuva, tmax, umid)
    total = sum(len(v) for v in dados.values())
    print("monitoramento: %d estacoes, %d dias-estacao" % (len(dados), total))
    return dados


def ler_vinculo():
    vinc = {}
    campos = ["CHAVESIG", "PIC_ID", "ESTACAO_NOME", "DISTANCIA_KM"]
    with arcpy.da.SearchCursor(TB_VINCULO, campos) as cur:
        for chave, pic, nome, dist in cur:
            vinc[chave] = (pic, nome, dist)
    print("vinculos talhao-estacao: %d" % len(vinc))
    return vinc


def ler_talhoes():
    """Chavesig, unidade, safra e data de plantio do inventario."""
    talhoes = []
    campos = ["Chavesig", "EmpDesc", "Safra", "DATA_PLANTIO"]
    with arcpy.da.SearchCursor(FC_INVENTARIO, campos) as cur:
        for chave, unidade, safra, plantio in cur:
            if not chave or plantio is None:
                continue
            talhoes.append((str(chave).strip(), unidade, safra, plantio.date()))
    print("talhoes com data de plantio: %d" % len(talhoes))
    return talhoes


def indicadores(serie, plantio):
    """Percorre a janela dia a dia. Dia ausente conta como sem dado e
    NAO entra no veranico - ausencia de registro nao e ausencia de chuva."""
    chuva15 = chuva30 = 0.0
    dias_chuva = sem_dado = dias_quentes = 0
    tmax_soma = tmax_n = 0
    umid_soma = umid_n = 0
    veranico = maior_veranico = 0

    for i in range(JANELA_DIAS + 1):
        dia = plantio + datetime.timedelta(days=i)
        registro = serie.get(dia)
        if registro is None:
            sem_dado += 1
            veranico = 0
            continue
        chuva, tmax, umid = registro
        chuva = chuva or 0.0
        chuva30 += chuva
        if i <= JANELA_CURTA:
            chuva15 += chuva
        if chuva >= VERANICO_MM:
            dias_chuva += 1
            veranico = 0
        else:
            veranico += 1
            maior_veranico = max(maior_veranico, veranico)
        if tmax is not None:
            tmax_soma += tmax
            tmax_n += 1
            if tmax >= TMAX_QUENTE:
                dias_quentes += 1
        if umid is not None:
            umid_soma += umid
            umid_n += 1

    return {
        "chuva15": round(chuva15, 1), "chuva30": round(chuva30, 1),
        "dias_chuva": dias_chuva, "veranico": maior_veranico,
        "tmax": round(tmax_soma / tmax_n, 1) if tmax_n else None,
        "quentes": dias_quentes,
        "umid": round(umid_soma / umid_n, 1) if umid_n else None,
        "sem_dado": sem_dado,
    }


def calcular():
    criar()
    diario = ler_diario()
    vinculo = ler_vinculo()
    talhoes = ler_talhoes()

    agora = datetime.datetime.now()
    resultados, sem_vinculo, sem_serie, fora_periodo = [], 0, 0, 0

    for chave, unidade, safra, plantio in talhoes:
        v = vinculo.get(chave)
        if not v:
            sem_vinculo += 1
            continue
        pic, nome, dist = v
        serie = diario.get(pic)
        if not serie:
            sem_serie += 1
            continue

        ind = indicadores(serie, plantio)
        if ind["sem_dado"] > JANELA_DIAS:      # janela inteira fora da serie
            fora_periodo += 1
            continue

        conf = ("Boa" if (dist or 0) <= RAIO_CONFIAVEL_KM else "Ressalva")
        resultados.append([chave, unidade, safra, plantio, pic, nome,
                           dist, conf, ind])

    print("\ncalculados: %d" % len(resultados))
    print("  sem vinculo de estacao : %d" % sem_vinculo)
    print("  estacao sem serie      : %d" % sem_serie)
    print("  janela fora do periodo : %d" % fora_periodo)

    medias = medias_por_unidade(resultados)
    gravar(resultados, medias, agora)
    conferir()


def medias_por_unidade(resultados):
    """Media dos indicadores por unidade e safra - a referencia do relatorio."""
    somas = {}
    for chave, unidade, safra, _, _, _, _, _, ind in resultados:
        k = (unidade, safra)
        acc = somas.setdefault(k, {"n": 0, "c15": 0.0, "c30": 0.0,
                                   "dc": 0, "ver": 0})
        acc["n"] += 1
        acc["c15"] += ind["chuva15"]
        acc["c30"] += ind["chuva30"]
        acc["dc"] += ind["dias_chuva"]
        acc["ver"] += ind["veranico"]

    medias = {}
    for k, a in somas.items():
        n = float(a["n"])
        medias[k] = (round(a["c15"] / n, 1), round(a["c30"] / n, 1),
                     round(a["dc"] / n, 1), round(a["ver"] / n, 1))
    print("  grupos unidade+safra   : %d" % len(medias))
    return medias


def gravar(resultados, medias, agora):
    arcpy.management.DeleteRows(TB_SAIDA)
    nomes = [c[0] for c in CAMPOS]
    with arcpy.da.InsertCursor(TB_SAIDA, nomes) as ins:
        for chave, unidade, safra, plantio, pic, nome, dist, conf, ind in resultados:
            m = medias.get((unidade, safra), (None, None, None, None))
            ins.insertRow([
                chave, unidade, safra, plantio, pic, nome, dist, conf,
                ind["chuva15"], ind["chuva30"], ind["dias_chuva"],
                ind["veranico"], ind["tmax"], ind["quentes"], ind["umid"],
                ind["sem_dado"], m[0], m[1], m[2], m[3], agora,
            ])
    print("gravados: %d" % len(resultados))


def conferir():
    piloto = ["32012700010004", "32012700010005",
              "32012700010006", "32012700010007"]
    campo = arcpy.AddFieldDelimiters(TB_SAIDA, "CHAVESIG")
    onde = "%s IN (%s)" % (campo, ",".join("'%s'" % p for p in piloto))
    campos = ["CHAVESIG", "ESTACAO_NOME", "DISTANCIA_KM", "CONFIABILIDADE",
              "CHUVA_0_15", "CHUVA_0_30", "CHUVA_0_30_UNID",
              "DIAS_COM_CHUVA", "MAIOR_VERANICO", "VERANICO_UNID",
              "TMAX_MEDIA", "DIAS_SEM_DADO"]
    print("\n=== area piloto (plantio em 03/03/2026) ===")
    print(" | ".join(campos))
    with arcpy.da.SearchCursor(TB_SAIDA, campos, onde) as cur:
        for linha in sorted(cur, key=lambda r: str(r[0])):
            print(" | ".join("-" if v is None else str(v) for v in linha))


if __name__ == "__main__":
    calcular()
