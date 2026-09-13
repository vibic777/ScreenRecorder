@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\activate.bat
python -m pip install -e .
if errorlevel 1 exit /b 1
echo Virtual environment ready.
