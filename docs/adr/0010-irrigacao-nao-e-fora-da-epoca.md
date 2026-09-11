# ADR 0010 — "Favorável com irrigação" não conta como fora da época

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A view expõe `EPOCA_FORA_DA_INDICADA`, um atalho para o semáforo do relatório:
o plantio caiu fora da época que a matriz indica?

A matriz tem quatro classes. `Favoravel com irrigacao` aparece sobretudo nos
meses de inverno e é a única que depende de uma condição de fora do calendário.

## Decisão

`EPOCA_FORA_DA_INDICADA` vale 1 só para `Restritivo`. `Favoravel com irrigacao`
vale 0.

No relatório essa classe não é pintada de vermelho: o título do bloco fica em
cinza e a célula da faixa do ano em azul-acinzentado. A nota escreve a condição
por extenso: "Plantio de inverno: a matriz o considera adequado quando há
irrigação ou salvamento."

## Alternativa descartada

**Somar ao restritivo.** Plantio de inverno é prática deliberada, e a matriz o
considera adequado com irrigação ou salvamento. Somar os dois exageraria o
problema.

## Consequências

Não há dado de irrigação nem de salvamento no banco. Um plantio de inverno feito
sem nenhum dos dois fica sem sinal no semáforo — o alerta existe só no texto da
nota.
