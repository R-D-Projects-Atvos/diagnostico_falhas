# Diagnóstico de Falhas de Plantio

Produto interno da equipe de **Cartografia — Geotecnologia / Atvos**.

Gera, por fazenda, um relatório de diagnóstico das falhas de plantio da cana,
reunindo o percentual oficial publicado no PIMS, o detalhamento espacial das
falhas levantadas por VANT, o registro do voo e da avaliação de porte, e os
indicadores climáticos da janela de brotação.

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

O produto responde às três a partir de dados que já existiam na empresa,
espalhados por cinco sistemas.

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
| Percentual oficial (PIMS via BigQuery) | em produção, 4.611 talhões |
| Linhas de falha e mapa de calor | funcionando; 1 área carregada (piloto) |
| Voo e porte (Survey123) | em produção; cobertura baixa por preenchimento |
| Indicadores climáticos | em produção, 4.604 talhões |
| Balanço hídrico / CAD | **bloqueado** — ver [pendências](docs/07-pendencias.md) |
| Ortomosaico no relatório | espaço reservado, sem decisão |

---

## Como rodar

Pré-requisitos: ArcGIS Pro com arcpy, extensão Spatial Analyst, conexão SDE
para o SQL Server corporativo e conexão para o BigQuery, ambas configuradas
no Catalog. Todos os scripts rodam no `arcgispro-py3`.

```bash
# 1. cópia local do percentual oficial (BigQuery -> SQL Server)
python -u src/carga/carga_status_report.py

# 2. estações meteorológicas e monitoramento diário
python -u src/carga/carga_estacoes_zeus.py

# 3. staging dos surveys + correção do chavesig na origem
python -u src/carga/sincronizar_surveys_vant.py

# 4. vínculo talhão -> estação (proximidade / cadastro)
python -u src/processamento/vincular_talhao_estacao.py

# 5. indicadores climáticos da janela 0-30 DAP
python -u src/processamento/indicadores_clima_talhao.py

# 6. linhas de falha de uma entrega da Bem Agro
python -u src/carga/carga_linhas_falha.py

# 7. mapa de calor da entrega
python -u src/processamento/mapa_calor_falhas.py

# 8. view consolidada
python -u src/processamento/criar_view_relatorio.py

# 9. relatórios
python -u src/relatorio/gerar_relatorio_falhas.py           # lote
python -u src/relatorio/gerar_relatorio_falhas.py 320127    # uma fazenda
```

Ordem, dependências e agendamento em [`docs/06-operacao.md`](docs/06-operacao.md).

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
| [ADRs](docs/adr/) | decisões arquiteturais e seus porquês |

---

## Convenções do repositório

Branches: `main` estável, `feat/*` para novidades, `fix/*` para correções.
Commits em português, no imperativo (`acrescenta gráfico de chuva diária`).
Toda decisão que alguém possa questionar depois vira um ADR em `docs/adr/`.

Joao
