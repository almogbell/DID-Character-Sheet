@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_DID_1.0.14.ps1"
if errorlevel 1 (
    echo.
    echo BUILD FAILED - See the error above. No application was installed.
    pause
    exit /b 1
)
echo.
echo Build finished. See installer_output folder.
pause
