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

Indicadores da janela 0–30 DAP por talhão. 4.604 linhas.

| Campo | Observação |
|---|---|
| `CHAVESIG`, `UNIDADE`, `SAFRA`, `DT_PLANTIO` | |
| `PIC_ID`, `ESTACAO_NOME`, `DISTANCIA_KM` | |
| `CONFIABILIDADE` | `Boa` até 15 km, `Ressalva` acima |
| `CHUVA_0_15`, `CHUVA_0_30` | mm acumulados |
| `DIAS_COM_CHUVA` | dias com 5 mm ou mais |
| `MAIOR_VERANICO` | maior sequência de dias abaixo de 5 mm |
| `TMAX_MEDIA`, `DIAS_TMAX_ALTA` | |
| `DIAS_SEM_DADO` | dias da janela sem registro na estação |
| `CHUVA_0_15_UNID`, `CHUVA_0_30_UNID`, `DIAS_CHUVA_UNID`, `VERANICO_UNID` | média da unidade na mesma safra |

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

Base atual de campo — **pós-plantio**. Usada apenas na união de chaves do
vínculo talhão–estação. Não entra no relatório de falhas.

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

LEFT JOIN INDICADORES_CLIMA_TALHAO c         -- clima da janela
       ON c.CHAVESIG = s.Layer
```

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

Os 8% de voo vinculado não significam que só 364 áreas foram voadas — é a
medida do preenchimento do Registro de Missão pelos pilotos.
