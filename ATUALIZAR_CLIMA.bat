@echo off
REM =====================================================================
REM  ATVOS - Atualizacao diaria do clima do diagnostico de falhas
REM
REM  1) carga_monitoramento_zeus.py  -> MONITORAMENTO_ESTACAO
REM                                     (planilha de ENTRADAS\CLIMA)
REM  2) vincular_talhao_estacao.py   -> TALHAO_ESTACAO (talhoes novos da base)
REM  3) indicadores_clima_talhao.py  -> INDICADORES_CLIMA_TALHAO
REM
REM  Agendado no Task Scheduler (\GEOTECNOLOGIA\atualizar_clima), depois
REM  da atualizacao da base - o vinculo e o clima dependem dela.
REM  Cada etapa so roda se a anterior terminou bem.
REM
REM  Codigo de saida: 0 = ciclo completo | 1 = falhou (ver log)
REM =====================================================================

setlocal

REM ---------------------- CONFIGURACAO ---------------------------------
set PY="C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"
set REPO=%~dp0
set LOGDIR=D:\GEO\LOGS

REM com a saida redirecionada para arquivo, o Python usa cp1252 e quebra
REM em caracteres fora dele
set PYTHONIOENCODING=utf-8
REM ---------------------------------------------------------------------

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set STAMP=%%i
if "%STAMP%"=="" set STAMP=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%

set LOG=%LOGDIR%\atualizacao_clima_%STAMP%_%USERNAME%.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%REPO%"

echo. >> "%LOG%"
echo ================================================================ >> "%LOG%"
echo  INICIO DO CICLO  -  %DATE% %TIME%  -  %USERNAME% >> "%LOG%"
echo ================================================================ >> "%LOG%"

echo. >> "%LOG%"
echo ---------------- [1/3] carga_monitoramento_zeus.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\carga\carga_monitoramento_zeus.py" --gravar >> "%LOG%" 2>&1
if errorlevel 1 (
    echo. >> "%LOG%"
    echo [X] carga_monitoramento_zeus.py FALHOU em %TIME%. Vinculo e clima NAO rodaram. >> "%LOG%"
    endlocal
    exit /b 1
)

echo. >> "%LOG%"
echo ---------------- [2/3] vincular_talhao_estacao.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\processamento\vincular_talhao_estacao.py" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo. >> "%LOG%"
    echo [X] vincular_talhao_estacao.py FALHOU em %TIME%. Clima NAO rodou. >> "%LOG%"
    endlocal
    exit /b 1
)

echo. >> "%LOG%"
echo ---------------- [3/3] indicadores_clima_talhao.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\processamento\indicadores_clima_talhao.py" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo. >> "%LOG%"
    echo [X] indicadores_clima_talhao.py FALHOU em %TIME%. >> "%LOG%"
    endlocal
    exit /b 1
)

echo. >> "%LOG%"
echo [OK] Ciclo completo em %TIME%. >> "%LOG%"
endlocal
exit /b 0
