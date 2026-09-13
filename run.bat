@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ==============================
echo   PyMaster - ambiente local
echo  ==============================
echo.

rem --- Localizar o Python (venv, launcher py, PATH ou pastas padrao) ---
set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE call :find_python
if not defined PYEXE call :install_or_ask_python
if not defined PYEXE (
  echo.
  echo  [PyMaster] Nao foi possivel obter um Python valido.
  echo  Instale manualmente em https://www.python.org/downloads/ e rode este arquivo novamente.
  echo.
  pause
  exit /b 1
)
echo  [PyMaster] Python encontrado: %PYEXE%

if not exist ".venv\Scripts\python.exe" (
  echo  [PyMaster] Criando ambiente virtual...
  "%PYEXE%" -m venv .venv
  if errorlevel 1 (
    echo  [PyMaster] Falha ao criar o ambiente virtual.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 (
    echo  [PyMaster] Falha ao atualizar o pip.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo  [PyMaster] Falha ao instalar as dependencias.
    pause
    exit /b 1
  )
)

if not exist "app\data\datasets\vendas.csv" (
  echo  [PyMaster] Gerando datasets de exemplo...
  ".venv\Scripts\python.exe" scripts\generate_datasets.py
)

rem --- Aviso se a porta 8000 ja estiver ocupada ---
netstat -ano 2>nul | findstr ":8000" 2>nul | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo.
  echo  [PyMaster] ATENCAO: a porta 8000 ja esta em uso.
  echo  Ha outra janela do PyMaster aberta ou um processo antigo rodando.
  echo  Feche a outra janela e execute este arquivo novamente.
  echo.
)

echo.
echo  [PyMaster] Subindo o servidor em http://127.0.0.1:8000
echo  A janela precisa continuar aberta enquanto voce estuda.
echo  Para parar: Ctrl+C ou feche esta janela.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo  [PyMaster] O servidor encerrou.
pause
endlocal
exit /b 0

rem -------------------------------------------------------------------------
rem  :find_python - procura Python no launcher "py", no PATH e em pastas padrao
rem -------------------------------------------------------------------------
:find_python
where py >nul 2>nul
if not errorlevel 1 (
  for /f "usebackq tokens=*" %%i in (`py -3.12 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
  if not defined PYEXE (
    for /f "usebackq tokens=*" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
  )
)
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python312\python.exe" set "PYEXE=%ProgramFiles%\Python312\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "usebackq tokens=*" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
    rem Python vindo da Microsoft Store costuma falhar ao criar venv -> ignora e pede instalacao via winget
    if defined PYEXE (
      echo !PYEXE! | findstr /I "WindowsApps MicrosoftAppData" >nul 2>&1
      if not errorlevel 1 set "PYEXE="
    )
  )
)
goto :eof

rem -------------------------------------------------------------------------
rem  :install_or_ask_python - instala via winget ou aceita caminho manual
rem -------------------------------------------------------------------------
:install_or_ask_python
echo.
echo  [PyMaster] Python nao foi encontrado (nem no PATH, nem em pastas padrao).
echo  Voce pode instalar o Python 3.12 automaticamente via winget,
echo  ou informar o caminho de uma instalacao existente.
echo.
set /p "OPCAO=Instalar via winget agora (S) ou informar o caminho manualmente (M)? [S/M]: "
if /i "%OPCAO%"=="M" goto :ask_manual_path

where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo  [PyMaster] winget nao esta disponivel neste computador.
  goto :ask_manual_path
)
echo  [PyMaster] Instalando o Python 3.12... (pode pedir permissao de administrador)
winget install --id Python.Python.3.12 -e --source winget --silent --accept-package-agreements --accept-source-agreements >nul
if errorlevel 1 (
  echo.
  echo  [PyMaster] Falha ao instalar automaticamente.
  goto :ask_manual_path
)
echo  [PyMaster] Python 3.12 instalado com sucesso.
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python312\python.exe" set "PYEXE=%ProgramFiles%\Python312\python.exe"
goto :eof

:ask_manual_path
echo.
set /p "PYEXE=Informe o caminho completo do python.exe (ex.: C:\Python312\python.exe), ou Enter para sair: "
if not defined PYEXE exit /b 1
if not exist "%PYEXE%" (
  echo.
  echo  [PyMaster] Caminho invalido: "%PYEXE%"
  goto :ask_manual_path
)
goto :eof