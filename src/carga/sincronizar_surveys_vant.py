# -*- coding: utf-8 -*-
"""
Sincroniza os surveys de VANT: monta o staging no SQL Server e corrige o
chavesig na origem, no Portal.

Cria/atualiza:
  ATVOSPUBLICADOR.STG_PORTE_AVALIACAO  - uma linha por TALHAO avaliado
  ATVOSPUBLICADOR.STG_VOO_MISSAO       - uma linha por TALHAO voado
  ATVOSPUBLICADOR.LOG_CHAVESIG_SURVEYS - registro das correcoes no Portal

Surveys de producao (confirmados em 11/09/2026):
  "Avaliacao de Porte Cana - Pilotos ATVOS"  item b2b4a34c14f24f2a9ca3a22a43154ad5
  "Registro de Missao - VANT"                item 55646b00864c4d458a5a8e4d0aa1d289
  porte com lista de talhoes por GPS         ver SRV_PORTE_GPS

Ordem de cada survey:
  1. le pai + repeat do Portal
  2. define o chavesig de cada linha de talhao:
     - survey com lista de talhoes por GPS: a chavesig vem da escolha do
       piloto, ja pronta no repeat, uma por talhao. Nada a remontar.
     - survey antigo: reconstroi de cod_fazenda + cod_setor do pai mais o
       cod_talhao do repeat - e portanto refem do setor digitado no pai.
  3. confere o que foi lido contra o staging atual - so entao apaga e regrava
  4. corrige no Portal as linhas divergentes e registra no log

O passo 4 escreve em producao a cada execucao. Por isso o log: toda alteracao
fica com data, valor anterior e valor novo. Ele nao roda no survey da lista por
GPS: ali a chave e a escolha do piloto, nao ha o que corrigir.

Sem --gravar, so simula: le o Portal, mostra quantas linhas iriam para o
staging e quantas seriam corrigidas no Portal, e nao grava nada em lugar
nenhum.

Uso:
  propy -u src\\carga\\sincronizar_surveys_vant.py            (simula)
  propy -u src\\carga\\sincronizar_surveys_vant.py --gravar   (grava)

Codigo de saida: 0 = ok | 1 = algum survey nao foi gravado (conferencia ou erro)

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import re
import sys

import arcpy
from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protecao import motivo_para_nao_gravar, regravar  # noqa: E402

# saida sem buffer: as mensagens aparecem conforme acontecem
print = functools.partial(print, flush=True)

# Autenticacao: usa a sessao ja logada do ArcGIS Pro, sem usuario nem senha.
# O Pro precisa estar conectado ao geoportal (nao precisa estar aberto).
PORTAL = "pro"

BASE = "https://geoportal.atvos.com/server/rest/services/Hosted"
SRV_PORTE = BASE + "/service_a170152fc3934e68be6a4fcbc6808bd8/FeatureServer"
SRV_MISSAO = BASE + "/service_ffb97edbaa524ba3872425369a9b214b/FeatureServer"

# Survey de porte com lista de talhoes por GPS: o piloto escolhe o talhao entre
# os que estao a 400 m dele, e a chavesig sai da escolha. E survey NOVO, nao
# atualizacao do antigo - os campos sao outros, e publicar por cima apagaria as
# avaliacoes ja registradas. Por isso os dois sao lidos, para o mesmo staging.
#
# Preencha com a URL do FeatureServer depois de publicar, no formato
#   BASE + "/service_<id>/FeatureServer"
# Vazio: ignorado, e o script se comporta exatamente como antes.
SRV_PORTE_GPS = ""

CHAVE_14 = re.compile(r"^\d{14}$")

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
    # Por TALHAO, e so o survey com lista por GPS os preenche: nas avaliacoes
    # do survey antigo ficam nulos, porque a altura nunca foi coletada por
    # talhao. O PORTE_ADEQUADO acima continua sendo o veredito da AVALIACAO
    # inteira, como sempre foi.
    ("ALTURA_M", "DOUBLE", None), ("PORTE_TALHAO", "TEXT", 10),
    ("OBS_TALHAO", "TEXT", 255),
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


def caminho(nome):
    return SDE + "\\ATVOSPUBLICADOR." + nome


def acrescentar_campos(destino, nome, campos):
    """Cria as colunas que a tabela ainda nao tem.

    O staging nasceu antes de o formulario coletar altura e porte por talhao.
    Sem isto, acrescentar um campo na lista acima nao criaria coluna nenhuma -
    o criar() saia pela porta so por a tabela existir - e o dado coletado no
    campo seria descartado calado na gravacao."""
    existentes = set(f.name.upper() for f in arcpy.ListFields(destino))
    for c, tipo, tam in campos:
        if c.upper() in existentes:
            continue
        print("  acrescentando coluna %s.%s (%s)" % (nome, c, tipo))
        if tam:
            arcpy.management.AddField(destino, c, tipo, field_length=tam)
        else:
            arcpy.management.AddField(destino, c, tipo)


def criar(nome, campos, indice="CHAVESIG"):
    destino = caminho(nome)
    if arcpy.Exists(destino):
        acrescentar_campos(destino, nome, campos)
        return destino
    print("criando %s" % nome)
    arcpy.management.CreateTable(SDE, nome)
    for c, tipo, tam in campos:
        if tam:
            arcpy.management.AddField(destino, c, tipo, field_length=tam)
        else:
            arcpy.management.AddField(destino, c, tipo)
    if indice:
        arcpy.management.AddIndex(destino, [indice], "IDX_%s" % nome[:10])
    return destino


def contar(nome):
    destino = caminho(nome)
    return int(arcpy.management.GetCount(destino)[0]) if arcpy.Exists(destino) else 0


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


def partes_chave(chave):
    """Fazenda, setor e talhao tirados da propria chavesig.

    As tres colunas de codigo do staging saem daqui, e nao mais do que foi
    digitado no pai: assim nenhuma delas discorda da chave que esta na linha.
    Vem com os zeros a esquerda, no formato da chave (6/4/4)."""
    if not chave:
        return None, None, None
    return chave[:6], chave[6:10], chave[10:]


def consultar_tudo(camada, out_fields):
    """Todas as feicoes da camada, em lotes.

    O servico devolve no maximo maxRecordCount feicoes por consulta, e a
    consulta simples parava ali sem aviso: em 11/09/2026 a missao tinha 1.676
    linhas de talhao e chegavam 1.000. A lista de ids nao tem esse limite, entao
    busca os ids e depois as feicoes de lote em lote - e confere o total."""
    ids = camada.query(where="1=1", return_ids_only=True).get("objectIds") or []
    lote = int(camada.properties.get("maxRecordCount") or 1000)
    feicoes = []
    for i in range(0, len(ids), lote):
        bloco = ids[i:i + lote]
        feicoes.extend(camada.query(object_ids=",".join(str(x) for x in bloco),
                                    out_fields=out_fields,
                                    return_geometry=False).features)
    esperado = camada.query(where="1=1", return_count_only=True)
    if len(feicoes) != esperado:
        raise RuntimeError("lidas %d de %d feicoes em %s - leitura incompleta, "
                           "nada gravado" % (len(feicoes), esperado, camada.url))
    return feicoes


def ler_survey(gis, url_srv, campos_pai, chave_no_repeat=False):
    """Devolve (linhas, dominios, tabela_filho).

    linhas: lista de (atributos_do_pai, atributos_da_linha, chavesig)

    chave_no_repeat=True: a chavesig ja vem pronta no repeat, uma por talhao,
    porque o piloto escolheu o talhao numa lista em vez de digitar codigo. E
    ela que vale - e so se ela faltar o pai volta a ser consultado.
    """
    pai = FeatureLayer(url_srv + "/0", gis=gis)
    filho = Table(url_srv + "/1", gis=gis)
    doms = dominios(pai)

    pais = {}
    for f in consultar_tudo(pai, ",".join(campos_pai)):
        a = f.attributes
        chave = (a.get("uniquerowid") or "").upper()
        if chave:
            pais[chave] = a

    # "*" porque o repeat de cada survey tem campos diferentes: o da lista por
    # GPS traz altura e porte por talhao, o antigo nao.
    linhas = []
    for f in consultar_tudo(filho, "*"):
        a = f.attributes
        p = pais.get((a.get("parentrowid") or "").upper())
        if not p:
            continue
        if p.get("cod_fazenda") in IGNORAR_FAZENDAS:
            continue
        chv = None
        if chave_no_repeat:
            escolhida = (a.get("chavesig") or "").strip()
            if CHAVE_14.match(escolhida):
                chv = escolhida
        if chv is None:
            chv = chavesig(p.get("cod_fazenda"), p.get("cod_setor"),
                           a.get("cod_talhao"))
        linhas.append((p, a, chv))

    print("  pais: %d | linhas de talhao: %d" % (len(pais), len(linhas)))
    return linhas, doms, filho


def corrigir_origem(filho, linhas, nome_survey, log_caminho, agora, gravar):
    """Grava no Portal o chavesig reconstruido, onde divergir."""
    edicoes = [{"attributes": {"objectid": a["objectid"], "chavesig": chv}}
               for _, a, chv in linhas
               if chv and a.get("chavesig") != chv]
    antes = {a["objectid"]: a.get("chavesig") for _, a, _ in linhas}

    if not edicoes:
        print("  origem ja consistente - nada a corrigir")
        return
    if not gravar:
        print("  SIMULACAO: %d linhas seriam corrigidas no Portal" % len(edicoes))
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


def gravar_staging(nome, campos, novas, sem_chave, gravar):
    """Confere antes de apagar. Devolve False se o staging nao foi gravado."""
    atuais = contar(nome)
    print("  staging: %d linhas lidas | no banco: %d | sem chavesig: %d"
          % (len(novas), atuais, sem_chave))
    motivo = motivo_para_nao_gravar(len(novas), atuais)
    if motivo:
        print("  NADA FOI GRAVADO: %s" % motivo)
        return False
    if gravar:
        regravar(criar(nome, campos), [c[0] for c in campos], novas)
        print("  staging regravado")
    return True


def sincronizar_porte(gis, log_caminho, agora, gravar):
    print("\n=== Avaliacao de Porte ===")
    campos = ["uniquerowid", "cod_fazenda", "cod_setor", "dt_avaliacao",
              "piloto", "porte_adequado", "obs_campo", "previsao_retorno",
              "qtd_talhoes"]
    # (nome, url, a chavesig vem do repeat?). Os dois surveys de porte vao para
    # o mesmo staging: o antigo guarda as avaliacoes ja feitas, e e dele que a
    # vw_relatorio_falhas tira o porte das avaliacoes anteriores.
    fontes = [("porte", SRV_PORTE, False)]
    if SRV_PORTE_GPS:
        fontes.append(("porte_gps", SRV_PORTE_GPS, True))

    novas, sem_chave, a_corrigir = [], 0, []
    for nome_survey, url, chave_no_repeat in fontes:
        print("  survey %s%s" % (nome_survey, " - chavesig da lista por GPS"
                                 if chave_no_repeat else " - chavesig do setor do pai"))
        linhas, doms, filho = ler_survey(gis, url, campos, chave_no_repeat)
        for p, a, chv in linhas:
            if not chv:
                sem_chave += 1
            faz, setor, talhao = partes_chave(chv)
            novas.append([
                chv, faz, setor, talhao, local(p.get("dt_avaliacao")),
                doms.get("piloto", {}).get(p.get("piloto"), p.get("piloto")),
                limpa(p.get("porte_adequado")), limpa(p.get("obs_campo")),
                local(p.get("previsao_retorno")), limpa(p.get("qtd_talhoes")),
                p.get("uniquerowid"), agora,
                a.get("altura_m"), limpa(a.get("porte_talhao")),
                limpa(a.get("obs_talhao")),
            ])
        if not chave_no_repeat:
            a_corrigir.append((filho, linhas, nome_survey))

    if not gravar_staging(TB_PORTE, CAMPOS_PORTE, novas, sem_chave, gravar):
        return False
    if CORRIGIR_ORIGEM:
        for filho, linhas, nome_survey in a_corrigir:
            corrigir_origem(filho, linhas, nome_survey, log_caminho, agora, gravar)
    return True


def sincronizar_voo(gis, log_caminho, agora, gravar):
    print("\n=== Registro de Missao ===")
    campos = ["uniquerowid", "cod_fazenda", "cod_setor", "dt_saida",
              "dt_retorno", "piloto", "vant_id", "tipo_missao",
              "resultado_missao", "obs_gerais"]
    linhas, doms, filho = ler_survey(gis, SRV_MISSAO, campos)

    novas, sem_chave = [], 0
    for p, a, chv in linhas:
        if not chv:
            sem_chave += 1
        saida, retorno = local(p.get("dt_saida")), local(p.get("dt_retorno"))
        dur = None
        if saida and retorno:
            dur = round((retorno - saida).total_seconds() / 3600.0, 2)
        faz, setor, talhao = partes_chave(chv)
        novas.append([
            chv, faz, setor, talhao, saida, retorno, dur,
            doms.get("piloto", {}).get(p.get("piloto"), p.get("piloto")),
            doms.get("vant_id", {}).get(p.get("vant_id"), p.get("vant_id")),
            doms.get("tipo_missao", {}).get(p.get("tipo_missao"),
                                            p.get("tipo_missao")),
            doms.get("resultado_missao", {}).get(p.get("resultado_missao"),
                                                 p.get("resultado_missao")),
            limpa(p.get("obs_gerais")), p.get("uniquerowid"), agora,
        ])

    if not gravar_staging(TB_VOO, CAMPOS_VOO, novas, sem_chave, gravar):
        return False
    if CORRIGIR_ORIGEM:
        corrigir_origem(filho, linhas, "missao", log_caminho, agora, gravar)
    return True


def conferir():
    piloto = ["32012700010004", "32012700010005",
              "32012700010006", "32012700010007"]
    for nome, campos in ((TB_VOO, ["CHAVESIG", "DT_SAIDA", "TIPO_MISSAO",
                                   "DURACAO_H", "PILOTO"]),
                         (TB_PORTE, ["CHAVESIG", "DT_AVALIACAO",
                                     "PORTE_ADEQUADO", "PILOTO"])):
        destino = caminho(nome)
        campo = arcpy.AddFieldDelimiters(destino, "CHAVESIG")
        onde = "%s IN (%s)" % (campo, ",".join("'%s'" % p for p in piloto))
        print("\n=== %s - area piloto ===" % nome)
        with arcpy.da.SearchCursor(destino, campos, onde) as cur:
            for linha in sorted(cur, key=lambda r: str(r[0])):
                print("  " + " | ".join(str(v) for v in linha))


def main():
    gravar = "--gravar" in sys.argv
    print("=" * 64)
    print(" SURVEYS DE VANT - %s"
          % ("GRAVACAO" if gravar else "SIMULACAO (use --gravar para gravar)"))
    print("=" * 64)
    print("conectando pela sessao do ArcGIS Pro...")
    conexao = GIS(PORTAL)
    if conexao.users.me is None:
        print("[X] conexao ANONIMA: o ArcGIS Pro nao esta logado no Portal.")
        print("    Sem isso o chavesig nao e corrigido na origem e o staging")
        print("    (STG_PORTE_AVALIACAO / STG_VOO_MISSAO) nao e atualizado.")
        print("    Verifique, na sessao do usuario que roda a tarefa, se o")
        print("    ArcGIS Pro esta aberto e logado no Portal de producao.")
        return 1
    print("conectado como:", conexao.users.me.username)
    print("portal:", conexao.properties.portalHostname)
    print("corrigir origem no Portal:", CORRIGIR_ORIGEM and gravar)

    log = criar(TB_LOG, CAMPOS_LOG, indice="DATA_EXEC") if gravar else None
    momento = datetime.datetime.now()

    ok_porte = sincronizar_porte(conexao, log, momento, gravar)
    ok_voo = sincronizar_voo(conexao, log, momento, gravar)

    if gravar:
        conferir()
    else:
        print("\nSIMULACAO: nada gravado no banco nem no Portal.")
    return 0 if (ok_porte and ok_voo) else 1


if __name__ == "__main__":
    sys.exit(main())
