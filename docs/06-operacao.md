# 06 — Operação

## Ambiente

Tudo roda no Python do ArcGIS Pro (`arcgispro-py3`). Nada precisa ser
instalado além do que já vem com o Pro.

**A produção roda deste clone**, em `D:\GEO\REPOS\diagnostico_falhas`, na `main`.
Não há cópia dos scripts em `D:\GEO\CODIGOS` — lá ficaram só avisos. Mudança
entra por commit e `git pull` no clone.

```
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"
```

Sempre com `-u`, para a saída aparecer conforme acontece:

```bash
python -u caminho\do\script.py
```

Sem o `-u`, o buffer segura tudo até o fim e o script parece travado.

Requisitos: extensão **Spatial Analyst** (kernel density e declividade),
conexão SDE para o SQL Server, conexão para o BigQuery, o Pro conectado ao
geoportal e, na primeira execução da declividade, acesso ao bucket público do
Copernicus na AWS.

## Dependências entre scripts

```
carga_status_report ─────────────────────┐
carga_estacoes_zeus ──► vincular_talhao_estacao ──► indicadores_clima ─┤
sincronizar_surveys_vant ────────────────┤
carga_linhas_falha ──► mapa_calor_falhas ┤
classificar_epoca_plantio ───────────────┤
                                          ▼
                                   criar_view_relatorio
                                          │
                                          ▼
                                  gerar_relatorio_falhas
```

O `vincular_talhao_estacao` depende da `ESTACOES_ZEUS` existir.
O `indicadores_clima_talhao` depende do vínculo e do monitoramento.
O `criar_view_relatorio` depende de todas as tabelas existirem.

A cadeia do solo e da época de plantio, em ordem:

1. `carga_mancha_solos` → `SOLOS_ATVOS`
2. `vincular_talhao_manejo` → `TALHAO_MANEJO` (regrava a tabela inteira)
3. `declividade_talhao` → completa a `TALHAO_MANEJO`
4. `carga_matriz_plantio` → `MATRIZ_PLANTIO` (independe dos anteriores)
5. `classificar_epoca_plantio` → `EPOCA_PLANTIO_TALHAO` (depende de 3 e 4)

**A ordem entre 2 e 3 importa.** O vínculo regrava a `TALHAO_MANEJO` e apaga a
declividade que estava lá. Depois dele, rode sempre a declividade.

O `classificar_epoca_plantio` usa a `DATA_PLANTIO` da `BASE_SAFRA`, então precisa
rodar de novo quando a base ganhar datas de plantio.

## Frequência sugerida

| Script | Frequência | Observação |
|---|---|---|
| `carga_status_report` | diária | junto com a rotina das 5h |
| `sincronizar_surveys_vant` | diária | escreve no Portal a cada execução |
| `carga_estacoes_zeus` | diária | quando migrar das planilhas para o BQ |
| `vincular_talhao_estacao` | diária | rápido; reajusta se a rede mudar |
| `indicadores_clima_talhao` | diária | |
| `carga_linhas_falha` | por entrega | manual hoje |
| `mapa_calor_falhas` | por entrega | |
| `carga_mancha_solos` | quando a mancha mudar | camada de referência |
| `vincular_talhao_manejo` | quando os talhões ou a mancha mudarem | sempre seguido da declividade |
| `declividade_talhao` | logo depois do vínculo | baixa os tiles só na primeira vez |
| `carga_matriz_plantio` | quando a matriz for revisada | |
| `classificar_epoca_plantio` | diária | acompanha a `DATA_PLANTIO` da base |
| `criar_view_relatorio` | só quando a definição mudar | |
| `solicitar_relatorio_falhas` | sob demanda | pelo `GERAR_RELATORIO_FALHAS.bat`; ver [08](08-relatorio-sob-demanda.md) |
| `gerar_relatorio_falhas` | sob demanda | ou após novas cargas |

Para agendar: a tarefa precisa rodar com o usuário do Windows que tem o Pro
autenticado no geoportal, porque a conexão usa `GIS("pro")`.

## Parâmetros a revisar

| Onde | Parâmetro | Valor atual | Pendente |
|---|---|---|---|
| `carga_linhas_falha` | `ESPACAMENTO_M` | 1.5 | de-para dos códigos `ESPAC` |
| `mapa_calor_falhas` | `QUEBRAS` | 300/600/900 | atualizar para 280/500/1000 |
| `gerar_relatorio` | `QUEBRAS` | 280/500/1000 | já correto |
| `gerar_relatorio` | `META_PCT` | 4.2 | confirmado com o agrícola |
| `indicadores_clima` | `VERANICO_MM` | 5.0 | validar com agrônomo |
| `indicadores_clima` | `RAIO_CONFIAVEL_KM` | 15.0 | definido a partir da distribuição |
| `*` | `UTC_OFFSET_H` | −3 | MS é −4; hoje é único para todas as unidades |
| `carga_mancha_solos` | `SHAPEFILE` | pasta do OneDrive de um usuário | ajustar em cada máquina |
| `carga_mancha_solos`, `vincular_talhao_manejo`, `declividade_talhao` | `NOME_CAMADA` / `NOME_CAMADA_SOLOS` | `SOLOS_ATVOS` | tem de ser o mesmo nos três |
| `carga_matriz_plantio` | `PLANILHA` | `D:\GEO\SOLOS\matriz_plantio.xlsx` | fora do repositório |
| `declividade_talhao` | `MARGEM_FRONTEIRA` | 0,5 ponto percentual | |
| `vincular_talhao_manejo` | `PCT_MINIMO_ALERTA` | 60% | repetido como número solto no `classificar_epoca_plantio` |

## Problemas conhecidos e como resolver

**Script parece travado, sem saída.** Buffer. Rode com `-u`.

**`RuntimeError: cannot open 'in_memory\...'`.** O `in_memory` foi
descontinuado nas versões recentes do Pro. Use `memory\...` ou
`arcpy.env.scratchGDB`.

**`Incorrect syntax near '2026-03-03'`.** A sintaxe `date 'aaaa-mm-dd'` é do
PostgreSQL. No SQL Server a data vai só entre aspas simples.

**`ERROR 999999` no `CreateDatabaseView`.** A ferramenta remonta a definição
por dentro e quebra com `OUTER APPLY` e subconsulta com alias. Use
`arcpy.ArcSDESQLExecute` e mande o DDL direto.

**View com contagem multiplicada.** Falta o filtro de archiving no join com a
`BASE_SAFRA`: `GDB_TO_DATE = '9999-12-31 23:59:59'`.

**Datas no formato americano no HTML.** O `ArcSDESQLExecute` devolve data como
texto no formato do driver. As funções `data()` e `to_date()` do gerador
aceitam ambos.

**Campos com espaços à esquerda.** Campos `char` de tamanho fixo no SQL Server
vêm preenchidos com espaços. O gerador aplica `strip()` na leitura.

**Imagem vazando para a página seguinte no PDF.** Imagem não pode ser quebrada;
sem `max-height` o navegador empurra a figura inteira. O CSS limita a altura e
usa `break-inside: avoid`.

**PDF não é gerado.** O script procura Edge e Chrome nos caminhos padrão. Se
não achar, avisa e o HTML continua disponível para impressão manual.

**`FileNotFoundError` com planilha do OneDrive.** Nome com acento ou arquivo
em modo online-only. Renomeie sem acento e marque "Sempre manter neste
dispositivo".

**`nao foi possivel remover a camada` na carga da mancha de solos.** Trava de
esquema na `SOLOS_ATVOS`. O próprio script lista as causas na ordem em que vale
verificar: Pro aberto em segundo plano, outra sessão de Python, serviço
publicado apontando para a camada, sessão presa no SQL Server. Se a trava não
ceder, troque o nome da camada — nos três scripts de solo, não só no vínculo,
como a mensagem do script sugere.

**`nenhum tile baixado` na declividade.** A rede corporativa pode estar
bloqueando o bucket da AWS. Baixe os tiles à mão para `D:\GEO\DEM`.

**Mancha de solos gravada com geometria e sem nenhum atributo.** Os campos foram
renomeados para maiúscula. Não faça isso — ver `SOLOS_ATVOS` no
[modelo de dados](03-modelo-de-dados.md).

**Declividade vazia na `TALHAO_MANEJO`.** O vínculo com a mancha rodou depois da
declividade e regravou a tabela. Rode o `declividade_talhao` de novo.

## Validação após execução

A área piloto (fazenda 320127) é o caso de referência. Valores esperados:

| Verificação | Esperado |
|---|---|
| Talhão 6, `FALHA_PCT` | 23,8 |
| Talhão 6, m/ha | ~1.581 |
| DAP do voo | 127 |
| Dias entre porte e voo | 14 |
| Chuva 0–30 DAP | 96,4 mm (unidade: 146,8) |
| Chuva 30 dias antes do plantio | sem registro na estação USL_320121 |
| Talhões 4, 5 e 6: unidade de manejo | 7 |
| Talhão 7: unidade de manejo | 9 |
| Talhão 4: faixa de declividade | `> 5%` (mediana 6,21%) |
| Talhões 4 a 7: período e classe da época | `Mar 1Q`, `Favoravel` |
| Integridade da view | linhas = chavesig distintos |
