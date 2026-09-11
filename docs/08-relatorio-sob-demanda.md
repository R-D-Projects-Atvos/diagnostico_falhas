# Relatório de falhas sob demanda — passo a passo

Atalho: `D:\GEO\CODIGOS\GERAR_RELATORIO_FALHAS.bat`

Liberado para: **João, Mateus, Leonardo e Rafael Miranda**.

---

## Três regras

1. **Rode com a sua conta normal**, sem "executar como administrador".
2. **Confira a fazenda na tela antes de responder `S`.** Um dígito trocado gera o relatório de outra fazenda sem erro nenhum.
3. **Abra o PDF antes de repassar.** O relatório mostra o que as cargas já trouxeram para o banco; ele não busca dado novo.

---

## 0. Antes do primeiro uso

- **Abra o ArcGIS Pro uma vez com a sua conta** e confirme que está logado. A licença é por usuário: sem ela, a ferramenta para em `Nao consegui carregar o ArcGIS`.
- **Faça um teste com a fazenda `320127`**, a área de referência. O esperado na tela de conferência é:

  ```
  Fazenda   : 320127 - FAZ JANDAIA (USL)
  Talhoes   : 10 talhoes com resultado de falhas publicado no PIMS
  Relatorio : 4 talhoes com linhas de falha carregadas
  Falhas    : 12.65% nos talhoes do relatorio (8.58% na fazenda toda)
              meta de 4.2%: ACIMA da meta
  ```

  E no fim, uma pasta aberta com `relatorio_falhas_320127.pdf` de 3 páginas.

---

## 1. Gerar

1. Dê dois cliques em `GERAR_RELATORIO_FALHAS.bat`.
2. Espere carregar o ArcGIS (uns 30 segundos).
3. Digite o **código da fazenda** (6 dígitos) e tecle ENTER.
4. **Confira o que apareceu**: nome, unidade, quantos talhões vão no relatório e o percentual.
5. Responda `S` para gerar. Leva uns 10 segundos.
6. A pasta com o PDF abre sozinha. Pegue o arquivo ali.
7. A ferramenta pergunta se quer gerar outro. `N` fecha.

---

## Onde fica cada coisa

| O quê | Onde |
|---|---|
| Relatórios gerados | `D:\GEO\FALHAS\sob_demanda\<sua conta>\<data_hora>\<fazenda>_<data>\` |
| Registro de cada tentativa | `D:\GEO\LOGS\relatorio_falhas_sob_demanda_<sua conta>.log` |

Cada geração ganha uma pasta nova. Duas pessoas podem gerar a mesma fazenda no mesmo dia sem uma atrapalhar a outra.

**Não apague as pastas de outra pessoa** — o sistema nem deixa, e o registro serve para saber quem gerou o quê.

---

## Mensagens e o que fazer

| Mensagem | O que significa | O que fazer |
|---|---|---|
| `codigo invalido` | não tem 6 dígitos | digite de novo |
| `fazenda ... nao encontrada na base do relatorio` | código não existe na base | confira o código |
| `nao tem resultado de falhas publicado no PIMS` | a fazenda ainda não tem percentual oficial | não há o que gerar |
| `Relatorio : ... SEM mapa` | a fazenda não tem linhas de falha carregadas | pode gerar: sai com o percentual do PIMS e sem o mapa |
| `Esta conta nao esta liberada` | sua conta não está na lista | peça para incluí-la em `USUARIOS_LIBERADOS`, no topo de `solicitar_relatorio_falhas.py` |
| `Nao consegui carregar o ArcGIS` | Pro sem login ou sem licença nesta conta | abra o ArcGIS Pro, faça login e tente de novo |
| `PDF: nao gerado` | o navegador não conseguiu imprimir | abra o `.html` da pasta e imprima com Ctrl+P, em A4 paisagem |
| `ERRO na fazenda ...` | falha inesperada | a mensagem fica no seu arquivo de registro; não repasse relatório dessa tentativa |

---

## Cuidados antes de repassar um relatório

Pontos que o relatório ainda não trata bem. Estão em `docs/07-pendencias.md` do repositório `diagnostico_falhas`.

- **Época de plantio:** o bloco da página 1 usa só o **primeiro talhão** da fazenda. Em fazenda com talhões plantados em épocas diferentes, ele mostra uma só.
- **Chuva antes do plantio:** até a correção entrar em produção, fazendas cuja estação não tem registro nesse período aparecem com **0 mm** antes do plantio. A própria `320127` está nesse caso.
- **Fazenda processada pela metade:** se só parte dos talhões tem resultado, o percentual é calculado sobre essa parte.
