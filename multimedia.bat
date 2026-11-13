@echo off
rem Grabador de voces del Laboratorio 4: abre http://localhost:5000
setlocal
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PY%" goto :correr
echo [aviso] No existe .venv: ejecuta update.bat. Por ahora se usa el python del sistema (sin clonacion).
set "PY=python"
"%PY%" -c "import flask, soundfile, numpy" 2>nul || "%PY%" -m pip install flask==3.1.0 soundfile numpy

:correr
echo Python usado: %PY%
"%PY%" -c "import TTS" 2>nul || echo [aviso] Falta XTTS: ejecuta update.bat. "Entrenar" solo hara control de calidad.
"%PY%" multimedia\grabador_voz.py
pause
