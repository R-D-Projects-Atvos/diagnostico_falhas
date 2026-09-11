# 03 — Modelo de dados

Todas as tabelas ficam no SQL Server corporativo, esquema `ATVOSPUBLICADOR`.
As que têm geometria vivem no feature dataset `AGRICOLA_ATVOS`.

## A chave: `Chavesig`

Identificador do talhão, **14 dígitos**, com zeros à esquerda:

```
320127 0001 0004
└─ 6 ─┘└─4─┘└─4─┘
fazenda setor talhão
```

Os seis primeiros dígitos da fazenda já embutem o prefixo da unidade. Todas as
tabelas do produto se ligam por essa chave.

Cuidado importante: **o `Chavesig` deve ser tratado como texto**, nunca como
número. Fazendas cujo código começa com zero perderiam o dígito e deixariam de
casar. Foi por isso que a `Status_Report_VANT` precisou ser recriada — ver
[ADR 0002](adr/0002-layer-como-texto.md).

---

## Tabelas criadas por este produto

### `LINHAS_FALHA` (feature class, polyline, 4326)

Uma feição por falha individual levantada pelo VANT. Volume alto: cerca de
800 falhas por hectare — 58.765 feições para 74 ha na área piloto.

| Campo | Tipo | Origem | Observação |
|---|---|---|---|
| `CHAVESIG` | text(20) | spatial join | atribuído por posição, não vem do arquivo |
| `SAFRA_INV` | text(10) | BASE_SAFRA | safra do inventário usada no join |
| `CAMADA_INV` | text(30) | parâmetro | `BASE_SAFRA` ou `HISTORICO_SAFRA` |
| `TALHAO_KML` | text(5) | shapefile | campo `Field` original, referência |
| `COMP_M` | double | shapefile | `Length` — comprimento bruto |
| `COMP_OFI_M` | double | shapefile | `LengthComp` — o oficial |
| `CLASSE_TAM` | text(12) | derivado | faixas de tamanho da falha |
| `DATA_VOO` | date | parâmetro | do Registro de Missão |
| `LOTE` | text(60) | parâmetro | identificador da entrega, base da idempotência |
| `DATA_CARGA` | date | automático | |

Índices em `CHAVESIG` e `LOTE`.

**Por que `SAFRA_INV` e `CAMADA_INV` existem:** o relatório precisa ser
reproduzível. Sem registrar contra qual inventário o join foi feito,
reprocessar a mesma área depois da virada da safra daria outro resultado sem
ninguém perceber.

### `STATUS_REPORT_VANT` (tabela)

Cópia local do percentual oficial. Um registro por talhão, sem repetição —
4.611 na safra corrente.

| Campo | Tipo | Observação |
|---|---|---|
| `Layer` | **text(14)** | **é o Chavesig** — no BigQuery vem como STRING |
| `UNIDADE`, `DA_EMPRESA`, `ADMIN` | text | |
| `CD_UPNIVEL1/2/3` | text | fazenda, setor, talhão separados |
| `DE_UPNIVEL1` | text | nome da fazenda |
| `DT_PLANTIO` | date | |
| `Area_total` | double | **área do PIMS**, denominador do percentual oficial |
| `VARIEDADE`, `SIST_PLANTIO`, `FG_REPLANTIO` | | |
| `DPP` | long | **não usar** — calculado até hoje, não até o voo |
| `FALHA_LINHA` | double | **o percentual oficial** |
| `DATA_AMOSTRA` | date | publicação no PIMS, não a data do voo |
| `Status_Falha` | text | |
| `AreaDaninha`, `TalhaoDaninhaArea`, `Status_Daninhas` | | nulos: origem só tem falhas |
| `DATA_CARGA` | date | rastreabilidade da cópia |

### `ESTACOES_ZEUS` (feature class, point, 4326)

170 estações, uma por fazenda atendida. O campo `NOME` segue `UNIDADE_FAZENDA`
(ex.: `USL_320013`), de onde `UNIDADE` e `COD_FAZENDA` são extraídos. Tolera
sufixo — `URC_219053 II` resolve para URC/219053.

`STATUS` assume `OK`, `INTERMITTENT` ou `FAIL`; só as `OK` entram no vínculo.

### `MONITORAMENTO_ESTACAO` (tabela)

Série diária por estação. 66.160 registros de 21/07/2025 a 16/08/2026, sem
duplicatas de estação+dia.

Campos: `PIC_ID`, `DIA`, temperatura (min/média/max), umidade (min/média/max),
pressão (min/média/max), vento (instantâneo/médio), rajada, `CHUVA_TOTAL`,
`IRRADIACAO_MEDIA`, `DATA_CARGA`.

### `TALHAO_ESTACAO` (tabela)

Vínculo entre talhão e estação meteorológica. 27.507 linhas — união dos
`Chavesig` da `TALHOES_DATABASE` e da `BASE_SAFRA`.

| Campo | Observação |
|---|---|
| `CHAVESIG` | |
| `ORIGEM_TALHAO` | `DATABASE`, `INVENTARIO` ou `AMBAS` |
| `PIC_ID`, `ESTACAO_NOME`, `ESTACAO_UNIDADE` | |
| `DISTANCIA_KM` | sempre gravada, inclusive no vínculo por cadastro |
| `ORIGEM_VINCULO` | `CADASTRO` (23,8%) ou `PROXIMIDADE` (76,2%) |
| `DATA_CALCULO` | |

**Não habilitar archiving nesta tabela** — é reescrita diariamente.

### `INDICADORES_CLIMA_TALHAO` (tabela)

Indicadores de duas janelas por talhão: **antes** do plantio (−30 a −1 DAP) e
**depois** (0 a 30 DAP). 4.604 linhas.

| Campo | Observação |
|---|---|
| `CHAVESIG`, `UNIDADE`, `SAFRA`, `DT_PLANTIO` | |
| `PIC_ID`, `ESTACAO_NOME`, `DISTANCIA_KM` | |
| `CONFIABILIDADE` | `Boa` até 15 km, `Ressalva` acima |
| `CHUVA_0_15`, `CHUVA_0_30` | mm acumulados |
| `DIAS_COM_CHUVA` | dias com 5 mm ou mais |
| `MAIOR_VERANICO` | maior sequência de dias abaixo de 5 mm |
| `TMAX_MEDIA`, `DIAS_TMAX_ALTA` | |
| `DIAS_SEM_DADO` | dias da janela 0–30 DAP sem registro na estação |
| `CHUVA_PRE_15`, `CHUVA_PRE_30` | mm nos 15 e nos 30 dias antes do plantio; o dia do plantio não entra |
| `DIAS_SEM_DADO_PRE` | dias da janela anterior sem registro na estação |
| `CHUVA_PRE_30_UNID`, `CHUVA_0_15_UNID`, `CHUVA_0_30_UNID`, `DIAS_CHUVA_UNID`, `VERANICO_UNID` | média da unidade na mesma safra |

### `STG_PORTE_AVALIACAO` e `STG_VOO_MISSAO` (tabelas)

Staging dos dois surveys, já achatado: **uma linha por talhão**, não por
avaliação. O relatório junta por `CHAVESIG` sem precisar entender repeat nem
`parentrowid`.

Ambas trazem `CHAVESIG` **reconstruído** dos códigos, datas convertidas para
hora local e domínios traduzidos para texto legível.

`STG_VOO_MISSAO` tem `DURACAO_H` recalculado de `DT_SAIDA` e `DT_RETORNO` — o
campo `horas_voo` do formulário vem como string com float sujo.

### `LOG_CHAVESIG_SURVEYS` (tabela)

Registro de cada correção de `chavesig` gravada de volta no Portal: data,
survey, objectid, valor anterior, valor novo e resultado. Existe porque a
sincronização escreve em produção a cada execução.

### `SOLOS_ATVOS` (feature class, polygon)

Mancha de solos da Atvos, publicada a partir do `Mancha_Solos.shp`. 1.260
polígonos, cerca de 196 mil ha, **só a região de USL-UEL**.

| Campo | Observação |
|---|---|
| `Num_Manejo` | unidade de manejo, 1 a 14 — **a chave da Matriz de Plantio** |
| `Manejo` | agrupamento de solos; o texto bate exatamente com o da matriz |
| `solo`, `Textura`, `Saturacao`, `Amb_Atvos`, `Amb_Athena` | atributos do shapefile |
| `DATA_CARGA` | |

Os nomes de campo ficam **como vêm do shapefile**, em caixa mista. Renomear
para maiúscula apaga o atributo: o geodatabase não diferencia caixa, então o
campo "novo" é o mesmo campo, e o `DeleteField` seguinte remove o único que
existe.

Índice em `Num_Manejo`. **Não habilitar archiving.**

### `TALHAO_MANEJO` (tabela)

Unidade de manejo e declividade de cada talhão. 7.050 linhas, uma por chavesig,
da união de inventário e database.

| Campo | Gravado por | Observação |
|---|---|---|
| `CHAVESIG` | vínculo | |
| `ORIGEM_TALHAO` | vínculo | `INVENTARIO`, `DATABASE` ou `AMBAS` |
| `NUM_MANEJO`, `MANEJO`, `SOLO`, `TEXTURA`, `AMB_ATVOS` | vínculo | da mancha **predominante em área** |
| `PCT_AREA` | vínculo | quanto do talhão a mancha predominante cobre |
| `QTD_MANCHAS` | vínculo | em quantas manchas o talhão cai |
| `DECLIV_MEDIANA`, `DECLIV_MEDIA`, `DECLIV_DESVIO` | declividade | em %, sobre o Copernicus GLO-30 |
| `FAIXA_DECLIV` | declividade | no texto exato da matriz: `< 2,5%`, `2,5 a 5%`, `> 5%` |
| `DECLIV_CONFIANCA` | declividade | `Ressalva` se a mediana está a até 0,5 ponto de uma fronteira |
| `DECLIV_FONTE` | declividade | `Copernicus GLO-30` |
| `DATA_CALCULO` | vínculo | |

Dois scripts escrevem na mesma tabela. O `vincular_talhao_manejo` a regrava
inteira; o `declividade_talhao` completa os campos de declividade. **A ordem
importa**: rodar o vínculo depois da declividade apaga a declividade.

### `MATRIZ_PLANTIO` (tabela)

A Matriz de Plantio em formato longo: uma linha por unidade de manejo × faixa
de declividade × período. 714 linhas (14 × 3 × 17).

| Campo | Observação |
|---|---|
| `POLO`, `USINA` | `Sul`, `USL-UEL` |
| `NUM_MANEJO`, `AGRUP_SOLOS` | |
| `FAIXA_DECLIV` | `< 2,5%`, `2,5 a 5%`, `> 5%` |
| `MES_NUM`, `MES`, `QUINZENA` | quinzena só de janeiro a maio |
| `PERIODO` | `Jan 1Q` … `Mai 2Q`, `Jun` … `Dez` — o texto usado no join |
| `CLASSE_EPOCA` | `Favoravel`, `Aceitavel`, `Restritivo`, `Favoravel com irrigacao` |
| `MARCADOR`, `CONDICAO` | os asteriscos da célula e a condição de manejo que eles representam |
| `DATA_CARGA` | |

Índice em `NUM_MANEJO` + `FAIXA_DECLIV`.

### `EPOCA_PLANTIO_TALHAO` (tabela)

Classe da época de plantio de cada talhão. 5.520 linhas.

| Campo | Observação |
|---|---|
| `CHAVESIG`, `SAFRA` | |
| `DT_PLANTIO` | da `BASE_SAFRA` — **não** do PIMS |
| `PERIODO_PLANTIO` | a data traduzida para o período da matriz |
| `NUM_MANEJO`, `FAIXA_DECLIV`, `DECLIV_MEDIANA`, `PCT_AREA_MANEJO` | o que foi usado na consulta |
| `CLASSE_EPOCA`, `CONDICAO` | da matriz |
| `EPOCA_CONFIANCA` | `Boa` ou `Ressalva` |
| `CLASSE_ALTERNATIVA` | a classe na faixa de declividade vizinha, quando difere |
| `MOTIVO_RESSALVA` | declividade na fronteira ou talhão dividido entre unidades |
| `DATA_CALCULO` | |

---

## Tabelas consumidas, mantidas por outros processos

### `BASE_SAFRA` (feature class, polygon)

Inventário — o **mapa pré-plantio** da safra vigente. É a geometria correta
para falhas, porque a divulgação é feita sobre o polígono pré-plantio.

**Tem archiving ligado.** Cerca de 3,4 milhões de linhas para 25.710 feições
vigentes. O ArcGIS filtra sozinho; **consulta SQL direta precisa de**
`GDB_TO_DATE = '9999-12-31 23:59:59'`. Ver [ADR 0003](adr/0003-archiving-base-safra.md).

Campos usados: `Chavesig`, `Safra`, `BLOCO`, `AMBIENTE`, `ESPAC`,
`Area_total`, `DATA_PLANTIO`, `EmpDesc`, `Shape`.

### `TALHOES_DATABASE` (feature class, polygon)

Base atual de campo — **pós-plantio**. Usada na união de chaves dos vínculos
talhão–estação e talhão–unidade de manejo, e nas zonas da declividade.

A geometria dela não entra no relatório de falhas, mas um talhão que só existe
nela ainda recebe unidade de manejo e declividade na `TALHAO_MANEJO`.

---

## A view: `VW_RELATORIO_FALHAS`

Uma linha por talhão com resultado publicado. 4.611 linhas, uma por chavesig.

Estrutura dos joins:

```sql
FROM STATUS_REPORT_VANT s                    -- base: só talhões com resultado

LEFT JOIN BASE_SAFRA b                       -- cadastro e geometria
       ON b.Chavesig = s.Layer
      AND b.GDB_TO_DATE = '9999-12-31 23:59:59'   -- filtro de archiving

LEFT JOIN ( ... GROUP BY CHAVESIG ) f        -- agregação das linhas de falha
       ON f.CHAVESIG = s.Layer

OUTER APPLY ( SELECT TOP 1 ... ) v           -- voo que originou o resultado
OUTER APPLY ( SELECT TOP 1 ... ) p           -- porte que autorizou o voo

LEFT JOIN INDICADORES_CLIMA_TALHAO c         -- clima das janelas pré e pós
       ON c.CHAVESIG = s.Layer

LEFT JOIN TALHAO_MANEJO m                    -- unidade de manejo e declividade
       ON m.CHAVESIG = s.Layer

LEFT JOIN EPOCA_PLANTIO_TALHAO e             -- classe da época de plantio
       ON e.CHAVESIG = s.Layer
```

`EPOCA_FORA_DA_INDICADA` é o atalho para o semáforo: vale 1 só para
`Restritivo`. `Favoravel com irrigacao` vale 0 — ver
[ADR 0010](adr/0010-irrigacao-nao-e-fora-da-epoca.md).

A geometria vem da `BASE_SAFRA`, então a view é publicável como camada — basta
registrá-la com o geodatabase pelo Catalog.

### Cobertura atual

| | |
|---|---|
| Talhões na view | 4.611 |
| Com percentual do PIMS | 1.998 (43%) |
| Com linhas de falha | 4 (só a área piloto) |
| Com voo vinculado | 364 (8%) |
| Com porte vinculado | 200 (4%) |
| Com indicadores climáticos | 3.724 (81%) |
| Sem geometria no inventário | 168 |
| Com unidade de manejo¹ | 593 (13%) |
| Com classe de época de plantio¹ | 394 (9%) |
| Com percentual e classe de época¹ | 200 |
| Plantio fora da época indicada¹ | 95 |

¹ Consulta de 11/09/2026. Só existe onde há mancha de solos, isto é, em
USL-UEL.

Os 8% de voo vinculado não significam que só 364 áreas foram voadas — é a
medida do preenchimento do Registro de Missão pelos pilotos.
