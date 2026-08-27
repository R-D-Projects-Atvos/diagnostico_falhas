# ADR 0007 — Escala fixa, ancorada no semáforo

**Data:** agosto/2026
**Situação:** aceita

## Contexto

O mapa de calor mostra densidade de falhas em metros por hectare. A
classificação poderia ser relativa a cada área (quebras naturais, quantis) ou
fixa.

## Decisão

Quebras fixas, derivadas dos limiares do semáforo. Com espaçamento de 1,5 m há
6.667 m lineares por hectare:

| Densidade | Percentual equivalente |
|---|---|
| 280 m/ha | 4,2% — meta |
| 500 m/ha | 7,5% — atenção |
| 1.000 m/ha | 15% — crítico |

## Consequências

**Comparabilidade.** Com classificação relativa, um talhão excelente pareceria
vermelho no próprio mapa e a comparação entre áreas e safras se perderia.

**Coerência.** O mapa passa a falar a mesma língua da tabela: verde é o que está
na meta, vermelho é o que passa de 15%.

**Custo.** Áreas muito ruins pintam quase inteiras na classe mais alta, e o
mapa perde poder de discriminação interna. Na área piloto, com média de 831
m/ha, 64% da área fica acima de 500. É o comportamento correto — a área é ruim
—, mas quem olhar esperando gradiente vai achar o mapa "estourado".

## Calibração

As quebras provisórias iniciais (300/600/900) foram substituídas depois de
medir a área piloto: densidade observada de 43 a 2.802 m/ha, média de 831.

Vale rodar em duas ou três áreas boas antes de fixar como padrão corporativo.
