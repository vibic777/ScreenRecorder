@echo off
cd /d "%~dp0.."
if not exist .venv-legacy\Scripts\python.exe py -3.8 -m venv .venv-legacy
if errorlevel 1 (
  echo Python 3.8 x64 is required for the legacy environment.
  exit /b 1
)
call .venv-legacy\Scripts\activate.bat
python -m pip install --upgrade "pip<24"
if errorlevel 1 exit /b 1
python -m pip install -r requirements-legacy.txt
if errorlevel 1 exit /b 1
echo Legacy environment ready: .venv-legacy