# Como contribuir

## Branches

`main` é estável — o que está lá roda. Trabalho novo em `feat/nome-curto`,
correções em `fix/nome-curto`.

## Commits

Em português, no imperativo, dizendo o efeito:

```
acrescenta gráfico de chuva diária na página 3
corrige formatação de data vinda do driver ODBC
```

Evite `ajustes`, `wip`, `correções diversas`.

## Antes de abrir PR

- O script roda de ponta a ponta na área piloto?
- Os valores de referência batem? (ver `docs/06-operacao.md`)
- A mudança altera alguma regra de negócio? Atualize
  `docs/04-regras-de-negocio.md`.
- A decisão pode ser questionada em seis meses? Escreva um ADR.

## Sobre os ADRs

Registre a decisão **e as alternativas descartadas**, com o motivo. O ADR 0003
é um bom exemplo: documenta uma correção que teria sido pior que o problema, e
por quê. Isso evita que alguém refaça o mesmo caminho.

## Parâmetros

Todo número que alguém pode querer mudar fica em constante no topo do script,
com comentário explicando de onde saiu. Nada de valor mágico no meio do código.

## Estilo

Português nos comentários e nas mensagens. Comentário explica **por que**, não
o que — o código já diz o que faz.
