# -*- coding: utf-8 -*-
"""
Carga do cadastro das estacoes Zeus para ATVOSPUBLICADOR.ESTACOES_ZEUS.

Origem: dl-bq-prd.bronze_zeus.pics, lida pela conexao BigQuery do ArcGIS que
fica no OneDrive do Joao - a mesma do percentual oficial e do atualizar_base.
Ate 02/10/2026 vinha de uma planilha exportada a mao.

So o cadastro. O diario e do carga_monitoramento_zeus.py, que ainda le a
planilha do Excel: o time de dados esta trabalhando na origem definitiva.

O nome vem no padrao UNIDADE_FAZENDA (ex.: USL_320013), entao a unidade e o
codigo da fazenda saem dali. O STATUS decide quais estacoes entram no vinculo
talhao-estacao, e e ele que costuma mudar de uma carga para outra: por isso a
simulacao mostra, estacao por estacao, o que mudaria.

Substituicao total, com as protecoes do protecao.py: nao grava se a origem
vier vazia ou com menos da metade das linhas do banco, e devolve as linhas
anteriores se a gravacao falhar.

Depois de gravar, rode o vincular_talhao_estacao.py: o vinculo usa o status e
a posicao das estacoes.

Sem --gravar, so simula: le, compara com o banco e mostra o que mudaria.

Uso:
  propy -u src\\carga\\carga_estacoes_zeus.py            (simula)
  propy -u src\\carga\\carga_estacoes_zeus.py --gravar   (grava)

Codigo de saida: 0 = ok | 1 = nada gravado (conferencia ou erro)

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import re
import sys

import arcpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protecao import motivo_para_nao_gravar, regravar  # noqa: E402

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_ESTACOES = os.path.join(DATASET, "ATVOSPUBLICADOR.ESTACOES_ZEUS")

# a mesma conexao do carga_status_report.py: so funciona na conta do Joao, e a
# tabela precisa ser aberta pelo nome completo (listar o dataset trava o arcpy)
BQ = (r"C:\Users\joao.fgromboni\OneDrive - Atvos\Documentos\ArcGIS\Projects"
      r"\gdb_atvos\BigQuery-dl-bq-prd-gold_arcgis.sde")
ORIGEM = BQ + r"\dl-bq-prd.bronze_zeus.pics"

CAMPOS_ORIGEM = ["picId", "clientId", "name", "lat", "lon", "location",
                 "status", "recordstamp"]

CAMPOS_ESTACAO = [
    ("PIC_ID", "LONG", None), ("CLIENT_ID", "LONG", None),
    ("NOME", "TEXT", 40), ("UNIDADE", "TEXT", 10),
    ("COD_FAZENDA", "TEXT", 10), ("LOCALIZACAO", "TEXT", 80),
    ("STATUS", "TEXT", 20), ("LAT", "DOUBLE", None), ("LON", "DOUBLE", None),
    ("RECORDSTAMP", "DATE", None), ("DATA_CARGA", "DATE", None),
]

# diferenca de coordenada a partir da qual a estacao mudou de lugar de fato
# (0,00001 grau e cerca de 1 m)
TOLERANCIA_GRAUS = 1e-5

# ---------------------------------------------------------------------------


def partes_do_nome(nome):
    """USL_320013 -> ('USL', '320013'). Tolera sufixos: 'URC_219053 II'."""
    texto = str(nome or "").strip()
    if "_" not in texto:
        return None, None
    unidade, resto = texto.split("_", 1)
    digitos = re.match(r"\s*(\d+)", resto)
    return unidade.strip().upper(), (digitos.group(1) if digitos else None)


def diferencas(novas, atuais, tolerancia=TOLERANCIA_GRAUS):
    """O que mudaria, comparando por PIC_ID.

    novas e atuais: {pic_id: {"NOME", "STATUS", "LAT", "LON"}}
    """
    saida = {"novas": [], "sumiram": [], "status": [], "posicao": [], "nome": []}
    for pic in sorted(set(novas) - set(atuais)):
        saida["novas"].append(novas[pic]["NOME"])
    for pic in sorted(set(atuais) - set(novas)):
        saida["sumiram"].append(atuais[pic]["NOME"])
    for pic in sorted(set(novas) & set(atuais)):
        nova, atual = novas[pic], atuais[pic]
        if (nova["STATUS"] or "") != (atual["STATUS"] or ""):
            saida["status"].append((nova["NOME"], atual["STATUS"], nova["STATUS"]))
        if (nova["NOME"] or "") != (atual["NOME"] or ""):
            saida["nome"].append((atual["NOME"], nova["NOME"]))
        for eixo in ("LAT", "LON"):
            if nova[eixo] is None or atual[eixo] is None:
                continue
            if abs(nova[eixo] - atual[eixo]) > tolerancia:
                saida["posicao"].append((nova["NOME"],
                                         (atual["LAT"], atual["LON"]),
                                         (nova["LAT"], nova["LON"])))
                break
    return saida


def criar():
    if arcpy.Exists(FC_ESTACOES):
        return
    print("criando ESTACOES_ZEUS")
    sr = arcpy.Describe(DATASET).spatialReference
    arcpy.management.CreateFeatureclass(DATASET, "ESTACOES_ZEUS", "POINT",
                                        spatial_reference=sr)
    for nome, tipo, tam in CAMPOS_ESTACAO:
        if tam:
            arcpy.management.AddField(FC_ESTACOES, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(FC_ESTACOES, nome, tipo)
    arcpy.management.AddIndex(FC_ESTACOES, ["PIC_ID"], "IDX_EST_PICID")
    arcpy.management.AddIndex(FC_ESTACOES, ["COD_FAZENDA"], "IDX_EST_FAZENDA")


def ler_origem():
    """{pic_id: dados da estacao} lido do BigQuery."""
    campos = {f.name for f in arcpy.ListFields(ORIGEM)}
    faltando = [c for c in CAMPOS_ORIGEM if c not in campos]
    if faltando:
        raise RuntimeError("campos ausentes na origem: %s" % faltando)

    estacoes = {}
    with arcpy.da.SearchCursor(ORIGEM, CAMPOS_ORIGEM) as cur:
        for pic, cliente, nome, lat, lon, local, status, stamp in cur:
            unidade, fazenda = partes_do_nome(nome)
            estacoes[pic] = {
                "PIC_ID": pic, "CLIENT_ID": cliente, "NOME": nome,
                "UNIDADE": unidade, "COD_FAZENDA": fazenda,
                "LOCALIZACAO": local, "STATUS": status, "LAT": lat, "LON": lon,
                "RECORDSTAMP": stamp,
            }
    return estacoes


def ler_banco():
    """{pic_id: dados da estacao} como esta hoje no SQL Server."""
    if not arcpy.Exists(FC_ESTACOES):
        return {}
    estacoes = {}
    campos = ["PIC_ID", "NOME", "STATUS", "LAT", "LON"]
    with arcpy.da.SearchCursor(FC_ESTACOES, campos) as cur:
        for linha in cur:
            estacoes[linha[0]] = dict(zip(campos, linha))
    return estacoes


def mostrar(mudancas):
    rotulos = [("novas", "estacoes novas"), ("sumiram", "sairam da origem"),
               ("status", "mudaram de status"), ("posicao", "mudaram de lugar"),
               ("nome", "mudaram de nome")]
    if not any(mudancas[chave] for chave, _ in rotulos):
        print("nada mudou desde a ultima carga")
        return
    for chave, rotulo in rotulos:
        itens = mudancas[chave]
        if not itens:
            continue
        print("%s: %d" % (rotulo, len(itens)))
        for item in itens:
            if chave == "status":
                print("  %-16s %s -> %s" % item)
            elif chave == "posicao":
                print("  %-16s (%.5f, %.5f) -> (%.5f, %.5f)"
                      % (item[0], item[1][0], item[1][1], item[2][0], item[2][1]))
            elif chave == "nome":
                print("  %s -> %s" % item)
            else:
                print("  %s" % item)


def carregar(gravar):
    print("=" * 64)
    print(" CADASTRO DAS ESTACOES ZEUS - %s"
          % ("GRAVACAO" if gravar else "SIMULACAO (use --gravar para gravar)"))
    print("=" * 64)
    print("origem: %s" % ORIGEM)

    # le tudo ANTES de apagar: falha de conexao nao pode zerar a producao
    novas = ler_origem()
    atuais = ler_banco()
    print("lidas do BigQuery: %d | no banco hoje: %d" % (len(novas), len(atuais)))

    por_status, sem_fazenda = {}, []
    for dados in novas.values():
        por_status[dados["STATUS"]] = por_status.get(dados["STATUS"], 0) + 1
        if not dados["COD_FAZENDA"]:
            sem_fazenda.append(dados["NOME"])
    print("status na origem: %s" % por_status)
    if sem_fazenda:
        print("AVISO: %d estacoes sem codigo de fazenda no nome: %s"
              % (len(sem_fazenda), ", ".join(sorted(sem_fazenda))))

    print()
    mostrar(diferencas(novas, atuais))

    motivo = motivo_para_nao_gravar(len(novas), len(atuais))
    if motivo:
        print("\nNADA FOI GRAVADO: %s" % motivo)
        return 1

    if not gravar:
        print("\nSIMULACAO: nada gravado. Com --gravar, a camada passaria de %d "
              "para %d estacoes." % (len(atuais), len(novas)))
        return 0

    criar()
    agora = datetime.datetime.now()
    nomes = [c[0] for c in CAMPOS_ESTACAO]
    linhas = [[(d["LON"], d["LAT"])]
              + [agora if c == "DATA_CARGA" else d.get(c) for c in nomes]
              for d in novas.values()]
    print("\nregravando o destino...")
    inseridas = regravar(FC_ESTACOES, ["SHAPE@XY"] + nomes, linhas)
    print("inseridas: %d" % inseridas)
    conferir()
    return 0


def conferir():
    print("\n=== conferencia ===")
    total = int(arcpy.management.GetCount(FC_ESTACOES)[0])
    por_status, sem_geometria = {}, 0
    with arcpy.da.SearchCursor(FC_ESTACOES, ["STATUS", "SHAPE@XY"]) as cur:
        for status, xy in cur:
            por_status[status] = por_status.get(status, 0) + 1
            if xy is None or xy[0] is None:
                sem_geometria += 1
    print("  ESTACOES_ZEUS: %d estacoes | status %s" % (total, por_status))
    if sem_geometria:
        print("  AVISO: %d estacoes sem coordenada" % sem_geometria)
    print("  o vinculo talhao-estacao usa o status e a posicao: rode em seguida")
    print("  propy -u src\\processamento\\vincular_talhao_estacao.py")


if __name__ == "__main__":
    sys.exit(carregar("--gravar" in sys.argv))
