# Changelog

Formato: o que mudou e por quê. Versões seguem `MAJOR.MINOR`.

## [0.1] — agosto/2026

Primeira versão funcional. Relatório gerado de ponta a ponta para a área
piloto (fazenda 320127, unidade USL, 4 talhões, 71,2 ha).

### Adicionado

- Carga do percentual oficial do BigQuery para `STATUS_REPORT_VANT`.
- Carga das linhas de falha da Bem Agro com spatial join contra o inventário.
- Mapa de calor por kernel density, escala fixa 280/500/1000 m/ha.
- Carga das estações Zeus e do monitoramento diário (170 estações, 66.160
  registros).
- Vínculo talhão–estação por proximidade e cadastro (27.507 linhas).
- Indicadores climáticos da janela 0–30 DAP com comparação à média da unidade.
- Staging dos surveys de porte e missão, com correção do chavesig na origem.
- View consolidada `VW_RELATORIO_FALHAS` (4.611 talhões).
- Gerador do relatório em HTML e PDF, com modo lote por meta.

### Corrigido

- `Layer` recriado como texto de 14 posições (ADR 0002).
- Filtro de archiving no join com a `BASE_SAFRA` (ADR 0003).
- 148 linhas de chavesig corrigidas nos dois surveys.
- Formatação de datas e números vindos como texto do driver ODBC.
- Quebra de página do PDF com imagem vazando para a página seguinte.

### Conhecido e não resolvido

Balanço hídrico bloqueado por falta de CAD e cobertura de ETo. Detecção de
fazenda parcialmente processada. Ver `docs/07-pendencias.md`.
