# ADR 0012 — Linhas de falha trocadas talhão a talhão

**Data:** setembro/2026
**Situação:** aceita

## Contexto

Até a versão 0.2, a carga das linhas era manual: o caminho do shapefile, a data
do voo e o lote ficavam escritos no script, e a idempotência era por `LOTE` —
rodar de novo a mesma entrega apagava o lote e regravava.

Com o relatório sob demanda, quem pede baixa as linhas da fazenda na Bem Agro e
salva em `ENTRADAS\LINHAS`. O arquivo não traz fazenda, talhão, data nem nome
de entrega: o download chega como `vectors-gaps.zip`. Pelo arquivo, não há como
saber se é a mesma entrega de antes ou um voo novo.

A view soma todas as linhas de cada talhão, sem olhar o lote. Duas entregas do
mesmo talhão dobrariam os metros de falha.

## Decisão

A entrega nova **substitui as linhas dos talhões que ela traz**, qualquer que
seja o lote anterior. Os outros talhões da fazenda ficam como estavam.

- Grava as novas e só depois apaga as antigas. Se a gravação falhar, as novas
  saem e as antigas ficam.
- Fazenda com menos de 1% das linhas da entrega entrou pela borda e fica de
  fora. Sem isso, algumas linhas de borda apagariam as linhas boas do talhão
  vizinho.
- Linha sem talhão não é gravada. Se mais da metade da entrega ficar sem
  talhão, nada é gravado: a área provavelmente não está no inventário vigente.
- `LOTE` passa a ser `<fazenda>_<AAAAMMDD_HHMMSS da carga>`, só informativo.
  `DATA_VOO` sai do Registro de Missão pela regra 4.1.
- O mapa de calor passa a ser o da fazenda inteira, com as linhas que estão no
  banco, e vai para o mosaic dataset `ATVOSPUBLICADOR.MAPA_CALOR_FALHAS`, no SQL
  Server, com um `.tif` por fazenda em `D:\GEO\FALHAS\mapa_calor_falhas`. Cada
  geração grava arquivo com nome novo, porque uma conta não sobrescreve arquivo
  criado por outra; na `rasters.gdb` antiga, as outras contas nem gravavam.

## Consequências

- Recarregar a mesma entrega não duplica, e o voo novo de um talhão troca o
  antigo sem intervenção.
- O banco guarda só a entrega mais recente de cada talhão. O arquivo carregado
  fica em `ENTRADAS\LINHAS\CARREGADAS`.
- Uma entrega que traga só parte de um talhão troca o talhão inteiro pelas
  linhas parciais. A tela de conferência mostra, por talhão, as linhas novas e
  as que estão no banco antes de gravar.
