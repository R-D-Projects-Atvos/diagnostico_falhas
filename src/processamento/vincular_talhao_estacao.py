# -*- coding: utf-8 -*-
"""
Monta o vinculo TALHAO -> ESTACAO METEOROLOGICA.

Cria/atualiza:
  ATVOSPUBLICADOR.TALHAO_ESTACAO   uma linha por chavesig

Regras:
  - Se a fazenda do talhao TEM estacao propria (nome UNIDADE_FAZENDA no
    cadastro) e ela esta OK, o vinculo e por CADASTRO. Foi alguem da unidade
    que decidiu qual estacao representa aquela fazenda - vale mais que
    geometria. Sao poucas fazendas.
  - Caso contrario, a estacao OK mais proxima do centroide do talhao,
    marcada como PROXIMIDADE.
  - Estacoes com status diferente de OK ficam de fora: uma estacao em falha
    nao deve alimentar diagnostico.
  - A distancia e sempre gravada, inclusive no vinculo por cadastro.

Cobertura: uniao dos chavesig da TALHOES_DATABASE (base atual de campo) e da
BASE_SAFRA (inventario). O relatorio de falhas usa o inventario, o resto da
empresa usa a database - a tabela serve aos dois.

IMPORTANTE: nao habilite archiving nesta tabela. Ela e reescrita todo dia;
com archiving ligado viraria milhoes de linhas, como aconteceu com a
BASE_SAFRA.

Uso: python -u C:\\temp\\vincular_talhao_estacao.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import math
import os
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

FC_DATABASE = os.path.join(DATASET, "ATVOSPUBLICADOR.TALHOES_DATABASE")
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
FC_ESTACOES = os.path.join(DATASET, "ATVOSPUBLICADOR.ESTACOES_ZEUS")

TB_VINCULO = SDE + r"\ATVOSPUBLICADOR.TALHAO_ESTACAO"

CAMPOS = [
    ("CHAVESIG", "TEXT", 14), ("ORIGEM_TALHAO", "TEXT", 12),
    ("PIC_ID", "LONG", None), ("ESTACAO_NOME", "TEXT", 40),
    ("ESTACAO_UNIDADE", "TEXT", 10), ("DISTANCIA_KM", "DOUBLE", None),
    ("ORIGEM_VINCULO", "TEXT", 14), ("DATA_CALCULO", "DATE", None),
]

RAIO_TERRA_KM = 6371.0088


def distancia_km(lat1, lon1, lat2, lon2):
    """Haversine. Evita depender de projecao - a base esta em 4326."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


def criar():
    if arcpy.Exists(TB_VINCULO):
        return
    print("criando TALHAO_ESTACAO")
    arcpy.management.CreateTable(SDE, "TALHAO_ESTACAO")
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(TB_VINCULO, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(TB_VINCULO, nome, tipo)
    arcpy.management.AddIndex(TB_VINCULO, ["CHAVESIG"], "IDX_TE_CHAVESIG")
    arcpy.management.AddIndex(TB_VINCULO, ["PIC_ID"], "IDX_TE_PICID")


def ler_estacoes():
    """So as estacoes saudaveis. Indexadas tambem por codigo de fazenda."""
    ativas, por_fazenda, descartadas = [], {}, 0
    campos = ["PIC_ID", "NOME", "UNIDADE", "COD_FAZENDA", "LAT", "LON", "STATUS"]
    with arcpy.da.SearchCursor(FC_ESTACOES, campos) as cur:
        for pic, nome, uni, faz, lat, lon, status in cur:
            if status != "OK" or lat is None or lon is None:
                descartadas += 1
                continue
            reg = (pic, nome, uni, lat, lon)
            ativas.append(reg)
            if faz:
                por_fazenda[str(faz)] = reg
    print("estacoes ativas: %d (descartadas: %d)" % (len(ativas), descartadas))
    return ativas, por_fazenda


def ler_talhoes():
    """Centroide por chavesig, unindo database e inventario.

    O cursor do arcpy respeita o archiving, entao nao ha risco de vir versao
    antiga - diferente de consulta SQL direta.
    """
    centroides, origem = {}, {}
    for caminho, marca in ((FC_DATABASE, "DATABASE"),
                           (FC_INVENTARIO, "INVENTARIO")):
        if not arcpy.Exists(caminho):
            print("AVISO: %s nao encontrada - ignorada" % caminho)
            continue
        n = 0
        with arcpy.da.SearchCursor(caminho, ["Chavesig", "SHAPE@"]) as cur:
            for chave, geom in cur:
                if not chave or geom is None:
                    continue
                chave = str(chave).strip()
                n += 1
                if chave not in centroides:
                    p = geom.trueCentroid
                    centroides[chave] = (p.Y, p.X)
                origem[chave] = ("AMBAS" if origem.get(chave, marca) != marca
                                 else marca)
        print("  %-12s: %d feicoes" % (marca, n))
    print("chavesig distintos: %d" % len(centroides))
    return centroides, origem


def calcular():
    criar()
    estacoes, por_fazenda = ler_estacoes()
    if not estacoes:
        raise RuntimeError("nenhuma estacao ativa - calculo abortado")

    centroides, origem = ler_talhoes()
    if not centroides:
        raise RuntimeError("nenhum talhao lido - calculo abortado")

    agora = datetime.datetime.now()
    linhas, distancias, por_origem = [], [], {}

    for chave, (lat, lon) in centroides.items():
        faz = chave[:6]
        cadastrada = por_fazenda.get(faz)

        if cadastrada:
            pic, nome, uni, elat, elon = cadastrada
            vinculo = "CADASTRO"
        else:
            melhor, menor = None, None
            for reg in estacoes:
                d = distancia_km(lat, lon, reg[3], reg[4])
                if menor is None or d < menor:
                    menor, melhor = d, reg
            pic, nome, uni, elat, elon = melhor
            vinculo = "PROXIMIDADE"

        d = distancia_km(lat, lon, elat, elon)
        distancias.append(d)
        por_origem[vinculo] = por_origem.get(vinculo, 0) + 1
        linhas.append([chave, origem.get(chave), pic, nome, uni,
                       round(d, 2), vinculo, agora])

    print("\ngravando %d vinculos..." % len(linhas))
    arcpy.management.DeleteRows(TB_VINCULO)
    with arcpy.da.InsertCursor(TB_VINCULO, [c[0] for c in CAMPOS]) as ins:
        for l in linhas:
            ins.insertRow(l)

    relatorio(distancias, por_origem)


def relatorio(distancias, por_origem):
    distancias.sort()
    n = len(distancias)

    def pct(p):
        return distancias[min(n - 1, int(n * p / 100.0))]

    print("\n=== origem do vinculo ===")
    for k in sorted(por_origem):
        print("  %-14s %6d  (%.1f%%)" % (k, por_origem[k],
                                         100.0 * por_origem[k] / n))

    print("\n=== distribuicao das distancias (km) ===")
    for rotulo, valor in (("minima", distancias[0]), ("p25", pct(25)),
                          ("mediana", pct(50)), ("p75", pct(75)),
                          ("p90", pct(90)), ("p95", pct(95)),
                          ("maxima", distancias[-1])):
        print("  %-8s %7.1f" % (rotulo, valor))

    print("\n=== quantos talhoes ficariam de fora por raio ===")
    for raio in (5, 10, 15, 20, 30, 50):
        fora = sum(1 for d in distancias if d > raio)
        print("  raio %2d km: %6d talhoes fora (%.1f%%)"
              % (raio, fora, 100.0 * fora / n))
    print("\nEscolha o raio olhando estes numeros e me diga - ele entra como "
          "regra de exibicao, nao de carga (o vinculo continua gravado).")


if __name__ == "__main__":
    calcular()
