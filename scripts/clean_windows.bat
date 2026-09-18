@echo off
setlocal
cd /d "%~dp0.."

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .test-output rmdir /s /q .test-output
del /q *.spec 2>nul

for /d /r %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d" 2>nul
for /d /r %%d in (*.egg-info) do if exist "%%d" rmdir /s /q "%%d" 2>nul

echo Project cleaned.
endlocal
