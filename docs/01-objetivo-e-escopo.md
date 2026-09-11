# 01 — Objetivo e escopo

## O problema

A Atvos levanta falhas de plantio por VANT. O voo é processado pela Bem Agro,
que devolve um percentual de falhas por talhão. Esse percentual sobe para o
BigQuery e é publicado no PIMS.

Até aqui, o resultado era um número por talhão numa tabela. O que faltava:

- **Localização da falha dentro do talhão.** Um talhão com 12% de falhas pode
  ter uma reboleira concentrada — encharcamento, ataque de praga em foco — ou
  falha difusa por toda a área — muda, regulagem, profundidade. O
  encaminhamento é completamente diferente, e o percentual sozinho não
  distingue os dois casos.
- **Contexto climático comparável.** Saber que choveu 96 mm não diz nada. Saber
  que choveu 96 mm enquanto o resto da unidade recebeu 147 mm é argumento.
- **Rastreabilidade do processo.** Quando a área foi aprovada no porte, quando
  foi voada, quantos dias até o resultado sair. Isso mede a operação de VANT,
  não a lavoura.

## O que o produto entrega

Um relatório de três páginas, em HTML e PDF, por fazenda:

**Página 1 — Identificação e resultado.** Cadastro da área, dados do voo,
unidade de manejo e declividade, quatro indicadores principais, a época de
plantio segundo a Matriz de Plantio — com o ano inteiro desenhado e o plantio
marcado — e a linha do tempo com plantio, porte, voo e publicação no PIMS.

**Página 2 — Distribuição das falhas.** As falhas como vieram da Bem Agro,
linha a linha, o mapa de calor da densidade com escala fixa, a tabela por
talhão e a proporção da área em cada faixa de densidade.

**Página 3 — Diagnóstico climático.** Chuva dos 30 dias antes do plantio, que
diz em que umidade o solo estava, e chuva acumulada, dias com chuva e maior
veranico da janela 0–30 DAP. Cada um comparado à média da unidade na mesma
safra, mais o gráfico de chuva diária cobrindo as duas janelas.

## Público

O comitê agrícola e a gerência das unidades. O relatório é feito para ser lido
por quem decide replantio, não por quem opera GIS.

## Critério de geração

O relatório **não** é gerado para todas as áreas. Só para fazendas cuja média
ponderada de falhas supere a meta corporativa (4,2%). Gerar milhares de PDFs
que ninguém abre desvaloriza o material.

## Fora de escopo (por ora)

- **Balanço hídrico e ARM/CAD.** Bloqueado por falta do CAD do solo e por
  cobertura insuficiente da ETo. Ver [pendências](07-pendencias.md).
- **Rastro de plantio.** Depende de telemetria de plantadora, que a Atvos não
  possui.
- **Paralelismo do plantio.** Viável a partir da `LINHAS_RESTITUIDAS`, mas fora
  da primeira entrega.
- **Correlação estatística entre falha e fatores.** A v1 é descritiva: apresenta
  os fatores lado a lado e deixa a leitura para quem interpreta. Correlação
  exige série maior e validação agronômica.
- **Painel web.** O relatório é o artefato de comitê. Um painel no Experience
  Builder sobre a mesma view é evolução natural, não requisito.

## Princípio que orienta as decisões

**O número oficial é o do PIMS.** Tudo que este produto calcula — metros por
hectare, tamanho médio da falha, densidade do mapa de calor — é detalhamento
espacial, nunca uma segunda versão do percentual. Dois números divergentes
circulando na empresa destruiriam a credibilidade do relatório.
