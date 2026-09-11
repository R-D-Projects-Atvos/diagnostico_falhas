@echo off
REM =====================================================================
REM  ATVOS - Atualizacao diaria dos dados do diagnostico de falhas
REM
REM  Tres grupos independentes - a falha de um nao impede os outros:
REM
REM   A) carga_status_report.py      -> Status_Report_VANT
REM                                     (percentual oficial, BigQuery)
REM   B) sincronizar_surveys_vant.py -> STG_PORTE_AVALIACAO, STG_VOO_MISSAO
REM                                     (Portal) e correcao do chavesig na origem
REM   C) carga_monitoramento_zeus.py -> MONITORAMENTO_ESTACAO
REM                                     (planilha de ENTRADAS\CLIMA)
REM      vincular_talhao_estacao.py  -> TALHAO_ESTACAO
REM      indicadores_clima_talhao.py -> INDICADORES_CLIMA_TALHAO
REM      Dentro do C, cada etapa so roda se a anterior terminou bem.
REM
REM  Agendado no Task Scheduler (\GEOTECNOLOGIA\atualizar_diagnostico), 6h,
REM  depois da atualizacao da base - o vinculo e o clima dependem dela.
REM
REM  Codigo de saida: 0 = tudo certo | 1 = alguma etapa falhou (ver log)
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

set LOG=%LOGDIR%\atualizacao_diagnostico_%STAMP%_%USERNAME%.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%REPO%"
set FALHOU=0

echo. >> "%LOG%"
echo ================================================================ >> "%LOG%"
echo  INICIO DO CICLO  -  %DATE% %TIME%  -  %USERNAME% >> "%LOG%"
echo ================================================================ >> "%LOG%"

REM --------------------------- A --------------------------------------
echo. >> "%LOG%"
echo ---------------- [A] carga_status_report.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\carga\carga_status_report.py" --gravar >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [X] carga_status_report.py FALHOU em %TIME%. >> "%LOG%"
    set FALHOU=1
)

REM --------------------------- B --------------------------------------
echo. >> "%LOG%"
echo ---------------- [B] sincronizar_surveys_vant.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\carga\sincronizar_surveys_vant.py" --gravar >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [X] sincronizar_surveys_vant.py FALHOU em %TIME%. >> "%LOG%"
    set FALHOU=1
)

REM --------------------------- C --------------------------------------
echo. >> "%LOG%"
echo ---------------- [C1] carga_monitoramento_zeus.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\carga\carga_monitoramento_zeus.py" --gravar >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [X] carga_monitoramento_zeus.py FALHOU em %TIME%. Vinculo e clima NAO rodaram. >> "%LOG%"
    set FALHOU=1
    goto FIM
)

echo. >> "%LOG%"
echo ---------------- [C2] vincular_talhao_estacao.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\processamento\vincular_talhao_estacao.py" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [X] vincular_talhao_estacao.py FALHOU em %TIME%. Clima NAO rodou. >> "%LOG%"
    set FALHOU=1
    goto FIM
)

echo. >> "%LOG%"
echo ---------------- [C3] indicadores_clima_talhao.py  %TIME% ---------------- >> "%LOG%"
%PY% -u "%REPO%src\processamento\indicadores_clima_talhao.py" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [X] indicadores_clima_talhao.py FALHOU em %TIME%. >> "%LOG%"
    set FALHOU=1
)

:FIM
echo. >> "%LOG%"
if "%FALHOU%"=="0" (
    echo [OK] Ciclo completo em %TIME%. >> "%LOG%"
) else (
    echo [X] Ciclo terminou com falha em %TIME% - ver as etapas marcadas com [X]. >> "%LOG%"
)
endlocal & exit /b %FALHOU%
