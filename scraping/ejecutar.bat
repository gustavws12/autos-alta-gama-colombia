@echo off
REM ============================================================
REM  Recoleccion de avisos de alta gama - MercadoLibre Colombia
REM  Doble clic para ejecutar. Requiere Python 3.9 o superior.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  [!] No encuentro Python en este equipo.
  echo      Instalalo desde https://www.python.org/downloads/
  echo      y marca la casilla "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

echo Verificando dependencias...
python -m pip install -q -r requirements.txt

python recolectar.py %*

echo.
pause
