@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_PROBLEM20_INSTALLER.ps1"
set "rc=%ERRORLEVEL%"
echo.
if not "%rc%"=="0" echo BUILD FAILED. Read the error above. Existing installation was not modified.
if "%rc%"=="0" echo You can find the installer in the installer_output folder.
pause
exit /b %rc%
