@echo off
rem Crea/actualiza el entorno del Laboratorio 4 en .venv (Python 3.11) con las versiones de requirements.txt
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
if exist "%PY%" goto :instalar

echo Buscando Python 3.11...
set "BASE="
py -3.11 -c "import sys" >nul 2>nul && set "BASE=py -3.11"
if not defined BASE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set BASE="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined BASE if exist "%ProgramFiles%\Python311\python.exe" set BASE="%ProgramFiles%\Python311\python.exe"
if defined BASE goto :crear

echo No se encontro Python 3.11.
choice /m "Instalarlo ahora con winget"
if errorlevel 2 goto :sinpython
winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
if not exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" goto :sinpython
set BASE="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

:crear
echo Creando entorno .venv con %BASE%...
%BASE% -m venv "%VENV%" || goto :fallo

:instalar
echo Python usado: %PY%
echo [1/4] pip
"%PY%" -m pip install --upgrade pip || goto :fallo
echo [2/4] torch con CUDA 12.8 (descarga grande, ~2,5 GB; soporte RTX 50)
"%PY%" -m pip install --upgrade torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128 || goto :fallo
echo [3/4] requirements.txt
"%PY%" -m pip install --upgrade -r requirements.txt || goto :fallo
echo [4/4] kernel de Jupyter "Python (TAREAML4)"
"%PY%" -m ipykernel install --user --name tareaml4 --display-name "Python (TAREAML4)" || goto :fallo
echo.
echo Verificacion:
"%PY%" -c "import torch, transformers, TTS, flask, sentence_transformers, rank_bm25, jiwer; ok=torch.cuda.is_available(); print('torch', torch.__version__, '| CUDA:', ok, '|', torch.cuda.get_device_name(0) if ok else 'sin GPU'); print('OK: todas las librerias importan')" || goto :fallo
echo.
echo Listo. Usa multimedia.bat y en el notebook elige el kernel "Python (TAREAML4)".
pause
exit /b 0

:sinpython
echo [error] Instala Python 3.11 desde https://www.python.org/downloads/release/python-3119/ y vuelve a ejecutar update.bat
pause
exit /b 1

:fallo
echo.
echo [error] Fallo la instalacion. Revisa el mensaje de arriba.
pause
exit /b 1
