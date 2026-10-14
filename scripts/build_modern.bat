@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Run scripts\setup_venv_windows.bat first.
  exit /b 1
)
call .venv\Scripts\activate.bat
python scripts\build.py --output-dir dist\modern
if errorlevel 1 exit /b 1
echo Modern build finished: dist\modern\ScreenRec.exe