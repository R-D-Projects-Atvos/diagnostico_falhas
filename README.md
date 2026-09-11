# Diagnóstico de Falhas de Plantio

Produto interno da equipe de **Cartografia — Geotecnologia / Atvos**.

Gera, por fazenda, um relatório de diagnóstico das falhas de plantio da cana,
reunindo o percentual oficial publicado no PIMS, o detalhamento espacial das
falhas levantadas por VANT, o registro do voo e da avaliação de porte, os
indicadores climáticos antes e depois do plantio e a época de plantio frente à
Matriz de Plantio.

O relatório sai em HTML e PDF, em A4 paisagem, e é gerado apenas para as
fazendas cuja média ponderada de falhas está acima da meta corporativa.

---

## Por que existe

O percentual de falhas já era publicado no PIMS, mas circulava como número
solto. Não havia como responder três perguntas que o comitê agrícola faz
sempre:

1. **Onde** a falha está dentro da área — reboleira localizada ou problema
   difuso? A resposta muda o encaminhamento.
2. **O clima explica?** Sem a comparação com a média da unidade, 96 mm de
   chuva não significa nada.
3. **O processo funcionou?** Quantos dias entre o porte aprovado e o voo,
   entre o voo e a publicação do resultado.
4. **A época de plantio era a indicada?** A Matriz de Plantio diz, para cada
   unidade de manejo de solo e faixa de declividade, quando plantar. É o
   indicador que aponta causa fora do clima.

O produto responde às quatro a partir de dados que já existiam na empresa.

---

## Arquitetura em uma frase

Cinco fontes convergem por `Chavesig` numa view no SQL Server
(`VW_RELATORIO_FALHAS`); um gerador em Python lê essa view, desenha o mapa
de calor e o gráfico de chuva, e produz o HTML e o PDF.

```
BigQuery (Bem Agro)  ─┐
Shapefile Bem Agro   ─┤
BASE_SAFRA (SDE)     ─┼──► VW_RELATORIO_FALHAS ──► gerador ──► HTML + PDF
Survey123 (2 surveys)─┤
Estações Zeus        ─┘
```

Detalhes em [`docs/02-arquitetura.md`](docs/02-arquitetura.md).

---

## Estado atual

| Bloco | Situação |
|---|---|
| Percentual oficial (PIMS via BigQuery) | em produção, atualizado todo dia às 6h |
| Linhas de falha e mapa de calor | funcionando; 1 área carregada (piloto) |
| Voo e porte (Survey123) | em produção, atualizado todo dia às 6h; cobertura baixa por preenchimento |
| Indicadores climáticos | em produção, 4.604 talhões, janelas antes e depois do plantio; atualizados todo dia às 6h a partir da planilha do Excel |
| Solo, declividade e época de plantio | em produção só para USL-UEL, 5.520 talhões; problemas conhecidos em [pendências](docs/07-pendencias.md) |
| Balanço hídrico / CAD | **bloqueado** — ver [pendências](docs/07-pendencias.md) |
| Ortomosaico no relatório | espaço reservado, sem decisão |

---

## Como rodar

Pré-requisitos: ArcGIS Pro com arcpy, extensão Spatial Analyst, conexão SDE
para o SQL Server corporativo e conexão para o BigQuery, ambas configuradas
no Catalog. Todos os scripts rodam no `arcgispro-py3`.

```bash
# 1. cópia local do percentual oficial (BigQuery -> SQL Server)
python -u src/carga/carga_status_report.py --gravar        # sem --gravar, simula

# 2. estações meteorológicas (só quando o cadastro mudar) e monitoramento diário
python -u src/carga/carga_estacoes_zeus.py
python -u src/carga/carga_monitoramento_zeus.py --gravar   # sem --gravar, simula

# 3. staging dos surveys + correção do chavesig na origem
python -u src/carga/sincronizar_surveys_vant.py --gravar   # sem --gravar, simula

# 4. vínculo talhão -> estação (proximidade / cadastro)
python -u src/processamento/vincular_talhao_estacao.py

# 5. indicadores climáticos da janela 0-30 DAP
python -u src/processamento/indicadores_clima_talhao.py

# o 1, o 3, o monitoramento, o 4 e o 5 rodam todo dia às 6h pelo ATUALIZAR_DIAGNOSTICO.bat

# 6. mancha de solos e vínculo talhão -> unidade de manejo
python -u src/carga/carga_mancha_solos.py
python -u src/processamento/vincular_talhao_manejo.py

# 7. declividade (sempre depois do vínculo, que regrava a tabela)
python -u src/processamento/declividade_talhao.py

# 8. Matriz de Plantio e classificação da época de plantio
python -u src/carga/carga_matriz_plantio.py
python -u src/processamento/classificar_epoca_plantio.py

# 9. linhas de falha de uma entrega da Bem Agro
python -u src/carga/carga_linhas_falha.py

# 10. mapa de calor da entrega
python -u src/processamento/mapa_calor_falhas.py

# 11. view consolidada
python -u src/processamento/criar_view_relatorio.py

# 12. relatórios
python -u src/relatorio/gerar_relatorio_falhas.py           # lote
python -u src/relatorio/gerar_relatorio_falhas.py 320127    # uma fazenda

# ou, no servidor, sob demanda e com conferência da fazenda antes de gerar
D:\GEO\REPOS\diagnostico_falhas\GERAR_RELATORIO_FALHAS.bat  # ver docs/08
```

Ordem, dependências e agendamento em [`docs/06-operacao.md`](docs/06-operacao.md).

---

## Onde as coisas ficam

| O quê | Onde |
|---|---|
| Este repositório — **a produção roda daqui**, na `main` | `D:\GEO\REPOS\diagnostico_falhas` |
| Relatórios do lote | `D:\GEO\FALHAS\relatorios` |
| Relatórios sob demanda | `D:\GEO\FALHAS\sob_demanda` |
| Rasters do mapa de calor | `D:\GEO\FALHAS\rasters.gdb` |
| Registro do relatório sob demanda | `D:\GEO\LOGS` |
| Planilha de monitoramento Zeus (atualizada no Excel) | `Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\CLIMA` |
| Log da atualização diária | `D:\GEO\LOGS\atualizacao_diagnostico_<data>_<conta>.log` |

**Não copie os scripts para `D:\GEO\CODIGOS`.** Lá ficaram só avisos apontando
para cá. Para atualizar a produção, `git pull` neste clone.

A conexão `D:\GEO\TALHOES\SQLServer-10-gisdb(atvospublicador).sde` fica fora do
repositório: carrega credencial.

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [00 — Início rápido](docs/00-inicio-rapido.md) | **comece por aqui** |
| [01 — Objetivo e escopo](docs/01-objetivo-e-escopo.md) | problema, público, o que está fora |
| [02 — Arquitetura](docs/02-arquitetura.md) | fluxo, componentes, tecnologias |
| [03 — Modelo de dados](docs/03-modelo-de-dados.md) | tabelas, campos, chaves |
| [04 — Regras de negócio](docs/04-regras-de-negocio.md) | todos os cálculos e critérios |
| [05 — Fontes de dados](docs/05-fontes-de-dados.md) | origem, formato, limitações |
| [06 — Operação](docs/06-operacao.md) | execução, agendamento, problemas conhecidos |
| [07 — Pendências](docs/07-pendencias.md) | backlog técnico e bloqueios |
| [08 — Relatório sob demanda](docs/08-relatorio-sob-demanda.md) | gerar o relatório de uma fazenda pelo servidor, com conferência |
| [ADRs](docs/adr/) | decisões arquiteturais e seus porquês |

---

## Convenções do repositório

Branches: `main` estável, `feat/*` para novidades, `fix/*` para correções.
Commits em português, no imperativo (`acrescenta gráfico de chuva diária`).
Toda decisão que alguém possa questionar depois vira um ADR em `docs/adr/`.

Joao
