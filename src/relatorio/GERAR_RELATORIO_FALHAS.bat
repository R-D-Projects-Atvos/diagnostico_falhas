@echo off
REM =====================================================================
REM  ATVOS - Relatorio de diagnostico de falhas de plantio, sob demanda
REM
REM  Duplo clique: pede o codigo da fazenda, mostra o que encontrou,
REM  gera o PDF e abre a pasta onde ele ficou.
REM
REM  Passo a passo: D:\GEO\CODIGOS\LEIA-ME_RELATORIO_FALHAS.md
REM  Rode com a sua conta normal, sem "executar como administrador".
REM =====================================================================

setlocal
set PY="C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"
set CODIGOS=D:\GEO\CODIGOS

REM sem isso o Python usa cp1252 na janela e quebra em alguns caracteres
set PYTHONIOENCODING=utf-8

title Relatorio de falhas de plantio
cd /d "%CODIGOS%"
%PY% -u "%CODIGOS%\solicitar_relatorio_falhas.py" %*

echo.
pause
endlocal
