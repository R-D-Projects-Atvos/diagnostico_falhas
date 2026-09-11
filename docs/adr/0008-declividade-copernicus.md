# ADR 0008 — Declividade pelo Copernicus GLO-30, pela mediana

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A Matriz de Plantio muda a recomendação conforme a faixa de declividade do
talhão: `< 2,5%`, `2,5 a 5%` e `> 5%`. Não havia declividade por talhão no
banco.

A fronteira que a matriz mais discrimina é a de 2,5%, e é justamente em torno
dela que a distribuição real dos talhões se concentra.

## Decisão

Declividade calculada sobre o **Copernicus DEM GLO-30**, baixado do bucket
público da AWS. O modelo é mosaicado, projetado para UTM 22S a 30 m, suavizado
por média 3 × 3 e convertido em declividade percentual. Cada talhão recebe a
**mediana** dos pixels.

Quando a mediana fica a até 0,5 ponto de uma fronteira, o talhão é marcado com
`DECLIV_CONFIANCA = 'Ressalva'`.

## Alternativas descartadas

**SRTM.** Mesma resolução de 30 m, mas erro vertical de 6 a 16 m contra 2 a 4 m
do Copernicus, e imageamento de 2000 contra 2011–2015. Numa encosta de 2,5% o
SRTM opera no limite do próprio ruído.

**Média da declividade no talhão.** O Copernicus é modelo de superfície: cana
alta no momento do imageamento vira relevo e gera pixels espúrios. A média os
absorve; a mediana os ignora.

## Consequências

A vegetação no modelo é mitigada, não eliminada. A suavização reduz o ruído
pixel a pixel, que numa encosta de 2,5% é da mesma ordem do sinal medido.

36% dos talhões ficam perto de uma fronteira. Marcar todos como incertos
tornaria a ressalva inútil — ver [ADR 0009](0009-ressalva-so-quando-muda-a-classe.md).

A primeira execução depende de acesso ao bucket da AWS. Se a rede corporativa
bloquear, os tiles precisam ser copiados à mão para `D:\GEO\DEM`.
