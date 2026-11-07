@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_DID_1.0.14_UI_FOLLOWUP.ps1"
if errorlevel 1 (
 echo Build failed. Read DID_1.0.14_UI_followup.log and DID_1.0.14_build.log
 pause
 exit /b 1
)
pause
