@echo off
setlocal
cd /d "%~dp0.."
if /i "%~1"=="modern" goto modern
if /i "%~1"=="legacy" goto legacy
echo Usage: scripts\build_profile.bat modern^|legacy
exit /b 2
:modern
call scripts\build_modern.bat
exit /b %errorlevel%
:legacy
echo Legacy build is paused until the Python 3.8/PySide2 environment and Windows 7/8.1 VM are available.
exit /b 3