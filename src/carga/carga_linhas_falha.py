# -*- coding: utf-8 -*-
"""
Carga das linhas de falha da Bem Agro para ATVOSPUBLICADOR.LINHAS_FALHA.

Quem pede o relatorio baixa as linhas da fazenda na Bem Agro e salva em
ENTRADAS\\LINHAS do jeito que vieram: o .zip, a pasta descompactada ou os
arquivos soltos do shapefile. O arquivo nao traz fazenda, talhao nem data -
tudo sai do cruzamento com o inventario.

Para cada entrega encontrada:
  1. copia ou descompacta numa pasta local e procura o shapefile de falhas
     (linhas, com Length e LengthComp);
  2. cruza com a BASE_SAFRA pelo centro de cada linha (ADR 0006);
  3. deixa de fora as linhas sem talhao e as de fazenda vizinha que entraram
     pela borda (menos de FAZENDA_MINIMA_PCT da entrega);
  4. grava as linhas novas e so depois apaga as antigas DOS MESMOS TALHOES
     (ADR 0012). Se a gravacao falhar, as novas saem e as antigas ficam;
  5. refaz o mapa de calor de cada fazenda (mapa_calor_falhas.py);
  6. move a entrega para ENTRADAS\\LINHAS\\CARREGADAS.

Observacoes:
  - O dataset AGRICOLA_ATVOS esta em GCS_WGS_1984 (4326), igual ao shapefile
    da Bem Agro, entao nao ha reprojecao no join.
  - O percentual usa LengthComp, que e o campo que a Bem Agro usa no PIMS. O
    percentual calculado aqui e so conferencia: o relatorio mostra o do PIMS.

Sem --gravar, so simula: le, cruza e mostra o que mudaria, sem mover nada.

Uso:
  propy -u src\\carga\\carga_linhas_falha.py                 (simula)
  propy -u src\\carga\\carga_linhas_falha.py --gravar        (grava)
  propy -u src\\carga\\carga_linhas_falha.py --pasta D:\\x   (outra pasta de entrada)

O relatorio sob demanda (solicitar_relatorio_falhas.py) roda esta carga antes
de conferir a fazenda.

Codigo de saida: 0 = carregou ou nao havia nada | 1 = alguma entrega nao entrou

Geotecnologia / Cartografia - Atvos
"""

import collections
import datetime
import functools
import os
import shutil
import sys
import zipfile

print = functools.partial(print, flush=True)
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "processamento"))

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")
FC_DESTINO = os.path.join(DATASET, "ATVOSPUBLICADOR.LINHAS_FALHA")
FC_INVENTARIO = os.path.join(DATASET, "ATVOSPUBLICADOR.BASE_SAFRA")
NOME_INVENTARIO = "BASE_SAFRA"
TB_PIMS = os.path.join(SDE, "ATVOSPUBLICADOR.Status_Report_VANT")
TB_VOO = os.path.join(SDE, "ATVOSPUBLICADOR.STG_VOO_MISSAO")

# Pasta da biblioteca da Geotecnologia no SharePoint. No servidor ela so esta
# sincronizada no OneDrive do Joao; se a conta que roda tiver a propria
# sincronizacao, vale a dela.
BIBLIOTECA = (r"OneDrive - Atvos\Geotecnologia-03. Geotecnologia Cartografia - Documentos"
              r"\Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\LINHAS")
PASTAS_ENTRADA = [
    os.path.join(os.environ.get("USERPROFILE", ""), BIBLIOTECA),
    os.path.join(r"C:\Users\joao.fgromboni", BIBLIOTECA),
]
NOME_CARREGADAS = "CARREGADAS"
PASTA_TEMP = r"D:\GEO\FALHAS\linhas_temp"

FAZENDA_MINIMA_PCT = 1.0      # abaixo disso, a fazenda entrou pela borda
SEM_TALHAO_MAXIMO_PCT = 50.0  # acima disso, a area nao esta no inventario
ESPACAMENTO_M = 1.5           # so para a conferencia contra o PIMS
TAMANHO_IN = 500              # chavesig por clausula IN

IGNORAR = ("desktop.ini", "thumbs.db")

# ---------------------------------------------------------------------------

CAMPOS = [
    ("CHAVESIG",   "TEXT",   20),
    ("SAFRA_INV",  "TEXT",   10),
    ("CAMADA_INV", "TEXT",   30),
    ("TALHAO_KML", "TEXT",    5),
    ("COMP_M",     "DOUBLE", None),
    ("COMP_OFI_M", "DOUBLE", None),
    ("CLASSE_TAM", "TEXT",   12),
    ("DATA_VOO",   "DATE",  None),
    ("LOTE",       "TEXT",   60),
    ("DATA_CARGA", "DATE",  None),
]


# --------------------------- sem banco --------------------------------------

def fazenda(chave):
    return str(chave)[:6]


def milhar(n):
    return "{:,}".format(int(round(n))).replace(",", ".")


def fmt(valor, casas):
    return "-" if valor is None else "%.*f" % (casas, valor)


def classe_tamanho(m):
    if m < 0.5:
        return "< 0,5 m"
    if m < 1.0:
        return "0,5 a 1 m"
    if m < 2.0:
        return "1 a 2 m"
    if m < 5.0:
        return "2 a 5 m"
    return "> 5 m"


def pasta_entrada(candidatas=None):
    """A primeira pasta de entrada que esta conta consegue abrir, ou None."""
    for pasta in candidatas or PASTAS_ENTRADA:
        try:
            os.listdir(pasta)
            return pasta
        except OSError:
            continue
    return None


def entregas_pendentes(pasta):
    """O que foi salvo na pasta e ainda nao foi carregado.

    Cada entrega e um .zip, uma pasta com shapefile dentro ou um .shp solto
    com os arquivos irmaos (.dbf, .shx...). A pasta CARREGADAS fica de fora."""
    nomes = sorted(os.listdir(pasta))
    entregas = []
    for nome in nomes:
        caminho = os.path.join(pasta, nome)
        minusculo = nome.lower()
        if (nome.upper() == NOME_CARREGADAS or minusculo in IGNORAR
                or nome.startswith(("~", "."))):
            continue
        if os.path.isdir(caminho):
            if shapefiles(caminho):
                entregas.append({"nome": nome, "tipo": "pasta",
                                 "caminho": caminho, "itens": [caminho]})
        elif minusculo.endswith(".zip"):
            entregas.append({"nome": nome, "tipo": "zip",
                             "caminho": caminho, "itens": [caminho]})
        elif minusculo.endswith(".shp"):
            base = minusculo[:-4] + "."
            irmaos = [os.path.join(pasta, n) for n in nomes
                      if n.lower().startswith(base)
                      and not os.path.isdir(os.path.join(pasta, n))]
            entregas.append({"nome": nome, "tipo": "shapefile",
                             "caminho": caminho, "itens": irmaos})
    return entregas


def shapefiles(pasta):
    return sorted(os.path.join(raiz, f) for raiz, _, arquivos in os.walk(pasta)
                  for f in arquivos if f.lower().endswith(".shp"))


def extrair_zip(caminho, destino):
    """Descompacta, recusando item cujo caminho saia da pasta de destino."""
    raiz = os.path.abspath(destino)
    with zipfile.ZipFile(caminho) as zf:
        for membro in zf.namelist():
            alvo = os.path.abspath(os.path.join(raiz, membro))
            if alvo != raiz and not alvo.startswith(raiz + os.sep):
                raise ValueError("o zip tem um caminho fora da pasta: %s" % membro)
        zf.extractall(raiz)
    return raiz


def trazer_para_temp(entrega, destino):
    """Copia ou descompacta a entrega numa pasta local e devolve os .shp.

    O arcpy trabalha sobre a copia: assim nao prende arquivo na pasta do
    OneDrive, que depois precisa ser movido."""
    os.makedirs(destino, exist_ok=True)
    if entrega["tipo"] == "zip":
        extrair_zip(entrega["caminho"], destino)
    elif entrega["tipo"] == "pasta":
        shutil.copytree(entrega["caminho"], os.path.join(destino, entrega["nome"]))
    else:
        for item in entrega["itens"]:
            shutil.copy2(item, destino)
    return shapefiles(destino)


def separar_por_fazenda(linhas_por_fazenda, minimo_pct=FAZENDA_MINIMA_PCT):
    """(mantidas, descartadas). Fazenda com menos de minimo_pct das linhas
    que caíram em talhao entrou pela borda de outra."""
    total = sum(linhas_por_fazenda.values())
    mantidas, descartadas = {}, {}
    for faz, n in linhas_por_fazenda.items():
        destino = mantidas if total and 100.0 * n / total >= minimo_pct else descartadas
        destino[faz] = n
    return mantidas, descartadas


def motivo_para_nao_carregar(total, sem_talhao, mantidas,
                             maximo_pct=SEM_TALHAO_MAXIMO_PCT):
    if total == 0:
        return "o shapefile nao tem nenhuma linha"
    if not mantidas:
        return ("nenhuma linha caiu em talhao da BASE_SAFRA - a area nao esta "
                "no inventario vigente?")
    if 100.0 * sem_talhao / total > maximo_pct:
        return ("%d de %d linhas (%.0f%%) fora dos talhoes da BASE_SAFRA - a "
                "area pode nao estar no inventario vigente"
                % (sem_talhao, total, 100.0 * sem_talhao / total))
    return None


def nome_lote(mantidas, quando):
    """<fazenda com mais linhas>_<AAAAMMDD_HHMMSS da carga>"""
    principal = max(sorted(mantidas), key=lambda f: mantidas[f])
    return "%s_%s" % (principal, quando.strftime("%Y%m%d_%H%M%S"))


def ultimo_voo(missoes):
    """Missao de falhas mais recente que nao foi interrompida (regra 4.1)."""
    datas = [saida for saida, tipo, resultado in missoes
             if saida and (tipo or "").strip() == "Falhas"
             and (resultado or "").strip() != "Interrompido"]
    return max(datas) if datas else None


def resumo_por_talhao(linhas):
    """{chavesig: (quantidade, metros de LengthComp)}"""
    resumo = {}
    for _, _, _, comp_ofi, chave, _ in linhas:
        n, metros = resumo.get(chave, (0, 0.0))
        resumo[chave] = (n + 1, metros + (comp_ofi or 0.0))
    return resumo


def clausula_in(campo, valores):
    return "%s IN (%s)" % (campo, ",".join(
        "'%s'" % str(v).replace("'", "''") for v in valores))


def em_blocos(valores, tamanho=TAMANHO_IN):
    valores = sorted(valores)
    for i in range(0, len(valores), tamanho):
        yield valores[i:i + tamanho]


def mover_para_carregadas(entrega, pasta, lote, usuario):
    destino = os.path.join(pasta, NOME_CARREGADAS, "%s_%s" % (lote, usuario))
    os.makedirs(destino, exist_ok=True)
    for item in entrega["itens"]:
        shutil.move(item, os.path.join(destino, os.path.basename(item)))
    return destino


# --------------------------- com banco --------------------------------------

def criar_destino():
    import arcpy
    if arcpy.Exists(FC_DESTINO):
        return
    print("criando %s" % FC_DESTINO)
    sr = arcpy.Describe(FC_INVENTARIO).spatialReference
    arcpy.management.CreateFeatureclass(DATASET, "LINHAS_FALHA", "POLYLINE",
                                        spatial_reference=sr)
    for nome, tipo, tam in CAMPOS:
        if tam:
            arcpy.management.AddField(FC_DESTINO, nome, tipo, field_length=tam)
        else:
            arcpy.management.AddField(FC_DESTINO, nome, tipo)
    arcpy.management.AddIndex(FC_DESTINO, ["CHAVESIG"], "IDX_LF_CHAVESIG")
    arcpy.management.AddIndex(FC_DESTINO, ["LOTE"], "IDX_LF_LOTE")


def validar_shapefile(shp):
    """None se for o shapefile de falhas; senao, o motivo."""
    import arcpy
    desc = arcpy.Describe(shp)
    if desc.shapeType != "Polyline":
        return "nao e de linhas (%s)" % desc.shapeType
    campos = {f.name.lower() for f in arcpy.ListFields(shp)}
    faltam = [c for c in ("Length", "LengthComp") if c.lower() not in campos]
    if faltam:
        return "faltam os campos %s" % ", ".join(faltam)
    return None


def cruzar(shp):
    """[geometria, Field, Length, LengthComp, chavesig, safra] por linha;
    chavesig e safra nulos quando o centro nao cai em talhao."""
    import arcpy
    kml = "Field" if "field" in {f.name.lower() for f in arcpy.ListFields(shp)} else None
    campos = ["SHAPE@", kml or "OID@", "Length", "LengthComp"]

    talhoes = "lyr_talhoes_linhas"
    arcpy.management.MakeFeatureLayer(FC_INVENTARIO, talhoes)
    try:
        arcpy.management.SelectLayerByLocation(talhoes, "INTERSECT", shp)
        if int(arcpy.management.GetCount(talhoes)[0]) == 0:
            with arcpy.da.SearchCursor(shp, campos) as cur:
                return [[g, None, c, co, None, None] for g, _, c, co in cur]
        juncao = r"memory\linhas_juncao"
        arcpy.analysis.SpatialJoin(shp, talhoes, juncao,
                                   join_operation="JOIN_ONE_TO_ONE",
                                   join_type="KEEP_ALL",
                                   match_option="HAVE_THEIR_CENTER_IN")
    finally:
        arcpy.management.Delete(talhoes)

    linhas = []
    with arcpy.da.SearchCursor(juncao, campos + ["Chavesig", "Safra"]) as cur:
        for geom, campo_kml, comp, comp_ofi, chave, safra in cur:
            linhas.append([geom, str(campo_kml)[:5] if kml and campo_kml else None,
                           comp, comp_ofi,
                           str(chave).strip() if chave else None,
                           str(safra).strip() if safra else None])
    arcpy.management.Delete(juncao)
    return linhas


def preparar(entrega, temp):
    prep = {"entrega": entrega, "linhas": [], "total": 0, "sem_talhao": 0,
            "mantidas": {}, "descartadas": {}, "motivo": None, "avisos": []}
    try:
        shps = trazer_para_temp(entrega, temp)
    except (zipfile.BadZipFile, ValueError, OSError) as erro:
        prep["motivo"] = ("nao consegui abrir a entrega (%s). Se acabou de salvar, "
                          "espere o OneDrive terminar de sincronizar" % erro)
        return prep

    validos = []
    for shp in shps:
        motivo = validar_shapefile(shp)
        if motivo:
            prep["avisos"].append("%s ignorado: %s" % (os.path.basename(shp), motivo))
        else:
            validos.append(shp)
    if not validos:
        prep["motivo"] = "nao achei o shapefile de falhas (linhas com Length e LengthComp)"
        return prep

    todas = []
    for shp in validos:
        print("  cruzando %s com a BASE_SAFRA..." % os.path.basename(shp))
        todas.extend(cruzar(shp))
    com_talhao = [l for l in todas if l[4]]
    mantidas, descartadas = separar_por_fazenda(
        collections.Counter(fazenda(l[4]) for l in com_talhao))
    prep.update(total=len(todas), sem_talhao=len(todas) - len(com_talhao),
                mantidas=mantidas, descartadas=descartadas,
                linhas=[l for l in com_talhao if fazenda(l[4]) in mantidas])
    prep["motivo"] = motivo_para_nao_carregar(prep["total"], prep["sem_talhao"],
                                              mantidas)
    return prep


def ler_por_chave(tabela, campo_chave, campos, chaves):
    """{chave: [tupla dos campos, ...]}"""
    import arcpy
    dados = collections.defaultdict(list)
    for bloco in em_blocos(chaves):
        with arcpy.da.SearchCursor(tabela, [campo_chave] + campos,
                                   clausula_in(campo_chave, bloco)) as cur:
            for linha in cur:
                dados[str(linha[0]).strip()].append(tuple(linha[1:]))
    return dados


def conferir(prep):
    import arcpy
    chaves = sorted({l[4] for l in prep["linhas"]})
    missoes = ler_por_chave(TB_VOO, "CHAVESIG",
                            ["DT_SAIDA", "TIPO_MISSAO", "RESULTADO_MISSAO"], chaves)
    return {
        "pims": ler_por_chave(TB_PIMS, "Layer", ["Area_total", "FALHA_LINHA"], chaves),
        "voos": {c: ultimo_voo(m) for c, m in missoes.items()},
        "atuais": (ler_por_chave(FC_DESTINO, "CHAVESIG", ["LOTE"], chaves)
                   if arcpy.Exists(FC_DESTINO) else {}),
    }


def mostrar(prep, conf):
    e = prep["entrega"]
    print("\nEntrega: %s (%s)" % (e["nome"], e["tipo"]))
    for aviso in prep["avisos"]:
        print("  aviso: %s" % aviso)
    if not prep["total"]:
        return
    print("  linhas no arquivo : %s" % milhar(prep["total"]))
    print("  sem talhao        : %s - borda ou fora da BASE_SAFRA, nao entram"
          % milhar(prep["sem_talhao"]))
    for faz, n in sorted(prep["descartadas"].items()):
        print("  fazenda %s    : %s linhas pela borda, nao entram" % (faz, milhar(n)))
    if conf is None:
        for faz, n in sorted(prep["mantidas"].items()):
            print("  fazenda %s    : %s linhas" % (faz, milhar(n)))
        return

    resumo = resumo_por_talhao(prep["linhas"])
    for faz in sorted(prep["mantidas"]):
        chaves = sorted(c for c in resumo if fazenda(c) == faz)
        print("\n  fazenda %s: %s linhas em %d talhoes"
              % (faz, milhar(prep["mantidas"][faz]), len(chaves)))
        print("  %-16s %7s %8s %6s %7s %7s %10s  %s" % (
            "talhao", "linhas", "metros", "m/ha", "calc %", "PIMS %", "voo",
            "hoje no banco"))
        for chave in chaves:
            n, metros = resumo[chave]
            area, pims = (conf["pims"].get(chave) or [(None, None)])[0]
            voo = conf["voos"].get(chave)
            atuais = conf["atuais"].get(chave, [])
            lotes = sorted({l[0] for l in atuais if l[0]})
            print("  %-16s %7s %8s %6s %7s %7s %10s  %s" % (
                chave, milhar(n), milhar(metros),
                fmt(metros / area if area else None, 0),
                fmt(100.0 * metros * ESPACAMENTO_M / (area * 10000.0) if area else None, 2),
                fmt(pims, 1), voo.strftime("%d/%m/%Y") if voo else "-",
                ("%s linhas (%s)" % (milhar(len(atuais)), ", ".join(lotes)))
                if atuais else "nenhuma"))
    print("\n  calc %%: metros / (area do PIMS x 10.000 / %.1f m). So conferencia - "
          "o relatorio mostra o PIMS." % ESPACAMENTO_M)


def apagar(fc, onde):
    import arcpy
    camada = "lyr_apagar_linhas"
    arcpy.management.MakeFeatureLayer(fc, camada, onde)
    try:
        n = int(arcpy.management.GetCount(camada)[0])
        if n:
            arcpy.management.DeleteFeatures(camada)
    finally:
        arcpy.management.Delete(camada)
    return n


def contar(fc, onde):
    import arcpy
    with arcpy.da.SearchCursor(fc, ["OID@"], onde) as cur:
        return sum(1 for _ in cur)


def gravar_linhas(prep, conf, agora):
    """Grava as novas e so depois apaga as antigas dos mesmos talhoes."""
    import arcpy
    criar_destino()
    lote = nome_lote(prep["mantidas"], agora)
    campos = ["SHAPE@", "CHAVESIG", "SAFRA_INV", "CAMADA_INV", "TALHAO_KML",
              "COMP_M", "COMP_OFI_M", "CLASSE_TAM", "DATA_VOO", "LOTE",
              "DATA_CARGA"]
    print("\n  gravando %s linhas no lote %s..." % (milhar(len(prep["linhas"])), lote))
    try:
        with arcpy.da.InsertCursor(FC_DESTINO, campos) as ins:
            for geom, kml, comp, comp_ofi, chave, safra in prep["linhas"]:
                ins.insertRow([geom, chave, safra, NOME_INVENTARIO, kml, comp,
                               comp_ofi, classe_tamanho(comp_ofi or 0.0),
                               conf["voos"].get(chave), lote, agora])
    except Exception:
        print("  ERRO na gravacao - retirando as linhas novas; as antigas ficam "
              "como estavam")
        apagar(FC_DESTINO, "LOTE = '%s'" % lote)
        raise

    chaves = {l[4] for l in prep["linhas"]}
    removidas = 0
    for bloco in em_blocos(chaves):
        removidas += apagar(FC_DESTINO, "%s AND LOTE <> '%s'"
                            % (clausula_in("CHAVESIG", bloco), lote))
    # lote antigo que ficou sem nenhum talhao leva junto as linhas sem talhao
    antigos = {l[0] for linhas in conf["atuais"].values() for l in linhas if l[0]}
    for antigo in sorted(antigos - {lote}):
        if contar(FC_DESTINO, "LOTE = '%s' AND CHAVESIG IS NOT NULL" % antigo) == 0:
            removidas += apagar(FC_DESTINO, "LOTE = '%s'" % antigo)
    print("  linhas antigas removidas: %s (desses talhoes e, de lote que ficou "
          "sem talhao, as de borda)" % milhar(removidas))
    return lote


def refazer_mapa(fazendas, agora):
    import mapa_calor_falhas
    for faz in sorted(fazendas):
        try:
            caminho = mapa_calor_falhas.gerar(faz, agora.strftime("%Y%m%d_%H%M%S"))
            print("  mapa de calor: %s" % caminho)
        except Exception as erro:
            print("  AVISO: o mapa de calor da fazenda %s nao foi gerado: %s" % (faz, erro))
            print("         o relatorio sai sem o mapa de calor ate ele ser refeito com")
            print("         propy -u src\\processamento\\mapa_calor_falhas.py %s" % faz)


def processar(entrega, pasta, temp, gravar, usuario, confirmar):
    resultado = {"entrega": entrega["nome"], "fazendas": [], "lote": None,
                 "motivo": None}
    prep = preparar(entrega, temp)
    resultado["fazendas"] = sorted(prep["mantidas"])
    conf = None if prep["motivo"] else conferir(prep)
    mostrar(prep, conf)

    if prep["motivo"]:
        print("\n  NADA CARREGADO: %s. A entrega continua na pasta." % prep["motivo"])
        resultado.update(situacao="NAO_CARREGADA", motivo=prep["motivo"])
        return resultado
    if not gravar:
        print("\n  SIMULACAO: nada gravado nem movido (use --gravar).")
        resultado["situacao"] = "SIMULADA"
        return resultado
    if confirmar and not confirmar(prep):
        print("  Nao carregada - a entrega continua na pasta.")
        resultado["situacao"] = "RECUSADA"
        return resultado

    agora = datetime.datetime.now()
    resultado["lote"] = gravar_linhas(prep, conf, agora)
    resultado["situacao"] = "CARREGADA"
    refazer_mapa(prep["mantidas"], agora)
    try:
        destino = mover_para_carregadas(entrega, pasta, resultado["lote"], usuario)
        print("  entrega movida para %s" % destino)
    except OSError as erro:
        print("  AVISO: linhas gravadas, mas a entrega nao foi movida (%s). Tire-a "
              "da pasta: se ficar, entra de novo na proxima vez (sem duplicar)." % erro)
    return resultado


def processar_pendentes(gravar, usuario, confirmar=None, pasta=None):
    """Processa todas as entregas da pasta de entrada.

    Devolve None se esta conta nao consegue abrir a pasta; senao, uma lista
    com um resultado por entrega (situacao CARREGADA, SIMULADA, RECUSADA ou
    NAO_CARREGADA)."""
    pasta = pasta or pasta_entrada()
    if pasta is None:
        print("  nao consegui abrir a pasta de linhas com a conta %s:" % usuario)
        print("  %s" % PASTAS_ENTRADA[-1])
        print("  Quem pede o relatorio precisa de acesso a ela - ver "
              "docs\\08-relatorio-sob-demanda.md.")
        return None

    entregas = entregas_pendentes(pasta)
    if not entregas:
        print("  nenhuma entrega nova em %s" % pasta)
        return []

    print("  %d entrega(s) em %s" % (len(entregas), pasta))
    temp = os.path.join(PASTA_TEMP, "%s_%s" % (
        usuario, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    resultados = []
    try:
        for i, entrega in enumerate(entregas, 1):
            resultados.append(processar(entrega, pasta, os.path.join(temp, str(i)),
                                        gravar, usuario, confirmar))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return resultados


def main():
    gravar = "--gravar" in sys.argv
    pasta = None
    if "--pasta" in sys.argv:
        i = sys.argv.index("--pasta")
        if i + 1 >= len(sys.argv):
            print("--pasta precisa do caminho")
            return 1
        pasta = sys.argv[i + 1]
    usuario = os.environ.get("USERNAME", "").strip().lower() or "desconhecido"

    print("=" * 64)
    print(" LINHAS DE FALHA (Bem Agro) - %s"
          % ("GRAVACAO" if gravar else "SIMULACAO (use --gravar para gravar)"))
    print(" usuario Windows: %s" % usuario)
    print("=" * 64)

    resultados = processar_pendentes(gravar, usuario, pasta=pasta)
    if resultados is None:
        return 1
    return 1 if any(r["situacao"] == "NAO_CARREGADA" for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
