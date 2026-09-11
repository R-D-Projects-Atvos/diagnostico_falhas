# 02 — Arquitetura

## Princípio

Tudo pousa no SQL Server corporativo antes de ser consumido. O relatório e
qualquer painel futuro leem de um lugar só, e nenhum deles depende do
BigQuery, do Portal ou do fornecedor estarem no ar em tempo de consulta.

## Fluxo

```
FONTES                        CARGA                    CONSOLIDAÇÃO      SAÍDA

BigQuery                      carga_status_report      ┐
gold_arcgis.Operacao_Vant ──► STATUS_REPORT_VANT       │
(% oficial do PIMS)                                    │
                                                       │
Shapefile Bem Agro            carga_linhas_falha       │
FALHAS.shp (linhas/metro) ──► LINHAS_FALHA             │
                              + spatial join           │
                                                       ├─► VW_RELATORIO_FALHAS
SDE                                                    │        │
BASE_SAFRA (inventário) ──────────────────────────────►│        │
                                                       │        ▼
Survey123 (Portal)            sincronizar_surveys      │   gerar_relatorio
Porte + Registro de Missão ─► STG_PORTE_AVALIACAO      │        │
                              STG_VOO_MISSAO           │        ├─► HTML
                                                       │        └─► PDF
Planilhas Zeus                carga_estacoes_zeus      │
(BigQuery, provisório)    ──► ESTACOES_ZEUS            │   mapa de calor (PNG)
                              MONITORAMENTO_ESTACAO    │   linhas de falha (PNG)
                                     │                 │   chuva diária (PNG)
                                     ▼                 │
                              vincular_talhao_estacao  │
                              TALHAO_ESTACAO           │
                                     │                 │
                                     ▼                 │
                              indicadores_clima_talhao │
                              INDICADORES_CLIMA_TALHAO ┤
                                                       │
Mancha_Solos.shp              carga_mancha_solos       │
(USL-UEL)                 ──► SOLOS_ATVOS              │
                                     │                 │
                                     ▼                 │
                              vincular_talhao_manejo   │
Copernicus GLO-30         ──► declividade_talhao       │
(AWS, público)                TALHAO_MANEJO            │
                                     │                 │
Planilha Matriz Plantio       carga_matriz_plantio     │
(cor da célula)           ──► MATRIZ_PLANTIO           │
                                     │                 │
                                     ▼                 │
                              classificar_epoca_plantio│
                              EPOCA_PLANTIO_TALHAO ────┘
```

## Componentes

### Camada de carga (`src/carga/`)

Traz dado de fora para o SQL Server. Todas as cargas são **substituição
total**: leem a origem inteira, validam, apagam o destino e reinserem. Os
volumes são pequenos (milhares a dezenas de milhares de linhas) e isso elimina
a classe inteira de problemas de sincronização parcial.

Exceção: `carga_linhas_falha` é **idempotente por lote** — apaga e recarrega
apenas a entrega identificada pelo campo `LOTE`, porque a tabela acumula
entregas de áreas diferentes.

Toda carga lê a origem **antes** de apagar o destino e aborta se a origem vier
vazia. Sem isso, uma falha de conexão zeraria a tabela de produção.

### Camada de processamento (`src/processamento/`)

Deriva dado a partir do que foi carregado: vínculo espacial talhão–estação,
indicadores climáticos, mapa de calor, vínculo talhão–unidade de manejo,
declividade, classificação da época de plantio e a view consolidada.

### Camada de relatório (`src/relatorio/`)

Lê a view, desenha as figuras com matplotlib e monta o HTML por substituição
de marcadores. O PDF sai do próprio HTML, impresso por navegador headless.

A faixa do ano da Matriz de Plantio não é figura: é desenhada em HTML e CSS,
com uma consulta à `MATRIZ_PLANTIO` na hora de gerar o relatório.

## Decisões de tecnologia

**Por que matplotlib e não layout do ArcGIS Pro.** Um layout do Pro exige um
`.aprx` como molde e manipulação de CIM para colorir indicadores conforme o
valor. Isso funciona, mas amarra o relatório a um arquivo que qualquer pessoa
pode abrir e alterar sem querer. Com matplotlib o desenho inteiro está no
código, versionado. Ver [ADR 0004](adr/0004-mapa-em-matplotlib.md).

**Por que HTML e não docx ou layout paginado.** O HTML é editável por qualquer
um, renderiza igual em qualquer máquina e vira PDF com uma chamada de
navegador. Mudar a régua de cores ou incluir um indicador é editar template,
não remontar layout.

**Por que navegador headless para o PDF.** O Edge existe em toda máquina
Windows, respeita `@page { size: A4 landscape }` e não exige instalar nada.
Alternativas como wkhtmltopdf ou weasyprint exigiriam aprovação de software.

**Por que view e não tabela materializada.** A view sempre reflete o estado
atual de todas as fontes. As tabelas por trás dela já são materializadas, então
o custo de consulta é baixo. Se um dia o volume crescer, a materialização é
uma troca simples.

## Sistema de referência

O dataset `AGRICOLA_ATVOS` está em **GCS_WGS_1984 (EPSG 4326)**, geográfico.
Tudo que é criado dentro dele herda esse SR.

Consequências:

- O shapefile da Bem Agro também vem em 4326, então o spatial join sai sem
  reprojeção — zero risco de deslocamento.
- **Área e comprimento não podem ser calculados pela geometria** — `Shape.STArea()`
  vem em graus quadrados. Sempre usar os campos de área do cadastro.
- O **kernel density exige projeção**. O mapa de calor projeta para
  SIRGAS 2000 / UTM 21S (EPSG 31981) em memória; só o raster fica projetado.
- **Área de mancha e declividade** usam SIRGAS 2000 / UTM 22S (EPSG 31982). A
  interseção talhão × mancha de solos roda em memória; o modelo de elevação
  reamostrado para 30 m fica em `D:\GEO\DEM\declividade.gdb`.

## Autenticação

Os scripts que acessam o Portal usam `GIS("pro")`, aproveitando a sessão já
autenticada do ArcGIS Pro. Não há senha em arquivo. Consequência para
agendamento: a tarefa precisa rodar com o usuário do Windows que tem o Pro
conectado ao geoportal.

## Dependência de rede

O `declividade_talhao` baixa o modelo de elevação do bucket público do
Copernicus na AWS, sem credencial. Os tiles ficam em `D:\GEO\DEM` e só são
baixados na primeira execução. Se a rede corporativa bloquear o bucket, os
arquivos podem ser copiados à mão para essa pasta.
