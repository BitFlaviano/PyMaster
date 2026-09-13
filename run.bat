@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ==============================
echo   PyMaster - ambiente local
echo  ==============================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [PyMaster] Criando ambiente virtual...
  call py -3.12 -m venv .venv
  if errorlevel 1 call python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if not exist "app\data\datasets\vendas.csv" (
  echo [PyMaster] Gerando datasets de exemplo...
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