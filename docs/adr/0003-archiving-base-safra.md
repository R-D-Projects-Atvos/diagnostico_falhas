# ADR 0003 — Filtro de archiving em consulta SQL direta

**Data:** agosto/2026
**Situação:** aceita

## Contexto

A primeira versão da `VW_RELATORIO_FALHAS` retornou **453.069 linhas** onde
deveriam ser 4.611 — cerca de 98 cópias de cada talhão, com valores corretos.

Investigação: o ArcGIS conta 25.710 feições na `BASE_SAFRA`, mas o SQL direto
vê **3.377.480 linhas**, com 28.473 chavesig distintos (mais que os vigentes).

A camada tem **archiving ligado** no geodatabase. Cada edição cria linha nova e
aposenta a anterior; as ~137 cópias por talhão correspondem aos dias em que a
rotina das 5h atualizou o registro. O ArcGIS filtra sozinho, o SQL cru não.

## Decisão errada, e por que foi descartada

A primeira correção proposta foi deduplicar com `ROW_NUMBER() OVER (PARTITION
BY Chavesig ORDER BY Safra DESC, OBJECTID DESC)`.

**Isso teria sido pior que o problema.** Todas as 137 cópias têm o mesmo
`OBJECTID` e a mesma safra, então a escolha seria arbitrária e poderia recair
sobre uma versão histórica. A contagem ficaria certa e o dado, errado.

## Decisão adotada

Filtrar a linha vigente no próprio join:

```sql
LEFT JOIN ATVOSPUBLICADOR.BASE_SAFRA AS b
       ON b.Chavesig = s.Layer
      AND b.GDB_TO_DATE = '9999-12-31 23:59:59'
```

Alternativa equivalente e independente de formato: `b.GDB_TO_DATE > GETDATE()`.

## Consequências

Qualquer consulta SQL direta a camadas com archiving precisa desse filtro. Vale
auditar outras rotinas que leem `BASE_SAFRA` ou `TALHOES_DATABASE` por SQL — o
sintoma seria contagem inflada ou dado antigo aparecendo.

Cursores do arcpy respeitam o archiving automaticamente. Onde possível, prefira
cursor a SQL direto para essas camadas.

## Achado colateral

A tabela cresce cerca de 25 mil linhas por dia porque a rotina reescreve todos
os talhões diariamente, mesmo os inalterados. Registrado nas
[pendências](../07-pendencias.md).
