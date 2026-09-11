# -*- coding: utf-8 -*-
"""
Publica a mancha de solos da Atvos no geodatabase corporativo.

Camada de REFERENCIA: muda raramente, mas precisa estar no GDB para que o
vinculo com os talhoes seja recalculavel. Enquanto ela vive num shapefile na
pasta de alguem, o vinculo e uma foto do dia em que alguem rodou.

Origem: Mancha_Solos.shp, SIRGAS 2000 / UTM 22S, 1.260 poligonos,
~196 mil ha, cobrindo a regiao de USL-UEL.

O campo Num_Manejo (1 a 14) e a chave que casa com a Matriz de Plantio - o
texto do agrupamento de solos bate exatamente entre as duas fontes, entao a
juncao e direta, sem de-para.

NAO habilitar archiving nesta camada.

Uso: python -u C:\\temp\\carga_mancha_solos.py

Geotecnologia / Cartografia - Atvos
"""

import datetime
import functools
import os
import time
import arcpy

print = functools.partial(print, flush=True)
arcpy.env.overwriteOutput = True

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------

SHAPEFILE = (r"C:\Users\joao.fgromboni\OneDrive - Atvos"
             r"\Geotecnologia-03. Geotecnologia Cartografia - Documentos"
             r"\Projetos_Cart\DIAGNOSTICO_FALHAS\Mancha_Solos.shp")

SDE = r"D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde"
DATASET = os.path.join(SDE, "ATVOSPUBLICADOR.AGRICOLA_ATVOS")

# Se a camada existente estiver travada e a trava nao ceder, troque este nome
# (ex.: SOLOS_ATVOS_V2). Criar camada nova nao exige trava exclusiva.
# O mesmo nome precisa ser usado no vincular_talhao_manejo.py.
NOME_CAMADA = "SOLOS_ATVOS"

FC_SAIDA = os.path.join(DATASET, "ATVOSPUBLICADOR." + NOME_CAMADA)

# Os nomes do shapefile sao mantidos como estao. NAO renomear para maiuscula:
# no geodatabase o nome de campo nao diferencia caixa, entao criar NUM_MANEJO
# ao lado de Num_Manejo nao cria campo novo - escreve no mesmo - e o
# DeleteField seguinte apaga o unico que existe, destruindo o atributo.
CAMPOS_ESPERADOS = ["Num_Manejo", "Manejo", "solo", "Textura",
                    "Saturacao", "Amb_Atvos", "Amb_Athena"]

UNIDADES_MANEJO_ESPERADAS = set(range(1, 15))


def conferir_origem():
    """Le a origem inteira ANTES de tocar no destino."""
    if not arcpy.Exists(SHAPEFILE):
        raise RuntimeError("shapefile nao encontrado: %s" % SHAPEFILE)

    desc = arcpy.Describe(SHAPEFILE)
    total = int(arcpy.management.GetCount(SHAPEFILE)[0])
    print("origem: %s" % SHAPEFILE)
    print("  feicoes    : %d" % total)
    print("  geometria  : %s" % desc.shapeType)
    print("  referencia : %s" % desc.spatialReference.name)

    if total == 0:
        raise RuntimeError("origem vazia - nada a carregar")

    campos_origem = {f.name for f in arcpy.ListFields(SHAPEFILE)}
    faltando = [c for c in CAMPOS_ESPERADOS if c not in campos_origem]
    if faltando:
        raise RuntimeError("campos ausentes na origem: %s" % ", ".join(faltando))

    ums, sem_um = set(), 0
    with arcpy.da.SearchCursor(SHAPEFILE, ["Num_Manejo"]) as cur:
        for (um,) in cur:
            if um is None:
                sem_um += 1
            else:
                ums.add(int(um))

    print("  unidades de manejo: %s" % sorted(ums))
    if sem_um:
        print("  AVISO: %d poligonos sem Num_Manejo" % sem_um)

    faltantes = UNIDADES_MANEJO_ESPERADAS - ums
    if faltantes:
        print("  AVISO: unidades da matriz sem mancha: %s" % sorted(faltantes))
    extras = ums - UNIDADES_MANEJO_ESPERADAS
    if extras:
        print("  AVISO: unidades fora da matriz: %s" % sorted(extras))

    return total


def esquema_ok():
    """A camada existente tem todos os campos esperados?"""
    if not arcpy.Exists(FC_SAIDA):
        return False
    presentes = {f.name for f in arcpy.ListFields(FC_SAIDA)}
    return all(c in presentes for c in CAMPOS_ESPERADOS)


def completar_esquema():
    """Tenta acrescentar os campos que faltam, sem recriar a camada.

    Alterar esquema tambem pede trava, mas em alguns casos passa onde o
    Delete falha. Se funcionar, evita a recriacao inteira.
    """
    presentes = {f.name for f in arcpy.ListFields(FC_SAIDA)}
    faltando = [c for c in CAMPOS_ESPERADOS if c not in presentes]
    if not faltando:
        return True

    tipos = {f.name: f for f in arcpy.ListFields(SHAPEFILE)}
    print("  tentando acrescentar os campos que faltam: %s"
          % ", ".join(faltando))
    try:
        for nome in faltando:
            f = tipos[nome]
            if f.type == "String":
                arcpy.management.AddField(FC_SAIDA, nome, "TEXT",
                                          field_length=f.length)
            elif f.type in ("Double", "Single"):
                arcpy.management.AddField(FC_SAIDA, nome, "DOUBLE")
            else:
                arcpy.management.AddField(FC_SAIDA, nome, "LONG")
    except arcpy.ExecuteError:
        print("  nao foi possivel alterar o esquema")
        return False

    print("  esquema completado - a camada sera repovoada")
    return True


def remover_camada():
    """Apaga a camada, contornando a trava de esquema.

    O proprio arcpy costuma ser o culpado: Exists e ListFields abrem a
    conexao e o processo mantem o cache do workspace, o que ja basta para o
    Delete seguinte falhar. ClearWorkspaceCache solta isso.
    """
    for tentativa in range(1, 4):
        try:
            arcpy.management.ClearWorkspaceCache(SDE)
        except Exception:
            pass
        try:
            arcpy.management.Delete(FC_SAIDA)
            return
        except arcpy.ExecuteError:
            print("  trava de esquema (tentativa %d de 3)..." % tentativa)
            time.sleep(3)

    raise RuntimeError(
        "nao foi possivel remover a camada - a trava nao e deste processo.\n"
        "Verifique, nesta ordem:\n"
        "  1. ArcGISPro.exe no Gerenciador de Tarefas (o Pro pode continuar\n"
        "     em segundo plano mesmo com a janela fechada)\n"
        "  2. outra janela de Python ou Notebook com a camada aberta\n"
        "  3. servico publicado no portal apontando para a SOLOS_ATVOS\n"
        "  4. sessao presa no SQL Server de uma execucao anterior que\n"
        "     terminou com erro - some ao encerrar a sessao no banco\n"
        "\nSaida rapida: reiniciar a maquina derruba qualquer sessao cliente\n"
        "presa. Se nao for possivel, troque NOME_CAMADA no topo deste script\n"
        "(ex.: SOLOS_ATVOS_V2) e ajuste o mesmo nome no\n"
        "vincular_talhao_manejo.py - criar camada nova dispensa a trava.")


def importar():
    """Traz o shapefile para o geodatabase.

    Recriar a camada exige trava exclusiva de esquema, que falha se alguem
    estiver com ela aberta no Pro. Quando o esquema atual ja serve, troca so
    as linhas - isso dispensa a trava e a camada pode continuar publicada e
    aberta enquanto o dado e atualizado.
    """
    if esquema_ok():
        print("\ncamada ja existe com o esquema correto - trocando as linhas")
        arcpy.management.DeleteRows(FC_SAIDA)
        sr = arcpy.Describe(FC_SAIDA).spatialReference
        reprojetado = r"memory\solos_reproj"
        arcpy.management.Project(SHAPEFILE, reprojetado, sr)
        arcpy.management.Append(reprojetado, FC_SAIDA, "NO_TEST")
        arcpy.management.Delete(reprojetado)
        return

    if arcpy.Exists(FC_SAIDA):
        print("\nesquema desatualizado - recriando a camada")
        if not completar_esquema():
            remover_camada()

    print("importando para o geodatabase (reprojeta para o SR do dataset)...")
    arcpy.conversion.FeatureClassToFeatureClass(
        SHAPEFILE, DATASET, NOME_CAMADA)


def conferir_destino():
    """Confere que os atributos sobreviveram a carga.

    Existe porque uma versao anterior deste script renomeava os campos para
    maiuscula e, como o geodatabase nao diferencia caixa, acabava apagando o
    atributo. A camada ficava com a geometria certa e sem nenhum dado.
    """
    print("conferindo os atributos gravados...")
    presentes = {f.name for f in arcpy.ListFields(FC_SAIDA)}
    faltando = [c for c in CAMPOS_ESPERADOS if c not in presentes]
    if faltando:
        raise RuntimeError(
            "campos ausentes no destino: %s. Campos gravados: %s"
            % (", ".join(faltando), ", ".join(sorted(presentes))))

    ums, vazios = set(), 0
    with arcpy.da.SearchCursor(FC_SAIDA, ["Num_Manejo", "Manejo"]) as cur:
        for um, manejo in cur:
            if um is None or not manejo:
                vazios += 1
            else:
                ums.add(int(um))
    print("  unidades de manejo gravadas: %s" % sorted(ums))
    if vazios:
        print("  AVISO: %d feicoes sem unidade ou sem manejo" % vazios)
    if not ums:
        raise RuntimeError("nenhuma unidade de manejo gravada - carga invalida")


def carregar():
    total = conferir_origem()

    importar()

    print("limpando espacos dos campos de texto...")
    texto = [c for c in CAMPOS_ESPERADOS if c != "Num_Manejo"]
    with arcpy.da.UpdateCursor(FC_SAIDA, texto) as cur:
        for linha in cur:
            novo = [(v.strip() or None) if isinstance(v, str) else v
                    for v in linha]
            if novo != list(linha):
                cur.updateRow(novo)

    if "DATA_CARGA" not in {f.name for f in arcpy.ListFields(FC_SAIDA)}:
        arcpy.management.AddField(FC_SAIDA, "DATA_CARGA", "DATE")
    hoje = datetime.datetime.now()
    with arcpy.da.UpdateCursor(FC_SAIDA, ["DATA_CARGA"]) as cur:
        for linha in cur:
            linha[0] = hoje
            cur.updateRow(linha)

    print("criando indice em Num_Manejo...")
    try:
        arcpy.management.AddIndex(FC_SAIDA, ["Num_Manejo"], "IDX_SOLOS_UM")
    except arcpy.ExecuteError:
        print("  indice ja existe")

    conferir_destino()

    gravadas = int(arcpy.management.GetCount(FC_SAIDA)[0])
    print("\n=== resultado ===")
    print("  origem  : %d feicoes" % total)
    print("  gravadas: %d feicoes" % gravadas)
    if gravadas != total:
        print("  ATENCAO: contagem divergente - conferir antes de usar")
    print("\ncamada: %s" % FC_SAIDA)
    print("proximo passo: vincular_talhao_manejo.py")


if __name__ == "__main__":
    carregar()