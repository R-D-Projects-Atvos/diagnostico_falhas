# ADR 0009 — Ressalva de época só quando a faixa vizinha mudaria a classe

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A declividade marca como `Ressalva` o talhão cuja mediana cai a até 0,5 ponto
de uma fronteira entre faixas. São 36% dos talhões, porque a distribuição real
se concentra em torno de 2,5%.

## Decisão

Na classificação da época de plantio a pergunta muda: **se este talhão
estivesse na faixa vizinha, a recomendação para o período em que ele foi
plantado seria diferente?** Só nesse caso a classificação recebe `Ressalva`,
com a classe da faixa vizinha em `CLASSE_ALTERNATIVA`.

A classificação também recebe `Ressalva` quando a unidade de manejo
predominante cobre menos de 60% do talhão.

## Alternativa descartada

**Herdar a ressalva da declividade.** Um terço dos talhões apareceria como
incerto, e ninguém lê uma ressalva que aparece em um de cada três casos.

A regra escolhida reduz muito o alarme: em 5 das 14 unidades de manejo as
faixas `< 2,5%` e `2,5 a 5%` dão a mesma recomendação nos 17 períodos, e nas
outras 9 diferem em 1 a 3 períodos.

## Consequências

A ressalva passa a significar "a classe pode ser outra", não "a medida é
imprecisa". O relatório mostra a classe alternativa ao lado.

## Nota

A versão de 31/08/2026 testa a faixa vizinha em **todo** talhão, sem olhar se a
mediana está perto da fronteira. Um talhão com 1,2% de declividade pode sair com
"declividade próxima da fronteira". Ver [pendências](../07-pendencias.md).
