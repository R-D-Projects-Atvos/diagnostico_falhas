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

O join valida a si mesmo: linhas que não caem em nenhum talhão são contadas na
tela e **não são gravadas**. Na área piloto foram 319 de 58.765 (0,5%, 384 m
de 59 mil) — borda de polígono, dentro do esperado. Se mais da metade da
entrega ficar sem talhão, nada é gravado: a área provavelmente não está no
inventário vigente.

### 2.2 Contra o inventário, não a base atual

As falhas são divulgadas sobre o **polígono pré-plantio**. Isso é regra da
Atvos, não escolha técnica, e tem duas consequências:

- Assim que sai o apontamento de plantio, o talhão vira safra seguinte na
  `TALHOES_DATABASE`. Cruzar com a base atual traria a geometria errada.
- Talhões plantados em faixas existem separados no inventário (talhão 1 e
  talhão 6001) e unificados no pós-plantio. O PIMS divulga **separado**, então
  o relatório também.

### 2.3 A entrega salva na pasta

Quem pede o relatório baixa as linhas da fazenda na Bem Agro e salva em
`ENTRADAS\LINHAS` — o `.zip`, a pasta descompactada ou os arquivos soltos. A
carga procura o shapefile de linhas com `Length` e `LengthComp` e descobre a
fazenda pelo join.

- **Fazenda de borda.** A que tiver menos de 1% das linhas da entrega entrou
  pela borda e fica de fora.
- **Troca por talhão.** As linhas novas substituem as dos talhões que a
  entrega traz; os outros talhões da fazenda ficam. Grava primeiro, apaga
  depois. Ver [ADR 0012](adr/0012-linhas-trocadas-por-talhao.md).
- **Voo.** `DATA_VOO` sai do Registro de Missão pela regra 4.1. O `LOTE` é a
  fazenda com mais linhas e o momento da carga.
- **Depois.** O mapa de calor da fazenda é refeito e a entrega vai para
  `ENTRADAS\LINHAS\CARREGADAS\<lote>_<conta>`.

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

O mapa é o da **fazenda inteira**, com todas as linhas dela que estão no banco,
e é refeito a cada entrega carregada.

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

### 6.6 Janela antes do plantio

A umidade do solo no dia do plantio depende do que choveu antes. Solo que vinha
seco há semanas não germina bem nem com chuva boa depois; solo já carregado
responde rápido.

Por isso há uma segunda janela, de −30 a −1 DAP. O dia do plantio não entra
nela: ele abre a janela de brotação. `CHUVA_PRE_15` e `CHUVA_PRE_30` somam os
últimos 15 e 30 dias, e `DIAS_SEM_DADO_PRE` conta os dias sem registro. A média
da unidade vem em `CHUVA_PRE_30_UNID`, como nos demais indicadores.

**Janela sem nenhum registro fica nula, não zero.** Falta de dado não é falta de
chuva — a mesma regra do veranico (6.2). Gravar 0,0 mm fazia o relatório afirmar
que não choveu antes do plantio e puxava a média da unidade para baixo. O talhão
fica fora da `CHUVA_PRE_30_UNID`, e o relatório diz que a estação não tem
registro do período.

O mesmo vale para `CHUVA_PRE_15` quando os últimos 15 dias não têm registro.
Com registro parcial, o acumulado é gravado e a nota de dias sem registro
aparece no relatório.

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

**Troca por talhão.** A `LINHAS_FALHA` acumula entregas de áreas diferentes;
carregar de novo um talhão substitui as linhas dele em vez de duplicar. A view
soma todas as linhas do talhão, sem olhar o lote — sem a troca, uma entrega
repetida dobraria o número de falhas sem ninguém perceber. Ver
[ADR 0012](adr/0012-linhas-trocadas-por-talhao.md).

**Archiving.** Nenhuma tabela reescrita diariamente deve ter archiving ligado.
A `BASE_SAFRA` tem, e acumulou 3,4 milhões de linhas para 25.710 feições.

---

## 9. Solo, declividade e época de plantio

Escopo: **só USL-UEL**, a região coberta pela mancha de solos e pela Matriz de
Plantio.

### 9.1 A unidade de manejo vem da mancha de solos

O talhão recebe a unidade de manejo (`Num_Manejo`, 1 a 14) da mancha de solos
publicada em `SOLOS_ATVOS`. O `Num_Manejo` é a chave da Matriz de Plantio: o
texto do agrupamento de solos bate exatamente entre as duas fontes, então a
junção é direta, sem de-para.

A mancha fica no geodatabase, e não num shapefile, para que o vínculo seja
recalculável. Enquanto ela vivia na pasta de alguém, o vínculo era uma foto do
dia em que alguém rodou.

### 9.2 Unidade predominante em área

Um talhão pode cair sobre mais de uma mancha. A regra é a unidade que ocupa a
**maior área** dentro dele. O percentual dessa unidade é gravado em `PCT_AREA`,
para que se saiba quando o vínculo é limpo (100%) e quando o talhão está
dividido entre solos.

A interseção roda em UTM 22S. No dataset, em coordenadas geográficas, a área
sairia em graus quadrados e não serviria para comparar manchas.

Entram inventário e database, para que o vínculo sirva também a outras
análises. Dos 7.050 talhões vinculados, 3.554 caem sobre mais de uma mancha, e
em 738 a predominante cobre menos de 60% da área.

### 9.3 Declividade: mediana sobre o Copernicus

A declividade do talhão é a **mediana** dos pixels de declividade percentual,
calculada sobre o Copernicus GLO-30 suavizado por média 3 × 3. A mediana ignora
os pixels espúrios que a vegetação gera num modelo de superfície. Ver
[ADR 0008](adr/0008-declividade-copernicus.md).

A faixa é gravada no texto exato da matriz:

| Mediana | Faixa |
|---|---|
| abaixo de 2,5% | `< 2,5%` |
| de 2,5% até abaixo de 5% | `2,5 a 5%` |
| 5% ou mais | `> 5%` |

Quando a mediana está a até 0,5 ponto de 2,5% ou de 5%, `DECLIV_CONFIANCA` é
`Ressalva`. São 36% dos talhões.

### 9.4 A Matriz de Plantio

Para cada unidade de manejo e faixa de declividade, a matriz diz se cada período
do ano é `Favoravel`, `Aceitavel`, `Restritivo` ou `Favoravel com irrigacao`.
Janeiro a maio são divididos em quinzenas; junho a dezembro valem o mês inteiro.
A primeira quinzena vai do dia 1 ao 15.

Na planilha, a classe está na **cor de fundo** da célula. O texto são asteriscos
que representam **condições de manejo**:

| Marcador | Condição |
|---|---|
| `**` | exige cobertura vegetal bem formada |
| `***` | exige cobertura bem formada e dessecada com antecedência |
| `****` | evitar solo argiloso em período de frio intenso |

"Aceitável `**`" não quer dizer que a época foi adequada: quer dizer que seria,
**se** a cobertura estivesse bem formada. Por isso a condição acompanha a classe
na tabela e no relatório.

### 9.5 Classificação do talhão

```
período = período da matriz que contém a data de plantio (PIMS; inventário se o PIMS não tiver)
classe  = MATRIZ_PLANTIO[unidade de manejo, faixa de declividade, período]
```

A data de plantio é a do **PIMS** — a mesma do clima e do DAP. A do inventário
vigente só entra quando o PIMS não tem o talhão. Ver
[ADR 0011](adr/0011-data-de-plantio-do-pims.md). Talhão sem data nas duas
fontes, sem faixa de declividade ou sem regra na matriz não é classificado.

Distribuição dos 5.720 talhões classificados em 11/09/2026:

| Classe | Talhões | % |
|---|---|---|
| `Restritivo` | 1.933 | 33,8% |
| `Favoravel` | 1.471 | 25,7% |
| `Favoravel com irrigacao` | 1.282 | 22,4% |
| `Aceitavel` | 1.034 | 18,1% |

1.210 deles carregam condição: 522 exigem cobertura bem formada e dessecada, 508
cobertura bem formada, e 180 trazem o alerta de solo argiloso no frio.

### 9.6 Ressalva só quando a classe poderia ser outra

A classificação recebe `Ressalva` quando, **na faixa de declividade vizinha, a
recomendação para o mesmo período seria outra**. A classe alternativa vai em
`CLASSE_ALTERNATIVA`. Também recebe `Ressalva` quando a unidade predominante
cobre menos de 60% do talhão.

Herdar a ressalva da declividade marcaria um terço dos talhões, e ninguém lê um
alerta tão frequente. Ver [ADR 0009](adr/0009-ressalva-so-quando-muda-a-classe.md).

Em 11/09/2026 eram 4.226 classificações `Boa` e 1.494 `Ressalva` — 998 por
declividade e 496 por talhão dividido.

**Limitação conhecida:** a versão atual testa a faixa vizinha em todo talhão,
sem olhar se a mediana está perto da fronteira. Ver [pendências](07-pendencias.md).

### 9.7 O que é "fora da época indicada"

`EPOCA_FORA_DA_INDICADA` vale 1 só para `Restritivo`. `Favoravel com irrigacao`
não conta: é plantio de inverno, prática deliberada, que a matriz considera
adequada quando há irrigação ou salvamento. Somar os dois exageraria o problema.
Ver [ADR 0010](adr/0010-irrigacao-nao-e-fora-da-epoca.md).

### 9.8 No relatório

A época ganha bloco próprio na página 1, com a faixa do ano inteiro pintada
conforme a matriz e o período do plantio marcado. Como campo de texto no meio de
doze outros, ela passava despercebida — justamente o indicador que aponta causa
fora do clima.

**Limitação conhecida:** o bloco é montado com o primeiro talhão da fazenda. Ver
[pendências](07-pendencias.md).
