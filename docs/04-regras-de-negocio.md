# 04 — Regras de negócio

Todas as regras que o produto aplica, com o porquê de cada uma.

---

## 1. Percentual de falhas

### 1.1 O número oficial vem do PIMS

O relatório **nunca recalcula** o percentual. Ele exibe o `FALHA_LINHA` da
`STATUS_REPORT_VANT`, que veio do BigQuery e é o mesmo publicado no PIMS.

Os metros das linhas de falha servem para m/ha, tamanho médio e mapa de calor —
detalhamento espacial, nunca uma segunda versão do percentual.

### 1.2 A fórmula (usada só para validação)

```
% falhas = soma(LengthComp) / (área_ha × 10.000 / espaçamento_m)
```

Validada na área piloto contra o PIMS:

| Talhão | Calculado | PIMS |
|---|---|---|
| 6 | 23,57% | 23,8% |
| 5 | 16,23% | 16,1% |
| 7 | 11,18% | 11,3% |
| 4 | 9,19% | 9,4% |
| **total** | **12,52%** | **12,66%** |

A diferença residual de cerca de 1% se explica por duas coisas que somam: o
espaçamento real fica em torno de 1,515 m, não 1,50; e a área do PIMS é
ligeiramente menor que a do inventário em alguns talhões, provavelmente por
descontar áreas não consideradas no processamento.

### 1.3 `LengthComp`, não `Length`

O shapefile da Bem Agro traz dois campos de comprimento por falha, e
`LengthComp = Length − 0,30 m` em todas as feições — é a tolerância descontada
de cada falha.

**A escolha muda o resultado em 23%**: na área piloto, 77.208 m com `Length`
contra 59.579 m com `LengthComp`. A Bem Agro usa `LengthComp` no cálculo do
PIMS, então é ele que o produto usa.

### 1.4 Média da área é ponderada pela área

```
falha_área = Σ(falha_talhão × área_talhão) / Σ(área_talhão)
```

Média simples daria peso igual a um talhão de 7,33 ha e a um de 32,48 ha.

### 1.5 Semáforo

| Faixa | Situação |
|---|---|
| até 4,2% | Dentro da meta |
| 4,2% a 7,5% | Atenção |
| acima de 7,5% | Crítico |

A meta de 4,2% é corporativa. Os limites de atenção e crítico foram propostos
com base na referência de mercado e **ainda aguardam validação do agrícola**.

---

## 2. Atribuição espacial das falhas

### 2.1 O talhão vem por spatial join, não do arquivo

O campo `Field` do shapefile (`000`, `001`, `002`, `003`) é o índice sequencial
do polígono no KML de voo, **não** o código do talhão da Atvos. Confirmado na
área piloto: o arquivo tem `Field` de 000 a 003, enquanto os talhões reais são
4, 5, 6 e 7.

A atribuição é feita por posição, contra o inventário:

```python
arcpy.analysis.SpatialJoin(..., match_option="HAVE_THEIR_CENTER_IN")
```

**Por centro da feição, não interseção.** Uma falha que cruza a divisa entre
dois talhões seria contada duas vezes com interseção; pelo centro pertence a um
só, e a soma dos talhões continua igual ao total da área.

O join valida a si mesmo: linhas que não caem em nenhum talhão ficam com
`CHAVESIG` nulo e são reportadas. Na área piloto foram 319 de 58.765 (0,5%,
384 m de 59 mil) — borda de polígono, dentro do esperado.

### 2.2 Contra o inventário, não a base atual

As falhas são divulgadas sobre o **polígono pré-plantio**. Isso é regra da
Atvos, não escolha técnica, e tem duas consequências:

- Assim que sai o apontamento de plantio, o talhão vira safra seguinte na
  `TALHOES_DATABASE`. Cruzar com a base atual traria a geometria errada.
- Talhões plantados em faixas existem separados no inventário (talhão 1 e
  talhão 6001) e unificados no pós-plantio. O PIMS divulga **separado**, então
  o relatório também.

---

## 3. Mapa de calor

### 3.1 Cada falha vira um ponto, pesado pelo comprimento

O Kernel Density sobre **linhas** já usa o comprimento da geometria no cálculo.
Passar `COMP_OFI_M` como população ali contaria o comprimento duas vezes.

Por isso cada falha é convertida no seu ponto médio, com `COMP_OFI_M` como peso
explícito. Como a falha média tem 1,3 m e o raio de busca é 40 m, a diferença
geométrica é irrelevante e o resultado é exatamente **metros de falha
compensada por hectare** — a mesma métrica da tabela.

Parâmetros: célula de 2 m, raio de 40 m, unidade de área em hectares.

### 3.2 Escala fixa, ancorada no semáforo

As quebras não são relativas a cada área. Se cada relatório reclassificasse
pelo próprio mínimo e máximo, um talhão excelente pareceria vermelho e a
comparação entre áreas se perderia.

Com espaçamento de 1,5 m há 6.667 m lineares por hectare, então:

| Densidade | Equivale a | Significado |
|---|---|---|
| até 280 m/ha | 4,2% | dentro da meta |
| 280 a 500 | 7,5% | atenção |
| 500 a 1.000 | 15% | crítico |
| acima de 1.000 | — | muito crítico |

O mapa passa a falar a mesma língua da tabela.

### 3.3 "Onde está a falha"

A proporção da área em cada faixa é medida sobre o próprio raster, contando
pixels por classe e convertendo pelo tamanho da célula. É o que distingue
reboleira localizada de falha difusa.

---

## 4. Vínculo entre voo, porte e resultado

Não existe identificador do KML no Registro de Missão que ligue diretamente uma
entrega da Bem Agro a um voo. O vínculo é por regra.

### 4.1 Qual voo gerou o resultado

```sql
SELECT TOP 1 ... FROM STG_VOO_MISSAO m
WHERE m.CHAVESIG = s.Layer
  AND m.TIPO_MISSAO = 'Falhas'
  AND ISNULL(m.RESULTADO_MISSAO,'') <> 'Interrompido'
  AND (s.DATA_AMOSTRA IS NULL OR m.DT_SAIDA <= s.DATA_AMOSTRA)
ORDER BY m.DT_SAIDA DESC
```

Missão de tipo falhas, não interrompida, mais recente **antes** da publicação
no PIMS. Missão interrompida fica de fora — senão o DAP do cabeçalho sai
errado.

### 4.2 Qual porte autorizou aquele voo

```sql
SELECT TOP 1 ... FROM STG_PORTE_AVALIACAO a
WHERE a.CHAVESIG = s.Layer
  AND a.PORTE_ADEQUADO = 'sim'
  AND (v.DT_SAIDA IS NULL OR a.DT_AVALIACAO <= v.DT_SAIDA)
ORDER BY a.DT_AVALIACAO DESC
```

A última avaliação **aprovada anterior ao voo** — foi ela que o autorizou.

### 4.3 DAP é calculado, não lido

O campo `DPP` do PIMS conta os dias até **hoje**, não até o voo. Verificado:
talhões plantados em 03/03/2026 mostravam 176, que corresponde à data da
consulta.

```
DAP = DATEDIFF(day, DT_PLANTIO, DT_VOO)
```

---

## 5. Chavesig dos surveys

### 5.1 Reconstruído, nunca lido do formulário

O `chavesig` calculado pelo Survey123 é **campo de conferência**, não chave.
O pipeline reconstrói:

```
Chavesig = LPAD(cod_fazenda,6) + LPAD(cod_setor,4) + LPAD(cod_talhao,4)
```

**Por quê:** o `calculate` dentro do repeat é avaliado de forma intermitente.
Três versões publicadas (v3.0, v3.1, v3.2 do porte) não resolveram — em
avaliação com quatro talhões, apenas as últimas linhas gravavam corretamente.
Ver [ADR 0001](adr/0001-chavesig-reconstruido.md).

A v3.2 pelo menos falha de forma segura: grava nulo em vez de sufixo `0000`,
que passaria por chave válida e faria join silencioso no talhão errado.

### 5.2 Relacionamento pai-filho

Os surveys ligam pai e repeat por **`uniquerowid` no pai contra `parentrowid`
no filho**, não por `globalid`. Quem escrever a consulta esperando globalid
recebe zero linhas.

A comparação deve normalizar caixa: o GUID vem entre chaves e com caixa
variável.

**Alerta:** foi observado um caso em que o `uniquerowid` do registro pai mudou
após edição, órfãos as linhas do repeat. Enquanto não estiver esclarecido, o
`parentrowid` só deve ser usado dentro de uma mesma extração, nunca como chave
persistida.

### 5.3 Datas em UTC

Os serviços gravam em UTC sem horário de verão. A conversão é feita na
**extração**, não na exibição. Parâmetro `UTC_OFFSET_H`, padrão −3 (Brasília);
Mato Grosso do Sul é −4.

`created_date` **não serve para nada cronológico** — reflete a sincronização,
não o evento. Foi observado registro de voo de 08/07 sincronizado em 16/08.

---

## 6. Indicadores climáticos

### 6.1 Janela 0–30 DAP

A janela vai da data média de plantio até 30 dias depois. É nela que a maior
parte da falha se origina — brotação.

`CHUVA_0_15` cobre a primeira quinzena, mais crítica.

### 6.2 Veranico: dias abaixo de 5 mm

Um dia com 2 mm não molha o solo o suficiente para a brotação; contar como dia
chuvoso mascararia a estiagem. `MAIOR_VERANICO` é a maior sequência de dias
consecutivos abaixo desse limiar.

**Dia sem registro não conta como dia seco.** Falta de dado não é falta de
chuva — se a estação ficou fora do ar três dias, isso não pode virar veranico
de três dias. Esses dias interrompem a contagem e são somados em
`DIAS_SEM_DADO`, que aparece no relatório.

### 6.3 Sempre ao lado da média da unidade

Todo indicador vem acompanhado da média da unidade na mesma safra. Número
sozinho não diagnostica: 96 mm só significa alguma coisa ao lado dos 147 mm que
o resto da unidade recebeu.

`CHUVA_VS_UNIDADE_PCT` expressa isso como razão — mais comparável entre
unidades que o valor absoluto.

### 6.4 Vínculo talhão–estação

Regra principal: **estação mais próxima do centroide** do talhão, entre as de
status `OK`.

Exceção preferencial: se a fazenda tem estação própria cadastrada (nome no
padrão `UNIDADE_FAZENDA`), o vínculo é por **cadastro** — foi alguém da unidade
que decidiu qual estação representa aquela fazenda.

A distância é sempre gravada. Distribuição observada: mediana de 3,5 km, 90%
abaixo de 7,4 km, máximo de 49,6 km.

### 6.5 Confiabilidade por distância

Até 15 km o dado é exibido normalmente (98,1% dos talhões). Acima, com
ressalva. O corte **não é aplicado na carga**, só na exibição — o vínculo é
sempre gravado, e finalidades diferentes podem adotar raios diferentes sem
recalcular nada.

---

## 7. Seleção de quais relatórios gerar

Só fazendas cuja **média ponderada pela área** supere a meta:

```sql
SELECT COD_FAZENDA, ...
FROM VW_RELATORIO_FALHAS
WHERE FALHA_PCT IS NOT NULL AND AREA_HA > 0
GROUP BY COD_FAZENDA
HAVING SUM(FALHA_PCT * AREA_HA) / NULLIF(SUM(AREA_HA), 0) > 4.2
```

A média considera **todos os talhões da fazenda com resultado publicado**, não
só os que têm linhas de falha carregadas: o critério é sobre a fazenda inteira.

**Limitação conhecida:** não há detecção de fazenda parcialmente processada.
Se metade dos talhões ainda não tem resultado, a média é calculada sobre a
metade existente. Ver [pendências](07-pendencias.md).

---

## 8. Regras de proteção nas cargas

**Ler antes de apagar.** Toda carga por substituição total lê a origem inteira
e aborta se vier vazia. Sem isso, uma falha de conexão zeraria produção.

**Idempotência por lote.** A `LINHAS_FALHA` acumula entregas; rodar de novo a
mesma entrega substitui em vez de duplicar. Sem o `LOTE`, uma execução repetida
dobraria o número de falhas sem ninguém perceber.

**Archiving.** Nenhuma tabela reescrita diariamente deve ter archiving ligado.
A `BASE_SAFRA` tem, e acumulou 3,4 milhões de linhas para 25.710 feições.
