# -*- coding: utf-8 -*-
"""
Testes das partes da carga de linhas que nao dependem do banco: achar as
entregas na pasta, descompactar, separar a fazenda da borda, decidir se carrega,
nome do lote, voo e mover para CARREGADAS.

Uso: propy -u testes\\testar_linhas_falha.py
"""

import datetime
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "carga"))
import carga_linhas_falha as c  # noqa: E402

falhas = []


def confere(nome, condicao):
    print("  %-4s %s" % ("ok" if condicao else "FALHA", nome))
    if not condicao:
        falhas.append(nome)


def criar(caminho, conteudo="x"):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w") as f:
        f.write(conteudo)


base = tempfile.mkdtemp(prefix="teste_linhas_")
try:
    pasta = os.path.join(base, "LINHAS")
    os.makedirs(pasta)
    with zipfile.ZipFile(os.path.join(pasta, "vectors-gaps.zip"), "w") as zf:
        for ext in ("shp", "shx", "dbf", "prj"):
            zf.writestr("FALHAS.%s" % ext, "x")
    criar(os.path.join(pasta, "entrega 2", "sub", "FALHAS.shp"))
    criar(os.path.join(pasta, "entrega 2", "sub", "FALHAS.dbf"))
    criar(os.path.join(pasta, "solta.shp"))
    criar(os.path.join(pasta, "solta.dbf"))
    criar(os.path.join(pasta, "solta.shp.xml"))
    criar(os.path.join(pasta, "orfao.dbf"))
    criar(os.path.join(pasta, "desktop.ini"))
    criar(os.path.join(pasta, "~$temporario.zip"))
    criar(os.path.join(pasta, "vazia", "leia.txt"))
    criar(os.path.join(pasta, "CARREGADAS", "320127_x", "FALHAS.shp"))

    print("entregas_pendentes")
    entregas = {e["nome"]: e for e in c.entregas_pendentes(pasta)}
    confere("acha zip, pasta com shp e shp solto",
            set(entregas) == {"vectors-gaps.zip", "entrega 2", "solta.shp"})
    confere("tipos certos", (entregas["vectors-gaps.zip"]["tipo"],
                             entregas["entrega 2"]["tipo"],
                             entregas["solta.shp"]["tipo"]) == ("zip", "pasta", "shapefile"))
    confere("shp solto leva os irmaos",
            sorted(os.path.basename(i) for i in entregas["solta.shp"]["itens"])
            == ["solta.dbf", "solta.shp", "solta.shp.xml"])
    confere("ignora CARREGADAS, pasta sem shp, dbf sem shp e temporarios",
            not {"CARREGADAS", "vazia", "orfao.dbf", "desktop.ini",
                 "~$temporario.zip"} & set(entregas))

    print("\ntrazer_para_temp / extrair_zip")
    temp = os.path.join(base, "temp")
    shps = c.trazer_para_temp(entregas["vectors-gaps.zip"], os.path.join(temp, "1"))
    confere("zip descompactado e shp achado", [os.path.basename(s) for s in shps] == ["FALHAS.shp"])
    shps = c.trazer_para_temp(entregas["entrega 2"], os.path.join(temp, "2"))
    confere("pasta copiada com subpasta", len(shps) == 1 and os.path.isfile(shps[0]))
    shps = c.trazer_para_temp(entregas["solta.shp"], os.path.join(temp, "3"))
    confere("shp solto copiado", [os.path.basename(s) for s in shps] == ["solta.shp"])
    confere("original continua na pasta", os.path.isfile(os.path.join(pasta, "solta.shp")))
    ruim = os.path.join(base, "ruim.zip")
    with zipfile.ZipFile(ruim, "w") as zf:
        zf.writestr("../fora.shp", "x")
    try:
        c.extrair_zip(ruim, os.path.join(temp, "4"))
        confere("zip com caminho para fora e recusado", False)
    except ValueError:
        confere("zip com caminho para fora e recusado",
                not os.path.exists(os.path.join(temp, "fora.shp")))

    print("\nseparar_por_fazenda")
    mantidas, descartadas = c.separar_por_fazenda({"320127": 58446, "320128": 120})
    confere("vizinha com menos de 1% sai", mantidas == {"320127": 58446}
            and descartadas == {"320128": 120})
    mantidas, _ = c.separar_por_fazenda({"320127": 600, "320128": 400})
    confere("duas fazendas grandes ficam", set(mantidas) == {"320127", "320128"})
    confere("nada com talhao: nada fica", c.separar_por_fazenda({}) == ({}, {}))

    print("\nmotivo_para_nao_carregar")
    confere("vazio nao carrega", c.motivo_para_nao_carregar(0, 0, {}) is not None)
    confere("nada em talhao nao carrega",
            c.motivo_para_nao_carregar(100, 100, {}) is not None)
    confere("mais da metade fora nao carrega",
            c.motivo_para_nao_carregar(100, 51, {"320127": 49}) is not None)
    confere("piloto (0,5% fora) carrega",
            c.motivo_para_nao_carregar(58765, 319, {"320127": 58446}) is None)

    print("\nnome_lote")
    quando = datetime.datetime(2026, 9, 11, 17, 5, 9)
    confere("fazenda com mais linhas e data da carga",
            c.nome_lote({"320128": 10, "320127": 500}, quando) == "320127_20260911_170509")
    confere("empate: menor codigo", c.nome_lote({"320128": 5, "320127": 5}, quando)
            .startswith("320127_"))

    print("\nultimo_voo")
    dt = datetime.datetime
    missoes = [(dt(2026, 7, 8), "Falhas", "Concluido"),
               (dt(2026, 8, 1), "Falhas ", "Interrompido"),
               (dt(2026, 8, 2), "Porte", "Concluido"),
               (dt(2026, 6, 1), "Falhas", None)]
    confere("mais recente de falhas nao interrompida", c.ultimo_voo(missoes) == dt(2026, 7, 8))
    confere("sem missao: None", c.ultimo_voo([]) is None)

    print("\nresumo_por_talhao e clausula_in")
    linhas = [[None, "000", 1.0, 0.7, "A", "22627"], [None, "000", 2.0, 1.7, "A", "22627"],
              [None, "001", 1.0, None, "B", "22627"]]
    resumo = c.resumo_por_talhao(linhas)
    confere("conta e soma LengthComp", resumo["A"][0] == 2 and abs(resumo["A"][1] - 2.4) < 1e-9
            and resumo["B"] == (1, 0.0))
    confere("aspas escapadas", c.clausula_in("CHAVESIG", ["1", "o'x"]) == "CHAVESIG IN ('1','o''x')")
    confere("blocos", [len(b) for b in c.em_blocos(range(1200), 500)] == [500, 500, 200])

    print("\nmover_para_carregadas e pasta_entrada")
    destino = c.mover_para_carregadas(entregas["solta.shp"], pasta, "320127_20260911_170509", "joao")
    confere("move os irmaos para CARREGADAS/<lote>_<usuario>",
            sorted(os.listdir(destino)) == ["solta.dbf", "solta.shp", "solta.shp.xml"]
            and not os.path.exists(os.path.join(pasta, "solta.shp")))
    confere("o que foi movido sai das pendentes",
            "solta.shp" not in {e["nome"] for e in c.entregas_pendentes(pasta)})
    confere("primeira pasta que abre",
            c.pasta_entrada([os.path.join(base, "nao_existe"), pasta]) == pasta)
    confere("nenhuma abre: None", c.pasta_entrada([os.path.join(base, "nao_existe")]) is None)
finally:
    shutil.rmtree(base, ignore_errors=True)

print("\nRESULTADO: %s" % ("TUDO OK" if not falhas else "%d FALHA(S): %s" % (len(falhas), falhas)))
sys.exit(1 if falhas else 0)
