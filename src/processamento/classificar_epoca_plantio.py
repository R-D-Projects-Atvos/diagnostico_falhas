# -*- coding: utf-8 -*-
"""
Classifica a epoca de plantio de cada talhao segundo a Matriz de Plantio.

Junta tres coisas que ja estao no banco:
  unidade de manejo + faixa de declividade  ->  TALHAO_MANEJO
  data de plantio                           ->  BASE_SAFRA
  recomendacao por periodo                  ->  MATRIZ_PLANTIO

e responde: aquela area foi plantada em epoca favoravel, aceitavel ou
restritiva.

SOBRE A RESSALVA DE DECLIVIDADE
O declividade_talhao.py marca como "Ressalva" o talhao cuja mediana cai perto
da fronteira entre faixas - 36% do total, porque a distribuicao real se
concentra em torno de 2,5%.

Marcar 36% dos talhoes como incertos seria inutil: ninguem le uma ressalva
que aparece em um terco dos casos. Entao aqui a pergunta muda: se este
talhao estivesse na faixa vizinha, a recomendacao para a data em que ele foi
plantado seria diferente? Se nao mudaria, nao ha incerteza a comunicar.

Isso reduz muito o alarme, porque em 5 das 14 unidades de manejo as faixas
"< 2,5%" e "2,5 a 5%" dao exatamente a mesma recomendacao nos 17 periodos, e
nas outras 9 diferem em 1 a 3 periodos apenas.

Uso: python -u C:\\temp\\classificar_epoca_plantio.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
TB_MANEJO = SDE + r"\ATVOSPUBLICADOR.TALHAO_MANEJO"
TB_MATRIZ = SDE + r"\ATVOSPUBLICADOR.MATRIZ_PLANTIO"
TB_SAIDA = SDE + r"\ATVOSPUBLICADOR.EPOCA_PLANTIO_TALHAO"

# ordem das faixas, para saber quem e vizinho de quem
FAIXAS_ORDEM = ["< 2,5%", "2,5 a 5%", "> 5%"]

CAMPOS = [
    ("CHAVESIG", "TEXT", 20),
    ("SAFRA", "TEXT", 10),
    ("DT_PLANTIO", "DATE", None),
    ("PERIODO_PLANTIO", "TEXT", 12),
    ("NUM_MANEJO", "SHORT", None),
    ("FAIXA_DECLIV", "TEXT", 12),
    ("DECLIV_MEDIANA", "DOUBLE", None),
    ("PCT_AREA_MANEJO", "DOUBLE", None),
    ("CLASSE_EPOCA", "TEXT", 30),
    ("CONDICAO", "TEXT", 120),
    ("EPOCA_CONFIANCA", "TEXT", 12),
    ("CLASSE_ALTERNATIVA", "TEXT", 30),
    ("MOTIVO_RESSALVA", "TEXT", 120),
    ("DATA_CALCULO", "DATE", None),
]


def periodo_da_data(data):
    """Traduz a data de plantio para o periodo usado pela matriz.

    Janeiro a maio sao divididos em quinzenas; junho a dezembro valem o mes
    inteiro. A primeira quinzena vai do dia 1 ao 15.
    """
    meses = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
             7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
    mes = meses[data.month]
    if data.month <= 5:
        return "%s %s" % (mes, "1Q" if data.day <= 15 else "2Q")
    return mes


def ler_matriz():
    """{(unidade, faixa, periodo): (classe, condicao)}"""
    matriz = {}
    campos = ["NUM_MANEJO", "FAIXA_DECLIV", "PERIODO", "CLASSE_EPOCA",
              "CONDICAO"]
    with arcpy.da.SearchCursor(TB_MATRIZ, campos) as cur:
        for um, faixa, periodo, classe, condicao in cur:
            if um is None:
                continue
            matriz[(int(um), (faixa or "").strip(), (periodo or "").strip())] = \
                (classe, condicao)
    print("matriz carregada: %d combinacoes" % len(matriz))
    if not matriz:
        raise RuntimeError("MATRIZ_PLANTIO vazia - rode carga_matriz_plantio.py")
    return matriz


def ler_manejo():
    """{chavesig: (unidade, faixa, mediana, pct_area)}"""
    dados = {}
    campos = ["CHAVESIG", "NUM_MANEJO", "FAIXA_DECLIV", "DECLIV_MEDIANA",
              "PCT_AREA"]
    with arcpy.da.SearchCursor(TB_MANEJO, campos) as cur:
        for chave, um, faixa, mediana, pct in cur:
            if not chave or um is None:
                continue
            dados[chave.strip()] = (int(um), (faixa or "").strip() or None,
                                    mediana, pct)
    print("talhoes com unidade de manejo: %d" % len(dados))
    return dados


def ler_plantio():
    """{chavesig: (safra, data de plantio)} - so o inventario vigente."""
    dados = {}
    campos = ["Chavesig", "Safra", "DATA_PLANTIO"]
    with arcpy.da.SearchCursor(FC_INVENTARIO, campos) as cur:
        for chave, safra, plantio in cur:
            if not chave or plantio is None:
                continue
            dados[chave.strip()] = ((safra or "").strip(), plantio)
    print("talhoes com data de plantio: %d" % len(dados))
    return dados


def vizinhas(faixa):
    if faixa not in FAIXAS_ORDEM:
        return []
    i = FAIXAS_ORDEM.index(faixa)
    return [FAIXAS_ORDEM[j] for j in (i - 1, i + 1)
            if 0 <= j < len(FAIXAS_ORDEM)]


def criar():
    if arcpy.Exists(TB_SAIDA):
        return
    print("criando a tabela %s..." % TB_SAIDA)
    arcpy.management.CreateTable(SDE, "EPOCA_PLANTIO_TALHAO")
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(TB_SAIDA, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(TB_SAIDA, nome, tipo)
    arcpy.management.AddIndex(TB_SAIDA, ["CHAVESIG"], "IDX_EPOCA_CHAVESIG")


def classificar():
    matriz = ler_matriz()
    manejo = ler_manejo()
    plantio = ler_plantio()

    agora = datetime.datetime.now()
    linhas = []
    sem_plantio = sem_faixa = sem_regra = 0
    from collections import Counter
    por_classe, por_confianca = Counter(), Counter()

    for chave, (um, faixa, mediana, pct) in manejo.items():
        info = plantio.get(chave)
        if not info:
            sem_plantio += 1
            continue
        safra, data = info
        if hasattr(data, "date"):
            data = data.date()
        if not faixa:
            sem_faixa += 1
            continue

        periodo = periodo_da_data(data)
        regra = matriz.get((um, faixa, periodo))
        if not regra:
            sem_regra += 1
            continue
        classe, condicao = regra

        # a ressalva so vale se mudar de faixa mudaria a recomendacao
        alternativas = set()
        for outra in vizinhas(faixa):
            r = matriz.get((um, outra, periodo))
            if r and r[0] != classe:
                alternativas.add(r[0])

        if alternativas:
            confianca = "Ressalva"
            alternativa = " / ".join(sorted(alternativas))
            motivo = ("Declividade proxima da fronteira: na faixa vizinha a "
                      "recomendacao seria outra")
        else:
            confianca, alternativa, motivo = "Boa", None, None

        # talhao muito dividido entre solos tambem enfraquece a classificacao
        if pct is not None and pct < 60 and confianca == "Boa":
            confianca = "Ressalva"
            motivo = ("Talhao dividido entre unidades de manejo: a "
                      "predominante cobre so %.0f%% da area" % pct)

        linhas.append([chave, safra, data, periodo, um, faixa, mediana, pct,
                       classe, condicao, confianca, alternativa, motivo, agora])
        por_classe[classe] += 1
        por_confianca[confianca] += 1

    if not linhas:
        raise RuntimeError("nenhum talhao classificado - abortando sem gravar")

    criar()
    print("\nregravando a tabela...")
    arcpy.management.TruncateTable(TB_SAIDA)
    campos = [c[0] for c in CAMPOS]
    with arcpy.da.InsertCursor(TB_SAIDA, campos) as ins:
        for l in linhas:
            ins.insertRow(l)

    print("\n=== resultado ===")
    print("  talhoes classificados : %d" % len(linhas))
    print("  sem data de plantio   : %d" % sem_plantio)
    print("  sem faixa de declividade: %d" % sem_faixa)
    print("  sem regra na matriz   : %d" % sem_regra)

    print("\n  classe da epoca de plantio:")
    for classe, n in por_classe.most_common():
        print("    %-26s %5d  (%.1f%%)"
              % (classe, n, 100.0 * n / len(linhas)))

    print("\n  confianca da classificacao:")
    for c, n in por_confianca.most_common():
        print("    %-10s %5d  (%.1f%%)" % (c, n, 100.0 * n / len(linhas)))

    print("\ntabela: %s" % TB_SAIDA)
    print("proximo passo: incluir na VW_RELATORIO_FALHAS.")


if __name__ == "__main__":
    classificar()
