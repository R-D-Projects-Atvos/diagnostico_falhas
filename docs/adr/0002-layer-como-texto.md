# ADR 0002 — `Layer` como texto de 14 posições

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A `Status_Report_VANT` existia no SQL Server com o campo `Layer` como
`BigInteger`. No BigQuery, o mesmo campo é `STRING`.

O `Layer` **é o Chavesig** — 14 dígitos, com zeros à esquerda quando o código da
fazenda começa com zero.

## Decisão

Recriar a tabela com `Layer` como `TEXT(14)`.

## Consequências

Fazendas com código iniciado em zero deixariam de casar com a `LINHAS_FALHA` se
o campo fosse numérico — o dígito seria perdido na conversão.

A tabela estava vazia, então não houve dado a preservar. Aproveitou-se para
ajustar tamanhos de texto (255 genéricos para valores realistas), acrescentar
`DATA_CARGA` e criar índices em `Layer` e `CD_UPNIVEL1`.

## Regra geral

Identificador com zero à esquerda é texto. Sempre.
