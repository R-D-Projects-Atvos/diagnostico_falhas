# ADR 0011 — Data de plantio do PIMS, com o inventário de reserva

**Data:** setembro/2026
**Situação:** aceita

## Contexto

O relatório já mostrava a data de plantio do PIMS
(`STATUS_REPORT_VANT.DT_PLANTIO`) e calculava o DAP com ela. Os indicadores de
clima e a época de plantio usavam a `DATA_PLANTIO` da `BASE_SAFRA`.

As duas fontes divergem justamente nos talhões para os quais se pede relatório.
Em 11/09/2026, dos 4.695 talhões com resultado publicado no PIMS:

- 176 não estavam no inventário vigente — a fazenda 310438, por exemplo;
- 699 estavam no inventário sem data de plantio;
- 102 tinham outra data, quase sempre a do plantio anterior, em área de reforma
  (PIMS em 2026, inventário em 2020).

A `BASE_SAFRA` só tem plantios até 30/06/2026: o talhão plantado em reforma
passa para a safra seguinte na base e o inventário espera a virada. Plantios de
julho em diante ficavam sem clima e sem época, e em talhão de reforma a janela
de chuva era a de um plantio de anos antes.

## Decisão

Decisão do usuário em 11/09/2026: **vale a data do PIMS**. A do inventário só
entra quando o PIMS não tem o talhão.

A escolha fica num lugar só, `src/processamento/data_plantio.py`, usado pelo
clima e pela época. As duas tabelas gravam a origem em `DT_PLANTIO_FONTE`
(`PIMS` ou `INVENTARIO`).

Unidade e safra, que agrupam a média da unidade, continuam vindo do inventário.
O talhão que só o PIMS tem fica com a unidade do PIMS e com a safra que o
inventário tem para essa unidade.

## Consequências

- Clima, época, DAP e a data exibida no relatório passam a falar do mesmo
  plantio.
- Na primeira execução, o clima foi de 4.604 para 5.529 talhões (dos que têm
  resultado no PIMS, de 3.724 para 4.649) e a época de 5.520 para 5.720 (de 394
  para 611). Nenhum talhão que já tinha época mudou de classe.
- A média da unidade muda porque entram mais talhões. Na área piloto, a chuva
  de 0 a 30 DAP da unidade foi de 146,8 para 144,7 mm; a do talhão continua
  96,4.
- A época passa a rodar todo dia, no grupo D do `ATUALIZAR_DIAGNOSTICO.bat`,
  porque a data do PIMS muda com a carga diária do percentual oficial.
- Se a `STATUS_REPORT_VANT` vier vazia, clima e época ficam só com o inventário,
  e o log avisa.
- A **geometria** das falhas continua sendo a do inventário
  ([ADR 0006](0006-inventario-como-alvo-do-join.md)). Só a data mudou de fonte.
