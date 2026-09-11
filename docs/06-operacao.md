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
O `indicadores_clima_talhao` depende do vínculo e do monitoramento. Ele e o
`classificar_epoca_plantio` usam a data de plantio do PIMS, então vêm depois
do `carga_status_report`.

O percentual oficial, os surveys, a sequência monitoramento → vínculo → clima e
a época de plantio rodam todo dia pelo `ATUALIZAR_DIAGNOSTICO.bat` — ver
[atualização diária dos dados](#atualização-diária-dos-dados).
O `criar_view_relatorio` depende de todas as tabelas existirem.

A cadeia do solo e da época de plantio, em ordem:

1. `carga_mancha_solos` → `SOLOS_ATVOS`
2. `vincular_talhao_manejo` → `TALHAO_MANEJO` (regrava a tabela inteira)
3. `declividade_talhao` → completa a `TALHAO_MANEJO`
4. `carga_matriz_plantio` → `MATRIZ_PLANTIO` (independe dos anteriores)
5. `classificar_epoca_plantio` → `EPOCA_PLANTIO_TALHAO` (depende de 3 e 4)

**A ordem entre 2 e 3 importa.** O vínculo regrava a `TALHAO_MANEJO` e apaga a
declividade que estava lá. Depois dele, rode sempre a declividade.

O `classificar_epoca_plantio` usa a data de plantio do PIMS — a da `BASE_SAFRA`
só quando o PIMS não tem o talhão — e roda todo dia, depois do percentual
oficial.

## Frequência sugerida

| Script | Frequência | Observação |
|---|---|---|
| `carga_status_report` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat` |
| `sincronizar_surveys_vant` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat`; escreve no Portal a cada execução |
| `carga_estacoes_zeus` | quando o cadastro das estações mudar | só o cadastro |
| `carga_monitoramento_zeus` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat` agendado |
| `vincular_talhao_estacao` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat` |
| `indicadores_clima_talhao` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat` |
| `carga_linhas_falha` | por entrega | pelo relatório sob demanda, a partir de `ENTRADAS\LINHAS`; ou à mão |
| `mapa_calor_falhas` | por entrega | refeito pela carga das linhas |
| `carga_mancha_solos` | quando a mancha mudar | camada de referência |
| `vincular_talhao_manejo` | quando os talhões ou a mancha mudarem | sempre seguido da declividade |
| `declividade_talhao` | logo depois do vínculo | baixa os tiles só na primeira vez |
| `carga_matriz_plantio` | quando a matriz for revisada | |
| `classificar_epoca_plantio` | diária, 6h | pelo `ATUALIZAR_DIAGNOSTICO.bat`; acompanha a data do PIMS |
| `criar_view_relatorio` | só quando a definição mudar | |
| `solicitar_relatorio_falhas` | sob demanda | pelo `GERAR_RELATORIO_FALHAS.bat`; ver [08](08-relatorio-sob-demanda.md) |
| `gerar_relatorio_falhas` | sob demanda | ou após novas cargas |

Para agendar: a tarefa precisa rodar com o usuário do Windows que tem o Pro
autenticado no geoportal, porque a conexão usa `GIS("pro")`.

## Atualização diária dos dados

Tarefa `\GEOTECNOLOGIA\atualizar_diagnostico`, todo dia às **6h**, depois da
atualização da base das 5h (que leva de 7 a 28 minutos): o vínculo e o clima
dependem dela. Roda o `ATUALIZAR_DIAGNOSTICO.bat` da raiz do clone, em quatro
grupos independentes — a falha de um não impede os outros:

- **A.** `carga_status_report.py --gravar` → `Status_Report_VANT` (percentual oficial)
- **B.** `sincronizar_surveys_vant.py --gravar` → `STG_PORTE_AVALIACAO`,
  `STG_VOO_MISSAO` e correção do chavesig no Portal
- **C.** `carga_monitoramento_zeus.py --gravar` → `vincular_talhao_estacao.py` →
  `indicadores_clima_talhao.py`; dentro do C, cada etapa só roda se a anterior
  terminou bem
- **D.** `classificar_epoca_plantio.py` → `EPOCA_PLANTIO_TALHAO`; usa a data de
  plantio do PIMS, então vem depois do A

Log em `D:\GEO\LOGS\atualizacao_diagnostico_<data>_<conta>.log`. A tarefa roda na
conta do João e só com a sessão dele aberta no servidor — desconectada serve.

**Conexão com o BigQuery.** O percentual oficial usa a conexão do ArcGIS que fica
no OneDrive do João (`Documentos\ArcGIS\Projects\gdb_atvos`), a mesma do
`atualizar_base.py`. A tabela é aberta pelo nome completo: listar as tabelas do
`gold_arcgis` trava o arcpy. A cópia da conexão em `D:\GEO\TALHOES` trava
esperando login.

**De onde vem a chuva, por enquanto.** O servidor ainda não lê o BigQuery.
Quem tem a conexão no próprio computador abre a planilha de monitoramento no
Excel, clica em **Atualizar tudo** e salva em
`Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\CLIMA`. A tarefa das 6h carrega o que
estiver lá. Sem atualizar o Excel, ela recarrega o mesmo conteúdo — e o log
avisa quando a planilha termina mais de 3 dias antes de ontem.

**O que protege a tabela.** A carga apaga e regrava. Antes de apagar, compara a
planilha com o banco e **não grava nada** se a planilha tiver colunas diferentes,
menos dias, menos estações, menos linhas ou estação+dia repetido. Antes de
gravar, copia a tabela para `D:\GEO\FALHAS\clima_backup.gdb`; se a gravação
falhar no meio, devolve a cópia.

**Percentual oficial e surveys.** Também leem tudo antes de apagar e **não
gravam** se a origem vier vazia ou com menos da metade das linhas que o banco já
tem (`protecao.py`). Se a gravação falhar no meio, devolvem as linhas
anteriores. Os surveys só corrigem o Portal com `--gravar`.

Para rodar à mão — sem `--gravar`, todas só simulam:

```
propy -u src\carga\carga_status_report.py        [--gravar]
propy -u src\carga\sincronizar_surveys_vant.py   [--gravar]
propy -u src\carga\carga_monitoramento_zeus.py   [--gravar]
ATUALIZAR_DIAGNOSTICO.bat                          (tudo, gravando)
```

## Linhas de falha e mapa de calor

Quem pede o relatório baixa as linhas da fazenda na Bem Agro e salva em
`Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\LINHAS`. O `GERAR_RELATORIO_FALHAS.bat`
carrega o que estiver lá antes de conferir a fazenda, pedindo confirmação. A
carga cruza com a `BASE_SAFRA`, troca as linhas dos talhões que vieram, refaz o
mapa de calor da fazenda em `D:\GEO\FALHAS\rasters_calor` e move a entrega para
`ENTRADAS\LINHAS\CARREGADAS\<lote>_<conta>`.

Para rodar à mão:

```
propy -u src\carga\carga_linhas_falha.py                  (simula)
propy -u src\carga\carga_linhas_falha.py --gravar         (grava)
propy -u src\carga\carga_linhas_falha.py --pasta D:\x     (outra pasta de entrada)
propy -u src\processamento\mapa_calor_falhas.py 320127    (só o mapa de calor)
```

**Acesso à pasta.** No servidor, a pasta só está sincronizada no OneDrive do
João, e fica sempre no disco. As contas liberadas para o relatório têm
permissão de modificar nela; conta nova precisa da mesma permissão, senão a
ferramenta avisa e o relatório sai com as linhas que já estavam no banco.

## Parâmetros a revisar

| Onde | Parâmetro | Valor atual | Pendente |
|---|---|---|---|
| `carga_linhas_falha` | `ESPACAMENTO_M` | 1.5 | de-para dos códigos `ESPAC`; só na conferência |
| `carga_linhas_falha` | `PASTAS_ENTRADA` | `ENTRADAS\LINHAS` no OneDrive de quem roda, senão no do João | |
| `carga_linhas_falha` | `FAZENDA_MINIMA_PCT` / `SEM_TALHAO_MAXIMO_PCT` | 1 / 50 | fazenda de borda / área fora do inventário |
| `mapa_calor_falhas` / `gerar_relatorio` | `PASTA_SAIDA` / `PASTA_RASTERS` | `D:\GEO\FALHAS\rasters_calor` | têm de ser a mesma |
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
| `carga_monitoramento_zeus` | `PASTA_ENTRADA` | `ENTRADAS\CLIMA` no OneDrive do João | só existe na conta que sincroniza a pasta |
| `carga_monitoramento_zeus` | `DIAS_SEM_ATUALIZAR_ALERTA` | 3 | a partir daí o log avisa que o Excel não foi atualizado |
| `protecao` | `QUEDA_MAXIMA_PCT` | 50 | queda de linhas acima disso não é gravada |
| `carga_status_report` | `BQ` | conexão do ArcGIS no OneDrive do João | só funciona nessa conta |

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

**`NADA FOI GRAVADO` na carga do monitoramento.** A conferência achou a planilha
menor que o banco — o motivo vem logo abaixo. A tabela não foi tocada. Quase
sempre é a consulta do Excel atualizada pela metade ou editada: atualize de novo
e salve.

**`ALERTA: a planilha termina em ...`** A chuva ainda vem da planilha do Excel.
Atualize a planilha e salve em `ENTRADAS\CLIMA`.

**`NADA FOI GRAVADO: a origem ...`** no percentual oficial ou nos surveys. A
leitura veio vazia ou muito menor que o banco, e a tabela não foi tocada. Rode a
carga de novo sem `--gravar` e confira o número de linhas antes de gravar.

**`NADA CARREGADO: nao consegui abrir a entrega`** nas linhas. O arquivo ainda
está sincronizando ou veio corrompido. Espere o OneDrive terminar e peça de
novo; se repetir, baixe de novo.

**`NADA CARREGADO: ... fora dos talhoes da BASE_SAFRA`.** A fazenda não está no
inventário vigente, ou foi baixada a área errada. A entrega fica na pasta; tire
de lá depois de conferir.

**`nao consegui abrir a pasta de linhas com a conta ...`.** A conta não tem
permissão na pasta do OneDrive do João. Ver
[linhas de falha](#linhas-de-falha-e-mapa-de-calor).

**`o mapa de calor da fazenda ... nao foi gerado`.** As linhas entraram, mas o
Spatial Analyst não estava disponível ou deu erro. O relatório sai sem o mapa
de calor até rodar `mapa_calor_falhas.py <fazenda>`.

## Validação após execução

A área piloto (fazenda 320127) é o caso de referência. Valores esperados:

| Verificação | Esperado |
|---|---|
| Talhão 6, `FALHA_PCT` | 23,8 |
| Talhão 6, m/ha | ~1.581 |
| DAP do voo | 127 |
| Dias entre porte e voo | 14 |
| Chuva 0–30 DAP | 96,4 mm (unidade: 144,7) |
| Chuva 30 dias antes do plantio | sem registro na estação USL_320121 |
| Talhões 4, 5 e 6: unidade de manejo | 7 |
| Talhão 7: unidade de manejo | 9 |
| Talhão 4: faixa de declividade | `> 5%` (mediana 6,21%) |
| Talhões 4 a 7: período e classe da época | `Mar 1Q`, `Favoravel` |
| Integridade da view | linhas = chavesig distintos |
