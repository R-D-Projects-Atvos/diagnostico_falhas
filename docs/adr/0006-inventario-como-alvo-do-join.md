# ADR 0006 — Falhas cruzadas contra o inventário

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A Atvos mantém duas bases de talhões:

- **Inventário** (`BASE_SAFRA`): mapa pré-plantio da safra.
- **Database** (`TALHOES_DATABASE`): base atual de campo, pós-plantio.

Assim que sai o apontamento de plantio, o talhão muda para a safra seguinte e
passa a valer o mapa pós-plantio. Talhões plantados em faixas existem separados
no pré-plantio (talhão 1 e talhão 6001) e unificados no pós-plantio, com a área
somada.

**As falhas são divulgadas sobre o polígono pré-plantio**, e o PIMS divulga o
percentual por talhão de inventário **separado** — 1 e 6001 aparecem como linhas
distintas.

## Decisão

O spatial join das linhas de falha é contra a `BASE_SAFRA`. A `LINHAS_FALHA`
grava `SAFRA_INV` e `CAMADA_INV` para registrar contra qual inventário o cálculo
foi feito.

## Consequências

Cruzar com a base atual traria geometria errada e faria as faixas desaparecerem.

O relatório é um **retrato histórico**: reprocessar a mesma área depois da
virada da safra precisa encontrar a mesma geometria. Por isso a camada de
inventário precisa ser preservada por safra, e não sobrescrita.

Para áreas de safras anteriores, o join vai no `HISTORICO_SAFRA`.

## Descompasso conhecido

Porte e missão são preenchidos cerca de 90 dias após o plantio, quando o piloto
já vê o mapa pós-plantio. Em áreas com faixas, o `cod_talhao` do survey e o
talhão do inventário não são a mesma coisa. Não é bloqueante — o vínculo do
porte é com a área voada, não com a subdivisão — mas exigiria um de-para
inventário → database se for necessário precisão nesse ponto.
