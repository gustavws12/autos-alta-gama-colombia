@echo off
REM ============================================================
REM  Revisa si los enlaces guardados en el Excel siguen abriendo
REM  el aviso. Doble clic para ejecutar.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python verificar_enlaces.py %*
echo.
pause
