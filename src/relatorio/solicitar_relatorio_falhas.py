# -*- coding: utf-8 -*-
"""
Gera, sob demanda, o relatorio de falhas de UMA fazenda.

Feito para quem opera pelo servidor: dois cliques no
GERAR_RELATORIO_FALHAS.bat, o codigo da fazenda, a conferencia do que foi
encontrado e o PDF, numa pasta que se abre sozinha no fim.

O relatorio em si continua sendo feito pelo gerar_relatorio_falhas.py, o
mesmo do lote. Este script so pergunta, confere e chama o gerador: qualquer
melhoria no relatorio vale para os dois caminhos.

Cada geracao vai para uma pasta propria, por usuario e por data e hora. No
servidor, uma conta nao consegue regravar arquivo criado por outra; na pasta
padrao do gerador (fazenda_data), gerar a mesma fazenda que um colega no
mesmo dia falharia no meio.

Passo a passo: D:\\GEO\\CODIGOS\\LEIA-ME_RELATORIO_FALHAS.md

Uso: duplo clique em D:\\GEO\\CODIGOS\\GERAR_RELATORIO_FALHAS.bat
     ou  python -u solicitar_relatorio_falhas.py [fazenda]

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import sys

print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

# Contas que podem gerar. Nao e controle de acesso - todas sao
# administradoras do servidor -, e sim para ninguem gerar relatorio por
# engano. Para liberar alguem, acrescente a conta do Windows aqui.
USUARIOS_LIBERADOS = {
    "joao.fgromboni",
    "mateusl.silva",
    "leonardo.oalves",
    "rafael.miranda",
}

PASTA_SOB_DEMANDA = r"D:\GEO\FALHAS\sob_demanda"
PASTA_LOGS = r"D:\GEO\LOGS"


def numero(v):
    """O ArcSDESQLExecute devolve numero ora como numero, ora como texto."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return float(str(v).replace(",", "."))


def plural(n, singular, varios):
    return "%d %s" % (n, singular if n == 1 else varios)


def perguntar(texto):
    """input() que tolera a entrada fechando no meio (janela fechada, Ctrl+Z)
    e a marca de BOM que alguns terminais poem na frente do que foi digitado:
    sem isso, um "S" chegava como "\\ufeffS" e a pergunta nao saia do lugar."""
    try:
        return input(texto).replace("﻿", "").strip()
    except EOFError:
        return None


def sim(pergunta):
    while True:
        resposta = perguntar("%s (S/N): " % pergunta)
        if resposta is None:
            return False
        if resposta.upper() in ("S", "N"):
            return resposta.upper() == "S"


def ler_codigo(argumento):
    if argumento:
        return argumento.strip()
    return perguntar("\nCodigo da fazenda (6 digitos) - ENTER para sair: ") or ""


def resumo_da_fazenda(cod):
    """O que o relatorio vai encontrar, lido da mesma view que o gerador usa.

    Mostrado ANTES de gerar: um digito trocado produz o relatorio de outra
    fazenda sem erro nenhum."""
    r = "FALHA_PCT IS NOT NULL AND AREA_HA > 0"
    rl = r + " AND TEM_LINHAS = 1"
    sql = ("SELECT MAX(FAZENDA), MAX(UNIDADE), COUNT(*), "
           "SUM(CASE WHEN {r} THEN 1 ELSE 0 END), "
           "SUM(CASE WHEN TEM_LINHAS = 1 THEN 1 ELSE 0 END), "
           "SUM(CASE WHEN {r} THEN FALHA_PCT * AREA_HA END) "
           "  / NULLIF(SUM(CASE WHEN {r} THEN AREA_HA END), 0), "
           "SUM(CASE WHEN {rl} THEN FALHA_PCT * AREA_HA END) "
           "  / NULLIF(SUM(CASE WHEN {rl} THEN AREA_HA END), 0), "
           "MAX(DT_PUBLICACAO_PIMS) "
           "FROM {v} WHERE COD_FAZENDA = '{c}'").format(
               r=r, rl=rl, v=gerador.VIEW, c=cod)
    linha = arcpy.ArcSDESQLExecute(gerador.SDE).execute(sql)
    if isinstance(linha, list) and linha and isinstance(linha[0], list):
        linha = linha[0]
    (nome, unidade, total, resultado, com_linhas,
     media_fazenda, media_linhas, publicacao) = linha
    return {"nome": (nome or "").strip(), "unidade": (unidade or "").strip(),
            "total": int(numero(total) or 0),
            "resultado": int(numero(resultado) or 0),
            "linhas": int(numero(com_linhas) or 0),
            "media_fazenda": numero(media_fazenda),
            "media_linhas": numero(media_linhas),
            "publicacao": publicacao}


def mostrar(cod, info):
    print("\n  Fazenda   : %s - %s (%s)" % (cod, info["nome"] or "?",
                                           info["unidade"] or "?"))
    print("  Talhoes   : %s com resultado de falhas publicado no PIMS"
          % plural(info["resultado"], "talhao", "talhoes"))
    if info["resultado"] == 0:
        return

    # o gerador so poe no relatorio os talhoes com linhas, quando existem; a
    # media que o relatorio mostra e a desses talhoes, nao a da fazenda toda
    if info["linhas"]:
        print("  Relatorio : %s com linhas de falha carregadas"
              % plural(info["linhas"], "talhao", "talhoes"))
        media = info["media_linhas"]
    else:
        print("  Relatorio : %s, SEM mapa - a fazenda nao tem linhas de falha "
              "carregadas" % plural(info["total"], "talhao", "talhoes"))
        media = info["media_fazenda"]

    if media is not None:
        texto = "  Falhas    : %.2f%% nos talhoes do relatorio" % media
        if info["linhas"] and info["media_fazenda"] is not None:
            texto += " (%.2f%% na fazenda toda)" % info["media_fazenda"]
        print(texto)
        print("              meta de %.1f%%: %s" % (
            gerador.META_PCT,
            "ACIMA da meta" if media > gerador.META_PCT else "dentro da meta"))

    publicacao = gerador.data(info["publicacao"])
    print("  PIMS      : ultima publicacao em %s"
          % ("-" if publicacao.startswith("&") else publicacao))


def gerar(cod, usuario):
    """Chama o gerador numa pasta que so esta execucao usa."""
    pasta = os.path.join(PASTA_SOB_DEMANDA, usuario,
                         datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(pasta)
    gerador.PASTA_SAIDA = pasta
    html = gerador.gerar_uma(cod)
    pdf = os.path.splitext(html)[0] + ".pdf"
    return os.path.dirname(html), (pdf if os.path.isfile(pdf) else None)


def registrar(usuario, cod, situacao, detalhe=""):
    """Uma linha por tentativa, num arquivo por usuario: no servidor, uma
    conta nao consegue acrescentar linha em arquivo criado por outra."""
    caminho = os.path.join(PASTA_LOGS,
                           "relatorio_falhas_sob_demanda_%s.log" % usuario)
    try:
        with open(caminho, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\t%s\n" % (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                cod, situacao, detalhe))
    except OSError as erro:
        print("  (aviso: registro nao gravado em %s: %s)" % (caminho, erro))


def atender(cod, usuario, teste):
    if not (cod.isdigit() and len(cod) == 6):
        print("  codigo invalido: use os 6 digitos da fazenda, ex.: 320127")
        return

    info = resumo_da_fazenda(cod)
    if info["total"] == 0:
        print("  fazenda %s nao encontrada na base do relatorio. "
              "Confira o codigo." % cod)
        registrar(usuario, cod, "NAO_ENCONTRADA")
        return

    mostrar(cod, info)
    if info["resultado"] == 0:
        print("\n  Esta fazenda nao tem resultado de falhas publicado no PIMS: "
              "nao ha o que gerar.")
        registrar(usuario, cod, "SEM_RESULTADO")
        return
    if not sim("\nGerar o relatorio?"):
        registrar(usuario, cod, "CANCELADO")
        return

    print()
    pasta, pdf = gerar(cod, usuario)
    registrar(usuario, cod, "GERADO" if pdf else "GERADO_SEM_PDF", pasta)

    print("\n" + "-" * 64)
    print(" PRONTO - o relatorio esta nesta pasta:")
    print(" %s" % pasta)
    print(" PDF: %s" % (os.path.basename(pdf) if pdf else
                        "nao gerado - abra o HTML e imprima com Ctrl+P"))
    print("-" * 64)

    if not teste:          # --teste nao abre janela
        os.startfile(pasta)


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    teste = "--teste" in sys.argv
    usuario = os.environ.get("USERNAME", "").strip().lower()

    print("=" * 64)
    print(" RELATORIO DE FALHAS DE PLANTIO - sob demanda")
    print(" usuario Windows: %s" % usuario)
    print("=" * 64)

    if usuario not in USUARIOS_LIBERADOS:
        print("\nEsta conta nao esta liberada para gerar relatorios.")
        print("Para liberar, inclua '%s' em USUARIOS_LIBERADOS, no topo de" % usuario)
        print("%s" % os.path.abspath(__file__))
        return 1

    print("\ncarregando o ArcGIS (leva uns 30 segundos)...")
    global arcpy, gerador
    try:
        import arcpy
        import gerar_relatorio_falhas as gerador
    except Exception as erro:
        print("\nNao consegui carregar o ArcGIS: %s" % erro)
        print("Abra o ArcGIS Pro com a sua conta, confirme que esta logado e "
              "tente de novo.")
        return 1

    unica = argumentos[0] if argumentos else None
    while True:
        cod = ler_codigo(unica)
        if not cod:
            break
        try:
            atender(cod, usuario, teste)
        except Exception as erro:
            print("\nERRO na fazenda %s: %s" % (cod, erro))
            print("A mensagem tambem ficou no registro em %s." % PASTA_LOGS)
            registrar(usuario, cod, "ERRO", str(erro).replace("\n", " "))
        if unica or not sim("\nGerar outro relatorio?"):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
