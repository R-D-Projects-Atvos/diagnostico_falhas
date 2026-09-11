# 05 — Fontes de dados

## 1. Bem Agro — percentual oficial

**Origem:** `dl-bq-prd.gold_arcgis.Operacao_Vant` (BigQuery, é uma **view**).

Uma linha por talhão, sem repetição — 4.611 registros, `DATA_AMOSTRA` de
01/04/2026 a 25/08/2026.

Pontos de atenção descobertos:

- O campo **`Layer` já é o Chavesig** de 14 dígitos. Não é preciso concatenar
  `CD_UPNIVEL1/2/3`. Vem como STRING no BigQuery.
- `CD_UPNIVEL2` vem como `1`, não `0001` — filtro por setor precisa disso.
- **`DATA_AMOSTRA` é a data de publicação no PIMS**, não a do voo. A data do
  voo está no Registro de Missão.
- `DPP` é dinâmico, conta até a data da consulta. Inútil para o relatório.
- A `Area_total` daqui **diverge levemente** da área do inventário. O
  relatório usa a do PIMS, porque é o denominador do percentual oficial.
- Sendo uma view, a lógica pode mudar na origem sem aviso. Vale saber quem a
  mantém.

**Carga:** `src/carga/carga_status_report.py`, substituição total.

## 2. Bem Agro — linhas de falha

**Origem:** shapefile entregue por área, `FALHAS.shp`, em WGS84 geográfico.

Estrutura (confirmada na área piloto, 58.765 feições):

| Campo | Conteúdo |
|---|---|
| `Field` | índice do polígono no KML de voo — **não é o talhão** |
| `Length` | comprimento bruto da falha, em metros |
| `LengthComp` | `Length − 0,30 m` — o usado no cálculo oficial |

Não traz chavesig, data, safra nem unidade. Todo esse contexto é injetado na
carga a partir de parâmetros e do spatial join.

Volume: cerca de 800 falhas por hectare. Extrapolando para a safra inteira,
dezenas de milhões de feições — a tabela precisa de índice espacial desde o
início e não é uma camada para carregar inteira num web map.

**Carga:** `src/carga/carga_linhas_falha.py`, idempotente por lote.

## 3. Inventário — `BASE_SAFRA`

Mantida pela rotina diária das 5h (`atualizar_base.py`, fora deste repositório).

Ver as ressalvas de archiving e de sistema de referência em
[modelo de dados](03-modelo-de-dados.md) e [arquitetura](02-arquitetura.md).

O campo `ESPAC` vem **codificado** (`"99"`), não em metros. O espaçamento real
usado no cálculo é parâmetro do script até existir o de-para dos códigos do
PIMS.

## 4. Survey123 — dois formulários

**Avaliação de Porte Cana - Pilotos ATVOS**
`service_a170152fc3934e68be6a4fcbc6808bd8`

Camada 0: pontos, com anexos (fotos ficam no **pai**, não no repeat).
Tabela 1: `talhoes_abrangidos`.

Campos úteis do pai: `dt_avaliacao`, `piloto` (lista codificada, oito pilotos),
`porte_adequado` (sim/não), `obs_campo` (só preenchido quando inadequado),
`previsao_retorno`, `qtd_talhoes`, `cod_fazenda`, `cod_setor`.

Não existe campo de altura ou classificação do porte — a avaliação é binária.

**Checklist e Registro de Missão — VANT**
`service_ffb97edbaa524ba3872425369a9b214b`

Camada 0: pontos. Tabela 1: `talhoes_voados`.

Campos úteis: `dt_saida`, `dt_retorno`, `piloto`, `vant_id` (embute a unidade:
`eBee X - USL`), `tipo_missao` (`falhas`, `daninhas`, `altimetria`,
`perimetro`), `resultado_missao`, `obs_gerais`.

**Não existe identificador do KML nem área analisada.** É por isso que o
vínculo com a entrega da Bem Agro precisa ser por regra.

Ambos são **hosted feature layers em PostgreSQL** (`sqlParserVersion:
PG_11.4.0`), fora do SQL Server corporativo — daí a necessidade das tabelas de
staging.

Muitos campos são rótulos de seção (`sec_*`, `nota_*`) que viraram coluna no
serviço. A extração deve listar campos explicitamente, nunca `outFields=*`.

**Carga:** `src/carga/sincronizar_surveys_vant.py`.

Problemas de qualidade observados: duração de voo de 1 minuto em missão
marcada como concluída; campos opcionais alternando entre `null` e string
vazia; `cod_setor` sempre 1 no porte enquanto varia na missão (suspeita de
valor padrão não editado).

## 5. Zeus — estações meteorológicas

**Cadastro das estações:** planilha exportada uma vez de `dl-bq-prd.bronze_zeus.pics`.
Muda raramente; recarregue com `carga_estacoes_zeus.py` só quando mudar.

**Monitoramento diário:** planilha que o Excel atualiza com a consulta de
[`sql/monitoramento_zeus.sql`](../sql/monitoramento_zeus.sql) (Power Query, ODBC ao BigQuery) e
salva em `Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\CLIMA`. É carregada todo dia
pelo `carga_monitoramento_zeus.py`, dentro do `ATUALIZAR_CLIMA.bat`.

**Origem definitiva:** a mesma consulta, rodando direto no BigQuery. Hoje o
servidor não tem login válido no BigQuery — ver [pendências](07-pendencias.md).

Tabelas relevantes do `silver_zeus`:

| Tabela | Conteúdo |
|---|---|
| `pics` | cadastro das estações — 170, todas com coordenada |
| `monitoramento_pic` | série diária |
| `pics_area` | vínculo estação → áreas (cadastro oficial da Zeus) |
| `areas` | cadastro de áreas — só `name`, `areaId`, `clientId` |
| `evapotranspiracao_et0pmf` | ETo Penman-Monteith |
| `prev_curto_prazo_3h/24h`, `prev_medio_prazo`, `prev_longo_prazo` | previsão |
| `alerta_enxurrada`, `alerta_incendio` | alertas |

Qualidade da série diária: 66.160 registros, 170 estações, sem duplicatas de
estação+dia, chuva sem nulos. Mediana de 392 dias por estação.

Ressalva: 3.137 leituras de pressão abaixo de 800 hPa (5% da base). Não afeta
o que o produto usa, mas indica sensor com problema.

**A Zeus entrega medição, não cálculo.** O `bronze_zeus.monitoramento_pic` é o
dado bruto do datalogger. O balanço hídrico que aparece no produto da Zeus não
desce para o BigQuery.

A `evapotranspiracao_et0pmf` tem 1.771.641 linhas mas **apenas 32.032 com
valor** (1,8%), cobrindo 85 estações e 211 dias. Não é falha intermitente: é
metade da rede calculando e a outra metade não.

A `areas` **não traz CAD nem tipo de solo** — só identificação.

**Carga:** `src/carga/carga_estacoes_zeus.py` (cadastro) e
`src/carga/carga_monitoramento_zeus.py` (diário).

## 6. Mancha de solos

**Origem:** `Mancha_Solos.shp`, na pasta do projeto na biblioteca de documentos
da Cartografia (`Projetos_Cart\DIAGNOSTICO_FALHAS`). SIRGAS 2000 / UTM 22S.

1.260 polígonos, cerca de 196 mil ha, cobrindo **só a região de USL-UEL**. Nem
ali a cobertura é total: 3.109 dos 3.400 talhões vigentes da UEL (91%) e 3.510
dos 4.649 da USL (75%) caem em alguma mancha. A fazenda 328307, da USL, fica
inteira de fora.

Campos: `Num_Manejo` (1 a 14), `Manejo`, `solo`, `Textura`, `Saturacao`,
`Amb_Atvos`, `Amb_Athena`.

**Carga:** `src/carga/carga_mancha_solos.py`, para a camada `SOLOS_ATVOS`.

## 7. Matriz de Plantio

**Origem:** planilha `matriz_plantio.xlsx`, aba `Matriz Plantio`, lida de
`D:\GEO\SOLOS`, fora do repositório. Validada no Encontro de Campo Grande, na
discussão da Cartilha Agronômica Atvos.

Cobre **apenas USL-UEL**: 14 unidades de manejo × 3 faixas de declividade × 17
períodos.

Pontos de atenção descobertos:

- **A classificação está na cor de fundo da célula**, não no texto. Lida com
  `pandas`, a planilha parece vazia.
- O vermelho aparece de duas formas — RGB `FFFF0000` e cor indexada 10 —,
  conforme a célula foi pintada pela paleta antiga ou pelo seletor de cor. Um
  leitor que conheça só uma delas perde células restritivas sem erro nenhum.
- O texto das células são asteriscos que representam **condições de manejo**
  (`**`, `***`, `****`), não parte da classe.
- Janeiro a maio são quinzenais; junho a dezembro, mensais.
- A coluna `Agrupamento solos` é um rótulo do grupo, não uma lista completa de
  códigos de solo, e não serve como de-para. O vínculo com o talhão vem da
  mancha de solos, pelo `Num_Manejo`.

**Carga:** `src/carga/carga_matriz_plantio.py`, substituição total.

## 8. Modelo de elevação — Copernicus GLO-30

**Origem:** bucket público da AWS, `https://copernicus-dem-30m.s3.amazonaws.com`.
GeoTIFF em tiles de 1 × 1 grau, 30 m, sem credencial.

Escolhido no lugar do SRTM: mesma resolução, erro vertical de 2 a 4 m contra 6 a
16 m e imageamento de 2011–2015 contra 2000. Ver
[ADR 0008](adr/0008-declividade-copernicus.md).

**É modelo de superfície**: inclui a vegetação. Cana alta no momento do
imageamento vira relevo.

Os tiles são baixados uma vez para `D:\GEO\DEM`.

**Uso:** `src/processamento/declividade_talhao.py`.

## 9. Fontes ainda não integradas

`pics_area` resolveria o vínculo talhão–estação pelo cadastro oficial da Zeus,
em vez do nosso cálculo de proximidade — depende de casar o `areaId` com o
chavesig.

As tabelas de previsão não servem ao relatório, que é retrospectivo, mas são o
insumo natural para o painel de demandas de VANT saber se vai dar para voar.
