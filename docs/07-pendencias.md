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

### Bloco de época montado com o primeiro talhão

O gerador monta o bloco "Época de plantio" e a unidade de manejo do cabeçalho
com o **primeiro talhão** da fazenda (`registros[0]`).

- Se esse talhão não tem classe, o bloco some do relatório, mesmo com outros
  talhões classificados. Acontece em 7 fazendas: na 310264, os talhões 1 e 2 não
  têm classe e os 3, 4, 6 e 7 têm.
- 20 das 33 fazendas classificadas têm talhões em classes diferentes, e o
  relatório mostra uma só.

Proposta: resumir a época por fazenda no bloco (área em cada classe) e levar a
classe de cada talhão para a tabela da página 2.

### Ressalva de fronteira aplicada longe da fronteira

O `classificar_epoca_plantio` testa a faixa de declividade vizinha em todo
talhão, sem consultar a `DECLIV_CONFIANCA`. O
[ADR 0009](adr/0009-ressalva-so-quando-muda-a-classe.md) pretendia refinar só os
talhões perto da fronteira.

Das 984 ressalvas com o motivo "declividade próxima da fronteira", **623 (63%)
são de talhões cuja mediana está longe dela**. Na área piloto, o talhão 9, com
1,19% de declividade, sai com esse motivo.

Proposta: só testar a faixa vizinha quando `DECLIV_CONFIANCA = 'Ressalva'`. As
ressalvas de fronteira cairiam de 984 para 361.

### Data de plantio da classificação só do inventário

A classificação lê a `DATA_PLANTIO` da `BASE_SAFRA` vigente. Na view, 199
talhões têm unidade de manejo, faixa de declividade e data de plantio e mesmo
assim estão sem classe. A fazenda 310438, que não está no inventário vigente, é
um desses casos: 19 talhões com unidade de manejo, nenhum classificado.

Decisão pendente: usar a data do PIMS quando o inventário não tiver, ou manter o
inventário como única fonte — coerente com o
[ADR 0006](adr/0006-inventario-como-alvo-do-join.md) — e dizer no relatório por
que a época não aparece.

### Mancha de solos incompleta em USL-UEL

A `SOLOS_ATVOS` cobre 3.109 dos 3.400 talhões vigentes da UEL (91%) e 3.510 dos
4.649 da USL (75%). A fazenda 328307 fica inteira de fora. Sem mancha não há
unidade de manejo, e o relatório sai sem o bloco de época.

Vale confirmar com quem mantém a mancha se a lacuna é de levantamento ou de
recorte do shapefile.

### Constante de 60% repetida

O limite de talhão dividido entre unidades existe como `PCT_MINIMO_ALERTA` no
`vincular_talhao_manejo` e como número solto no `classificar_epoca_plantio`.
Mudar um sem o outro desalinha o alerta da ressalva.

### Caminho do shapefile de solos

O `carga_mancha_solos` aponta para a pasta do OneDrive de um usuário. Em outra
máquina o caminho precisa ser ajustado antes de rodar.

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

### Monitoramento Zeus ainda depende do Excel

A chuva entra por uma planilha que alguém atualiza no Excel. A consulta já está
no repositório ([`sql/monitoramento_zeus.sql`](../sql/monitoramento_zeus.sql)) e a
carga já está agendada.

**Dá para sair do Excel** (confirmado em 11/09/2026): a conexão do ArcGIS que fica
no OneDrive do João — a do `atualizar_base.py` e do percentual oficial — lê o
`bronze_zeus`, com o monitoramento até o dia corrente. Falta trocar a
`ler_origem` do `carga_monitoramento_zeus.py` para rodar a consulta por ela. A
conexão só funciona na conta do João.

As outras conexões do servidor não servem: a ODBC de sistema `Google BigQuery`
está sem configuração, a ODBC `dl-bq-prd` da conta do João tem o token recusado
(`invalid_grant`), e a cópia da conexão do ArcGIS em `D:\GEO\TALHOES` trava
esperando login.

Enquanto o cadastro das estações não for recarregado, o **status** de cada estação
(OK, intermitente, falha) fica como estava na exportação — e é ele que decide
quais estações entram no vínculo.

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
quantas áreas críticas viraram replantio de fato. A época de plantio, um desses
fatores, entrou na página 1 na versão 0.2.

**Paralelismo do plantio.** Viável a partir da `LINHAS_RESTITUIDAS`. Cobre
parte do que o rastro de plantio daria, e é o candidato natural à próxima
versão.

**Painel no Experience Builder.** A view já é publicável como camada. Falta
registrá-la com o geodatabase pelo Catalog.
