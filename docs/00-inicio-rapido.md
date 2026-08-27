# 00 — Início rápido

Para quem acabou de chegar no projeto e precisa entender em quinze minutos.

## O que este produto faz

Gera um relatório de diagnóstico das falhas de plantio, por fazenda, reunindo
cinco fontes de dado que já existiam na Atvos mas nunca conversavam.

## Leia nesta ordem

1. **[README](../README.md)** — visão geral e como rodar.
2. **[01 — Objetivo](01-objetivo-e-escopo.md)** — por que existe, o que está fora.
3. **[04 — Regras de negócio](04-regras-de-negocio.md)** — é aqui que está o
   conhecimento do produto. Se for ler só um documento, leia este.
4. **[ADRs](adr/)** — as decisões e seus porquês.

## As cinco coisas que mais confundem quem chega

**O percentual não é calculado aqui.** Vem do PIMS. O que este produto calcula é
detalhamento espacial. ([ADR 0005](adr/0005-percentual-oficial-do-pims.md))

**Existem duas bases de talhões.** Inventário é pré-plantio, database é
pós-plantio. As falhas usam o inventário.
([ADR 0006](adr/0006-inventario-como-alvo-do-join.md))

**A `BASE_SAFRA` tem archiving.** Consulta SQL direta sem filtro retorna 137
cópias de cada talhão. ([ADR 0003](adr/0003-archiving-base-safra.md))

**O chavesig dos surveys não é confiável.** É reconstruído no staging.
([ADR 0001](adr/0001-chavesig-reconstruido.md))

**O campo `Field` do shapefile da Bem Agro não é o talhão.** É o índice do
polígono no KML. O talhão vem por spatial join.

## Área de referência

Fazenda **320127**, unidade USL, talhões 4 a 7, plantio em 03/03/2026, voo em
08/07/2026. É a única área com linhas de falha carregadas e serve para validar
qualquer alteração. Valores esperados em [06 — Operação](06-operacao.md).

## Glossário

| Termo | Significado |
|---|---|
| **Chavesig** | identificador do talhão, 14 dígitos: fazenda(6) + setor(4) + talhão(4) |
| **DAP** | dias após o plantio |
| **Falha** | trecho sem cana no sulco de plantio |
| **Inventário** | mapa pré-plantio da safra (`BASE_SAFRA`) |
| **Database** | base atual de campo, pós-plantio (`TALHOES_DATABASE`) |
| **Talhão 6000** | faixa adicional de um talhão, existe só no pré-plantio |
| **Porte** | avaliação em campo que autoriza o voo de falhas |
| **PIC** | estação meteorológica da Zeus |
| **Veranico** | sequência de dias com menos de 5 mm de chuva |
| **CAD** | capacidade de água disponível do solo, em mm |
| **ETo / ETc** | evapotranspiração de referência / da cultura |
| **LengthComp** | comprimento da falha menos a tolerância de 0,30 m |
