# 07 — Pendências

## Bloqueios externos

### CAD do solo

**Impede:** balanço hídrico, ARM/CAD, déficit hídrico acumulado. Toda a
página 3 no formato que a gerência pediu.

O CAD não está em lugar nenhum dos sistemas já mapeados. A tabela `areas` do
`silver_zeus` traz só identificação. O PIMS traz tipo de solo, mas não os
parâmetros físico-hídricos.

Caminhos, em ordem de preferência:

1. **A própria Zeus** — ela calcula o balanço, então tem o CAD cadastrado.
   Garante que o número do relatório é o mesmo do produto dela.
2. **PIMS** — verificar com quem administra o cadastro agrícola se existe campo
   de CAD ou água disponível por classe de solo.
3. **Área de solos / planejamento agrícola** — levantamento pedológico costuma
   virar tabela de classes com atributos.
4. **Derivar do tipo de solo** com valores de referência. Precisa de aval
   agronômico; não é número que a Geotecnologia deva arbitrar.

Observação: o CAD é **uma tabela pequena**, um valor por classe de solo, não
por talhão. O relatório da Bem Agro já exibe `CAD: 31,3 mm` — vale descobrir
de onde quem monta aquele relatório tira esse número.

### ETo com cobertura insuficiente

`dl-bq-prd.silver_zeus.evapotranspiracao_et0pmf` tem 1.771.641 linhas, das
quais **32.032 com valor (1,8%)**, cobrindo 85 estações e 211 dias, de 28/01
até hoje.

O padrão indica metade da rede calculando continuamente e a outra metade não —
não é falha intermitente nem carga interrompida.

Perguntas para a Zeus: por que só parte das estações calcula ETo, e qual a
semântica do campo `period` (a contagem sugere mais de um registro por dia).

### Balanço hídrico da Zeus

O produto da Zeus calcula e exibe balanço hídrico com CC, AFD, PMP e fenologia,
mas esse resultado **não desce para o BigQuery**. Pedir que seja exposto é mais
barato e mais seguro que reimplementar — evita dois cálculos divergentes
circulando.

---

## Dívidas técnicas

### Detecção de fazenda completa

O critério de seleção calcula a média sobre os talhões que **já têm** resultado.
Uma fazenda meio processada, em que os piores vieram primeiro, entra na lista
indevidamente, e o número muda quando o resto chegar.

Proposta: cobertura por área com tolerância — a fazenda entra quando 90% da sua
área tem resultado, e o percentual de cobertura aparece no relatório.

Consulta para dimensionar antes de decidir o corte:

```sql
SELECT COUNT(*) AS fazendas,
       SUM(CASE WHEN pct_area >= 90 THEN 1 ELSE 0 END) AS completas_90,
       SUM(CASE WHEN pct_area >= 99 THEN 1 ELSE 0 END) AS completas_99
FROM (
  SELECT COD_FAZENDA,
         100.0 * SUM(CASE WHEN FALHA_PCT IS NOT NULL THEN AREA_HA ELSE 0 END)
               / NULLIF(SUM(AREA_HA), 0) AS pct_area
  FROM ATVOSPUBLICADOR.VW_RELATORIO_FALHAS
  GROUP BY COD_FAZENDA
) t;
```

### Leitura climática por quinzena

A frase de diagnóstico da página 3 compara só o acumulado de 30 dias. Na área
piloto isso esconde um padrão relevante: os primeiros 15 dias tiveram chuva
**acima** da média da unidade (87,2 contra 81,4 mm), e do dia 16 ao 30 caíram
9 mm contra 65 da unidade.

Ou seja, não foi seca na brotação — foi chuva boa no plantio e parada quase
completa na quinzena seguinte. A regra atual não enxerga isso.

Proposta: comparar as duas quinzenas separadamente, distinguindo seca desde o
plantio, seca só na segunda quinzena e chuva normal.

### Confiabilidade por dias sem dado

A `CLIMA_CONFIABILIDADE` hoje considera só a distância da estação. Uma janela
com 23 de 31 dias sem registro produz acumulados que não são comparáveis, mas
aparece como "Boa" se a estação estiver perto.

### Automação de `LOTE` e `DATA_VOO`

Hoje são preenchidos à mão no `carga_linhas_falha`. O `LOTE` pode sair do nome
da pasta ou do arquivo da entrega. A `DATA_VOO` pode ser resolvida pela regra
do voo (seção 4.1 das regras de negócio), com relatório de pendências quando a
missão não for encontrada.

### Quebras do mapa de calor desatualizadas

O `mapa_calor_falhas.py` ainda usa 300/600/900. O gerador já aplica
280/500/1000 no desenho. Alinhar os dois.

### Migração das planilhas Zeus para o BigQuery

A carga das estações lê planilhas exportadas. Quando a consulta virar tabela no
BQ, só muda a função de leitura — o esquema e a lógica permanecem.

### Registro de missão com 8% de cobertura

Só 364 dos 4.611 talhões têm voo vinculado, e 200 têm porte. Não é problema
técnico: é preenchimento da operação. Sem isso o relatório perde o DAP, a
defasagem porte–voo e o nome do piloto.

É conversa de gestão com a Operação VANT, e agora está quantificada.

### `uniquerowid` instável nos surveys

Foi observado um registro pai cujo `uniquerowid` mudou após edição, órfãos as
linhas do repeat. Vale conferir no XLSForm publicado se a fórmula do campo está
envolvida em `once()`.

### Archiving da `BASE_SAFRA`

3,4 milhões de linhas para 25.710 feições vigentes, crescendo cerca de 25 mil
por dia. Se o archiving não foi ligado de propósito, é problema de
armazenamento em formação. Se a rotina das 5h reescrevesse só o que mudou, o
crescimento praticamente pararia.

Fora do escopo deste produto, mas descoberto por ele.

---

## Melhorias de produto

**Ortomosaico na página 1.** Espaço já reservado. A decisão pendente é o
formato: o TIF inteiro é pesado demais; um recorte da área em baixa resolução
cumpre a função.

**Página 4 — fatores agronômicos e encaminhamento.** Existia no modelo original
e foi cortada: os fatores disponíveis hoje são poucos, e o encaminhamento
depende de decisão de comitê que ninguém preenche ainda. Quando existirem
campos de decisão, responsável e prazo, a página volta — e permite medir
quantas áreas críticas viraram replantio de fato.

**Paralelismo do plantio.** Viável a partir da `LINHAS_RESTITUIDAS`. Cobre
parte do que o rastro de plantio daria, e é o candidato natural à próxima
versão.

**Painel no Experience Builder.** A view já é publicável como camada. Falta
registrá-la com o geodatabase pelo Catalog.
