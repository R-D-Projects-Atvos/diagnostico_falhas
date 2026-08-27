# ADR 0005 — O percentual exibido é sempre o do PIMS

**Data:** agosto/2026
**Situação:** aceita

## Contexto

Com as linhas de falha carregadas, é tecnicamente possível recalcular o
percentual de falhas a partir dos metros. A validação mostrou que o cálculo
reproduz o oficial com cerca de 1% de diferença.

## Decisão

O relatório exibe o `FALHA_LINHA` da `STATUS_REPORT_VANT`, que veio do PIMS.
Nunca o valor recalculado.

Os metros servem para m/ha, tamanho médio, mapa de calor e priorização de
replantio.

## Consequências

Se o produto exibisse um número próprio, haveria dois percentuais divergentes
circulando na empresa — o do PIMS e o do relatório. Numa reunião de comitê,
isso destrói a credibilidade do material e desloca a conversa para "qual dos
dois está certo".

A área exibida também vem do PIMS, não do inventário, pelo mesmo motivo: é o
denominador do número oficial, e misturar as origens faria o denominador
exibido não corresponder ao percentual exibido.

## Nota

A validação continua útil: ela prova que o dado carregado é o mesmo que gerou o
número oficial. É verificação, não fonte.
