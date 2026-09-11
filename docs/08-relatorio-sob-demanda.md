# Relatório de falhas sob demanda — passo a passo

Atalho: `D:\GEO\REPOS\diagnostico_falhas\GERAR_RELATORIO_FALHAS.bat`

Liberado para: **João, Mateus, Leonardo e Rafael Miranda**.

A ferramenta roda direto deste repositório. **Não copie os arquivos para
`D:\GEO\CODIGOS`** — lá ficou só um aviso apontando para cá.

---

## Três regras

1. **Rode com a sua conta normal**, sem "executar como administrador".
2. **Confira a fazenda na tela antes de responder `S`.** Um dígito trocado gera o relatório de outra fazenda sem erro nenhum.
3. **Abra o PDF antes de repassar.** O relatório mostra o que está no banco, mais as linhas que você salvou na pasta; o resto ele não busca.

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

## 1. Para ter os mapas, salve as linhas da Bem Agro

Baixe as linhas de falha da fazenda na plataforma da Bem Agro e salve em
`Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\LINHAS`, na biblioteca da
Geotecnologia, do jeito que vieram — o `.zip` serve, não precisa renomear nem
descompactar. Baixe a **fazenda inteira** e espere o OneDrive terminar de
sincronizar.

Sem linhas, o relatório sai com o percentual do PIMS e sem os mapas.

## 2. Gerar

1. Dê dois cliques em `GERAR_RELATORIO_FALHAS.bat`.
2. Espere carregar o ArcGIS (uns 30 segundos).
3. Digite o **código da fazenda** (6 dígitos) e tecle ENTER.
4. Se houver linhas na pasta, a ferramenta mostra o que achou — a fazenda, cada talhão com as linhas novas e as que estão no banco hoje — e pergunta `Carregar estas linhas?`. **Confira a fazenda** e responda `S`. Leva cerca de 1 minuto, com o mapa de calor.
5. **Confira o que apareceu**: nome, unidade, quantos talhões vão no relatório e o percentual.
6. Responda `S` para gerar. Leva uns 10 segundos.
7. A pasta com o PDF abre sozinha. Pegue o arquivo ali.
8. A ferramenta pergunta se quer gerar outro. `N` fecha.

---

## Onde fica cada coisa

| O quê | Onde |
|---|---|
| Relatórios gerados | `D:\GEO\FALHAS\sob_demanda\<sua conta>\<data_hora>\<fazenda>_<data>\` |
| Registro de cada tentativa | `D:\GEO\LOGS\relatorio_falhas_sob_demanda_<sua conta>.log` |
| Linhas da Bem Agro para carregar | `Projetos_Cart\DIAGNOSTICO_FALHAS\ENTRADAS\LINHAS` |
| Linhas já carregadas | `ENTRADAS\LINHAS\CARREGADAS\<fazenda>_<data_hora>_<conta>\` |

Cada geração ganha uma pasta nova. Duas pessoas podem gerar a mesma fazenda no mesmo dia sem uma atrapalhar a outra.

**Não apague as pastas de outra pessoa** — o sistema nem deixa, e o registro serve para saber quem gerou o quê.

---

## Mensagens e o que fazer

| Mensagem | O que significa | O que fazer |
|---|---|---|
| `codigo invalido` | não tem 6 dígitos | digite de novo |
| `fazenda ... nao encontrada na base do relatorio` | código não existe na base | confira o código |
| `nao tem resultado de falhas publicado no PIMS` | a fazenda ainda não tem percentual oficial | não há o que gerar |
| `Relatorio : ... SEM mapa` | a fazenda não tem linhas de falha carregadas | salve as linhas da Bem Agro em `ENTRADAS\LINHAS` e peça de novo, ou gere sem o mapa |
| `NADA CARREGADO: nao consegui abrir a entrega` | o arquivo ainda está sincronizando ou veio corrompido | espere o OneDrive terminar e peça de novo; se repetir, baixe de novo |
| `NADA CARREGADO: ... fora dos talhoes da BASE_SAFRA` | as linhas não caem nos talhões do inventário | confira se baixou a fazenda certa; a entrega fica na pasta |
| `fazenda ...: ... linhas pela borda, nao entram` | poucas linhas de fazenda vizinha | normal, nada a fazer |
| `ATENCAO: as linhas carregadas agora sao da(s) fazenda(s) ...` | as linhas salvas são de outra fazenda | confira o download e peça o relatório da fazenda certa |
| `nao consegui abrir a pasta de linhas com a conta ...` | sua conta não tem permissão na pasta | peça ao João; o relatório sai com as linhas que já estavam no banco |
| `AVISO: o mapa de calor da fazenda ... nao foi gerado` | as linhas entraram, o mapa não | o relatório sai sem o mapa de calor; avise o João |
| `Esta conta nao esta liberada` | sua conta não está na lista | peça para incluí-la em `USUARIOS_LIBERADOS`, no topo de `src\relatorio\solicitar_relatorio_falhas.py` |
| `Nao consegui carregar o ArcGIS` | Pro sem login ou sem licença nesta conta | abra o ArcGIS Pro, faça login e tente de novo |
| `PDF: nao gerado` | o navegador não conseguiu imprimir | abra o `.html` da pasta e imprima com Ctrl+P, em A4 paisagem |
| `ERRO na fazenda ...` | falha inesperada | a mensagem fica no seu arquivo de registro; não repasse relatório dessa tentativa |

---

## Cuidados antes de repassar um relatório

Pontos que o relatório ainda não trata bem. Estão em `docs/07-pendencias.md` do repositório `diagnostico_falhas`.

- **Época de plantio:** o bloco da página 1 usa só o **primeiro talhão** da fazenda. Em fazenda com talhões plantados em épocas diferentes, ele mostra uma só.
- **Linhas de parte da fazenda:** cada talhão que vier na entrega tem as linhas trocadas pelas novas. Se o download trouxer só parte de um talhão, ele fica só com essa parte. Baixe sempre a fazenda inteira.
- **Fazenda processada pela metade:** se só parte dos talhões tem resultado, o percentual é calculado sobre essa parte.
