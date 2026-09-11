# Changelog

Formato: o que mudou e por quê. Versões seguem `MAJOR.MINOR`.

## [Em andamento]

### Adicionado

- Relatório sob demanda no servidor: `GERAR_RELATORIO_FALHAS.bat` pede o código
  da fazenda, mostra o que encontrou para conferência e gera o PDF numa pasta
  própria por usuário e por execução. Liberado para João, Mateus, Leonardo e
  Rafael Miranda. Ver `docs/08-relatorio-sob-demanda.md`.
- A produção passa a rodar do clone em `D:\GEO\REPOS\diagnostico_falhas`; em
  `D:\GEO\CODIGOS` ficam só avisos apontando para cá.
- Atualização diária do clima: `ATUALIZAR_CLIMA.bat`, agendado às 6h, carrega o
  monitoramento Zeus da planilha de `ENTRADAS\CLIMA` (com conferência antes de
  apagar e cópia da tabela), refaz o vínculo talhão–estação e os indicadores.
  A consulta do Excel foi guardada em `sql/monitoramento_zeus.sql`.

### Corrigido

- Chuva antes do plantio: janela sem nenhum registro na estação era gravada como
  0,0 mm, e o relatório afirmava que não tinha chovido. Agora fica nula, fora da
  média da unidade, e o relatório diz que não há registro. A área piloto
  (320127) estava nesse caso.

## [0.2] — agosto/2026

Solo, declividade e época de plantio no relatório, para USL-UEL, e janela de
chuva antes do plantio. Em produção desde 31/08/2026; versionada em 11/09/2026.

### Adicionado

- Mancha de solos publicada no geodatabase como `SOLOS_ATVOS` (1.260 polígonos,
  USL-UEL).
- Vínculo talhão–unidade de manejo pela mancha predominante em área
  (`TALHAO_MANEJO`, 7.050 talhões).
- Declividade por talhão sobre o Copernicus GLO-30, pela mediana (ADR 0008).
- Matriz de Plantio carregada da planilha, lida pela cor das células
  (`MATRIZ_PLANTIO`, 714 combinações).
- Classificação da época de plantio por talhão, com condição de manejo e
  ressalva quando a classe poderia ser outra (`EPOCA_PLANTIO_TALHAO`, 5.520
  talhões; ADR 0009).
- Janela de chuva de −30 a −1 DAP, com média da unidade.
- Na view: unidade de manejo, declividade, época de plantio, ressalva e
  `EPOCA_FORA_DA_INDICADA` (ADR 0010).
- No relatório: bloco "Época de plantio" com a faixa do ano; unidade de manejo e
  declividade no cabeçalho; mapa das linhas de falha como vieram da Bem Agro;
  gráfico e leitura de chuva cobrindo antes e depois do plantio.

### Alterado

- O relatório sai com o percentual do PIMS mesmo quando a fazenda não tem linhas
  de falha carregadas, sem o detalhamento espacial.
- Altura máxima das figuras de mapa reduzida, para os dois mapas caberem na
  página 2.

### Conhecido e não resolvido

Chuva antes do plantio gravada como zero quando a estação não tem registro;
bloco de época montado com o primeiro talhão; ressalva de fronteira aplicada
longe da fronteira; talhões fora do inventário sem classe; mancha de solos
incompleta em USL-UEL. Ver `docs/07-pendencias.md`.

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
