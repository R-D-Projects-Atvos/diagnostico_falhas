# -*- coding: utf-8 -*-
"""
Sincroniza os surveys de VANT: monta o staging no SQL Server e corrige o
chavesig na origem, no Portal.

Cria/atualiza:
  ATVOSPUBLICADOR.STG_PORTE_AVALIACAO  - uma linha por TALHAO avaliado
  ATVOSPUBLICADOR.STG_VOO_MISSAO       - uma linha por TALHAO voado
  ATVOSPUBLICADOR.LOG_CHAVESIG_SURVEYS - registro das correcoes no Portal

Ordem de cada survey:
  1. le pai + repeat do Portal
  2. reconstroi o chavesig de cod_fazenda + cod_setor + cod_talhao
  3. grava o staging (independe do que o formulario gravou)
  4. corrige no Portal as linhas divergentes e registra no log

O passo 4 escreve em producao a cada execucao. Por isso o log: toda alteracao
fica com data, valor anterior e valor novo.

Uso: python C:\\temp\\sincronizar_surveys_vant.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import arcpy
from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Table

# saida sem buffer: as mensagens aparecem conforme acontecem
print = functools.partial(print, flush=True)

# Autenticacao: usa a sessao ja logada do ArcGIS Pro, sem usuario nem senha.
# O Pro precisa estar conectado ao geoportal (nao precisa estar aberto).
PORTAL = "pro"

BASE = "https://geoportal.atvos.com/server/rest/services/Hosted"
SRV_PORTE = BASE + "/service_a170152fc3934e68be6a4fcbc6808bd8/FeatureServer"
SRV_MISSAO = BASE + "/service_ffb97edbaa524ba3872425369a9b214b/FeatureServer"

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
TB_PORTE = "STG_PORTE_AVALIACAO"
TB_VOO = "STG_VOO_MISSAO"
TB_LOG = "LOG_CHAVESIG_SURVEYS"

CORRIGIR_ORIGEM = True     # grava a correcao do chavesig no Portal
LOTE_EDICAO = 500

# Brasilia = -3; Mato Grosso do Sul = -4.
UTC_OFFSET_H = -3

IGNORAR_FAZENDAS = [447045, 440745]

CAMPOS_PORTE = [
    ("CHAVESIG", "TEXT", 14), ("COD_FAZENDA", "TEXT", 10),
    ("COD_SETOR", "TEXT", 10), ("COD_TALHAO", "TEXT", 10),
    ("DT_AVALIACAO", "DATE", None), ("PILOTO", "TEXT", 60),
    ("PORTE_ADEQUADO", "TEXT", 5), ("OBS_CAMPO", "TEXT", 255),
    ("PREVISAO_RETORNO", "DATE", None), ("QTD_TALHOES_INFO", "TEXT", 10),
    ("ID_AVALIACAO", "TEXT", 40), ("DATA_CARGA", "DATE", None),
]

CAMPOS_VOO = [
    ("CHAVESIG", "TEXT", 14), ("COD_FAZENDA", "TEXT", 10),
    ("COD_SETOR", "TEXT", 10), ("COD_TALHAO", "TEXT", 10),
    ("DT_SAIDA", "DATE", None), ("DT_RETORNO", "DATE", None),
    ("DURACAO_H", "DOUBLE", None), ("PILOTO", "TEXT", 60),
    ("VANT", "TEXT", 40), ("TIPO_MISSAO", "TEXT", 30),
    ("RESULTADO_MISSAO", "TEXT", 40), ("OBS_GERAIS", "TEXT", 255),
    ("ID_MISSAO", "TEXT", 40), ("DATA_CARGA", "DATE", None),
]

CAMPOS_LOG = [
    ("DATA_EXEC", "DATE", None), ("SURVEY", "TEXT", 30),
    ("OBJECTID_LINHA", "LONG", None), ("CHAVESIG_ANTES", "TEXT", 20),
    ("CHAVESIG_DEPOIS", "TEXT", 14), ("RESULTADO", "TEXT", 20),
]


def criar(nome, campos, indice="CHAVESIG"):
    caminho = SDE + "\\ATVOSPUBLICADOR." + nome
    if arcpy.Exists(caminho):
        return caminho
    print("criando %s" % nome)
    arcpy.management.CreateTable(SDE, nome)
    for c, tipo, tam in campos:
        if tam:
            arcpy.management.AddField(caminho, c, tipo, field_length=tam)
        else:
            arcpy.management.AddField(caminho, c, tipo)
    if indice:
        arcpy.management.AddIndex(caminho, [indice], "IDX_%s" % nome[:10])
    return caminho


def dominios(camada):
    mapa = {}
    for f in camada.properties.fields:
        dom = f.get("domain")
        if dom and dom.get("type") == "codedValue":
            mapa[f["name"]] = {cv["code"]: cv["name"]
                               for cv in dom["codedValues"]}
    return mapa


def local(ms):
    if ms in (None, ""):
        return None
    return (datetime.datetime.utcfromtimestamp(ms / 1000.0)
            + datetime.timedelta(hours=UTC_OFFSET_H))


def limpa(v):
    return None if v in (None, "") else v


def chavesig(fazenda, setor, talhao):
    partes = []
    for valor, casas in ((fazenda, 6), (setor, 4), (talhao, 4)):
        if valor is None:
            return None
        texto = str(int(valor))
        if len(texto) > casas:
            return None
        partes.append(texto.rjust(casas, "0"))
    return "".join(partes)


def ler_survey(gis, url_srv, campos_pai):
    """Devolve (linhas, dominios, tabela_filho).

    linhas: lista de (atributos_do_pai, atributos_da_linha, chavesig_calculado)
    """
    pai = FeatureLayer(url_srv + "/0", gis=gis)
    filho = Table(url_srv + "/1", gis=gis)
    doms = dominios(pai)

    pais = {}
    for f in pai.query(where="1=1", out_fields=",".join(campos_pai),
                       return_geometry=False).features:
        a = f.attributes
        chave = (a.get("uniquerowid") or "").upper()
        if chave:
            pais[chave] = a

    linhas = []
    for f in filho.query(where="1=1",
                         out_fields="objectid,parentrowid,cod_talhao,chavesig",
                         return_geometry=False).features:
        a = f.attributes
        p = pais.get((a.get("parentrowid") or "").upper())
        if not p:
            continue
        if p.get("cod_fazenda") in IGNORAR_FAZENDAS:
            continue
        chv = chavesig(p.get("cod_fazenda"), p.get("cod_setor"),
                       a.get("cod_talhao"))
        linhas.append((p, a, chv))

    print("  pais: %d | linhas de talhao: %d" % (len(pais), len(linhas)))
    return linhas, doms, filho


def corrigir_origem(filho, linhas, nome_survey, log_caminho, agora):
    """Grava no Portal o chavesig reconstruido, onde divergir."""
    edicoes = [{"attributes": {"objectid": a["objectid"], "chavesig": chv}}
               for _, a, chv in linhas
               if chv and a.get("chavesig") != chv]
    antes = {a["objectid"]: a.get("chavesig") for _, a, _ in linhas}

    if not edicoes:
        print("  origem ja consistente - nada a corrigir")
        return

    print("  corrigindo %d linhas no Portal..." % len(edicoes))
    registros = []
    for i in range(0, len(edicoes), LOTE_EDICAO):
        bloco = edicoes[i:i + LOTE_EDICAO]
        res = filho.edit_features(updates=bloco)
        por_id = {r.get("objectId"): r for r in res.get("updateResults", [])}
        for e in bloco:
            oid = e["attributes"]["objectid"]
            r = por_id.get(oid, {})
            registros.append([agora, nome_survey, oid, antes.get(oid),
                              e["attributes"]["chavesig"],
                              "ok" if r.get("success") else "falha"])

    with arcpy.da.InsertCursor(log_caminho, [c[0] for c in CAMPOS_LOG]) as ins:
        for r in registros:
            ins.insertRow(r)

    ok = sum(1 for r in registros if r[5] == "ok")
    print("  gravadas %d de %d (log em %s)" % (ok, len(registros), TB_LOG))


def sincronizar_porte(gis, log_caminho, agora):
    print("\n=== Avaliacao de Porte ===")
    destino = criar(TB_PORTE, CAMPOS_PORTE)
    campos = ["uniquerowid", "cod_fazenda", "cod_setor", "dt_avaliacao",
              "piloto", "porte_adequado", "obs_campo", "previsao_retorno",
              "qtd_talhoes"]
    linhas, doms, filho = ler_survey(gis, SRV_PORTE, campos)

    arcpy.management.DeleteRows(destino)
    sem_chave = 0
    with arcpy.da.InsertCursor(destino, [c[0] for c in CAMPOS_PORTE]) as ins:
        for p, a, chv in linhas:
            if not chv:
                sem_chave += 1
            ins.insertRow([
                chv, str(p.get("cod_fazenda")), str(p.get("cod_setor")),
                str(a.get("cod_talhao")), local(p.get("dt_avaliacao")),
                doms.get("piloto", {}).get(p.get("piloto"), p.get("piloto")),
                limpa(p.get("porte_adequado")), limpa(p.get("obs_campo")),
                local(p.get("previsao_retorno")), limpa(p.get("qtd_talhoes")),
                p.get("uniquerowid"), agora,
            ])
    print("  staging: %d linhas | sem chavesig: %d" % (len(linhas), sem_chave))

    if CORRIGIR_ORIGEM:
        corrigir_origem(filho, linhas, "porte", log_caminho, agora)


def sincronizar_voo(gis, log_caminho, agora):
    print("\n=== Registro de Missao ===")
    destino = criar(TB_VOO, CAMPOS_VOO)
    campos = ["uniquerowid", "cod_fazenda", "cod_setor", "dt_saida",
              "dt_retorno", "piloto", "vant_id", "tipo_missao",
              "resultado_missao", "obs_gerais"]
    linhas, doms, filho = ler_survey(gis, SRV_MISSAO, campos)

    arcpy.management.DeleteRows(destino)
    sem_chave = 0
    with arcpy.da.InsertCursor(destino, [c[0] for c in CAMPOS_VOO]) as ins:
        for p, a, chv in linhas:
            if not chv:
                sem_chave += 1
            saida, retorno = local(p.get("dt_saida")), local(p.get("dt_retorno"))
            dur = None
            if saida and retorno:
                dur = round((retorno - saida).total_seconds() / 3600.0, 2)
            ins.insertRow([
                chv, str(p.get("cod_fazenda")), str(p.get("cod_setor")),
                str(a.get("cod_talhao")), saida, retorno, dur,
                doms.get("piloto", {}).get(p.get("piloto"), p.get("piloto")),
                doms.get("vant_id", {}).get(p.get("vant_id"), p.get("vant_id")),
                doms.get("tipo_missao", {}).get(p.get("tipo_missao"),
                                                p.get("tipo_missao")),
                doms.get("resultado_missao", {}).get(p.get("resultado_missao"),
                                                     p.get("resultado_missao")),
                limpa(p.get("obs_gerais")), p.get("uniquerowid"), agora,
            ])
    print("  staging: %d linhas | sem chavesig: %d" % (len(linhas), sem_chave))

    if CORRIGIR_ORIGEM:
        corrigir_origem(filho, linhas, "missao", log_caminho, agora)


def conferir():
    piloto = ["32012700010004", "32012700010005",
              "32012700010006", "32012700010007"]
    for nome, campos in ((TB_VOO, ["CHAVESIG", "DT_SAIDA", "TIPO_MISSAO",
                                   "DURACAO_H", "PILOTO"]),
                         (TB_PORTE, ["CHAVESIG", "DT_AVALIACAO",
                                     "PORTE_ADEQUADO", "PILOTO"])):
        caminho = SDE + "\\ATVOSPUBLICADOR." + nome
        campo = arcpy.AddFieldDelimiters(caminho, "CHAVESIG")
        onde = "%s IN (%s)" % (campo, ",".join("'%s'" % p for p in piloto))
        print("\n=== %s - area piloto ===" % nome)
        with arcpy.da.SearchCursor(caminho, campos, onde) as cur:
            for linha in sorted(cur, key=lambda r: str(r[0])):
                print("  " + " | ".join(str(v) for v in linha))


if __name__ == "__main__":
    print("conectando pela sessao do ArcGIS Pro...")
    conexao = GIS(PORTAL)
    print("conectado como:", conexao.users.me.username)
    print("portal:", conexao.properties.portalHostname)
    print("corrigir origem no Portal:", CORRIGIR_ORIGEM)

    log = criar(TB_LOG, CAMPOS_LOG, indice="DATA_EXEC")
    momento = datetime.datetime.now()

    sincronizar_porte(conexao, log, momento)
    sincronizar_voo(conexao, log, momento)
    conferir()
