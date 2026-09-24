@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe py -3.13 -m venv .venv
if errorlevel 1 (
  echo Python 3.13 x64 is required for the modern environment.
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -e .
if errorlevel 1 exit /b 1
echo Virtual environment ready.
