@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Corriendo las pruebas (no necesita internet ni credenciales)...
echo.
python -m unittest discover -s pruebas -v
echo.
echo Ahora una corrida completa con datos de ejemplo:
echo.
python recolectar.py --simular --sin-respaldo
pause
