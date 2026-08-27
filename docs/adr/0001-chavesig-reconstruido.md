# ADR 0001 — Chavesig reconstruído no staging

**Data:** agosto/2026
**Situação:** aceita

## Contexto

Os dois surveys de VANT calculam o `chavesig` no próprio formulário, por um
`calculate` dentro do repeat de talhões. Esse cálculo falha de forma
intermitente.

Evidência coletada em produção:

- Na primeira análise, 21 de 50 linhas do repeat do porte estavam corrompidas.
  Avaliações de **um** talhão sempre acertavam; avaliações multi-talhão erravam
  na maioria das linhas, gravando sufixo `0000` ou o valor de outro talhão.
- No Registro de Missão, o `chavesig` estava **nulo em 100%** da amostra —
  pilotos submetendo com versão anterior do formulário.
- Três correções foram publicadas (v3.0, v3.1, v3.2 do porte, com fórmula
  travada por `if()`, note de conferência no repeat, `allowUpdates=true`, e por
  fim dependência de campo posterior ao repeat). **Nenhuma resolveu.** Na
  última, em avaliação com quatro talhões, só a última linha gravou.

O `calculate` é avaliado durante a digitação e não é reavaliado depois — um
talhão digitado como "1" e corrigido para "10" mantinha o sufixo `0001`.

## Decisão

O `chavesig` gravado pelo formulário é **campo de conferência**, exibido ao
piloto. A chave usada no pipeline é reconstruída no staging:

```
Chavesig = LPAD(cod_fazenda,6) + LPAD(cod_setor,4) + LPAD(cod_talhao,4)
```

Os três componentes têm constraint no formulário e estão sempre corretos.

## Consequências

**Boas.** O pipeline não depende de versão de formulário, de o piloto atualizar
o app nem de sincronismo. É determinístico.

**Ruins.** O campo no serviço continua podendo ficar nulo ou errado para quem
consumir o serviço diretamente. Por isso o
`sincronizar_surveys_vant.py` corrige a origem a cada execução, com registro em
`LOG_CHAVESIG_SURVEYS`.

**Ganho lateral.** A v3.2 pelo menos falha de forma segura: grava nulo em vez de
sufixo `0000`, que passaria por chave válida e produziria join silencioso no
talhão errado.

## Nota

Foram três ciclos de publicação para um campo que é conveniência, não fonte de
verdade. O aprendizado: quando o dado componente está correto e validado,
reconstruir é mais barato e mais confiável que insistir na origem.
