@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv-legacy\Scripts\python.exe (
  echo Run scripts\setup_venv_legacy.bat first.
  exit /b 1
)
call .venv-legacy\Scripts\activate.bat
set SCREENREC_QT=PySide2
python scripts\build.py --output-dir dist\legacy
if errorlevel 1 exit /b 1
echo Legacy build finished: dist\legacy\ScreenRec.exe
