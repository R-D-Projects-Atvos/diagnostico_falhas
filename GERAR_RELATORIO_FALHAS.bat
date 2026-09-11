@echo off
REM =====================================================================
REM  ATVOS - Relatorio de diagnostico de falhas de plantio, sob demanda
REM
REM  Duplo clique: pede o codigo da fazenda, mostra o que encontrou,
REM  gera o PDF e abre a pasta onde ele ficou.
REM
REM  Roda direto deste repositorio: D:\GEO\REPOS\diagnostico_falhas
REM  Passo a passo: docs\08-relatorio-sob-demanda.md
REM  Rode com a sua conta normal, sem "executar como administrador".
REM =====================================================================

setlocal

REM sem isso o Python usa cp1252 na janela e quebra em alguns caracteres
set PYTHONIOENCODING=utf-8

title Relatorio de falhas de plantio
call "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" -u "%~dp0src\relatorio\solicitar_relatorio_falhas.py" %*

echo.
pause
endlocal
