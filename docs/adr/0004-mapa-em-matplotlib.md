# ADR 0004 — Mapa desenhado em matplotlib

**Data:** agosto/2026
**Situação:** aceita

## Contexto

O relatório precisa de um mapa de calor por área. As opções eram layout do
ArcGIS Pro com Map Series, ou desenho por código.

## Alternativa avaliada: layout do Pro

O Pro entrega de graça o mapa, o ortomosaico, o cabeçalho por texto dinâmico e
a tabela por Table Frame filtrado pela página.

Mas o texto dinâmico **escreve valores, não muda cor nem tamanho conforme o
valor**. Indicadores com semáforo, barras comparativas dimensionadas e a linha
do tempo exigiriam percorrer as páginas com `arcpy.mp` e editar elementos via
CIM antes de exportar cada uma — cerca de 150 linhas de manipulação de CIM.

Pior: chart frames ficam presos à camada, não à feição da página, então o
gráfico de chuva não mudaria por área.

E o layout viveria num `.aprx` que qualquer pessoa pode abrir e alterar.

## Decisão

Desenhar mapa e gráfico com matplotlib, a partir do raster e dos polígonos, e
montar o documento em HTML.

## Consequências

**Boas.** O desenho inteiro está versionado. Mudar a régua de cores ou incluir
um indicador é editar código, não remontar layout. O relatório não depende de
nenhum arquivo de projeto.

**Ruins.** Perde-se a qualidade cartográfica de um layout do Pro — escala
gráfica, norte, grade de coordenadas. Para o público do relatório isso não fez
falta, mas é uma limitação real.

**Sobre o SR.** O raster está em UTM 21S e os polígonos em 4326; o desenho
projeta os polígonos com `projectAs` para o SR do raster.
