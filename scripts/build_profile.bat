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
call scripts\build_legacy.bat
exit /b %errorlevel%
