@echo off
setlocal
cd /d "%~dp0"

if not exist "frontend_2_8.py.phase8.bak" (
    echo No Phase 8 frontend backup was found. Nothing was changed.
    pause
    exit /b 1
)

copy /Y "frontend_2_8.py.phase8.bak" "frontend_2_8.py" >nul
if errorlevel 1 (
    echo ERROR: Could not restore frontend_2_8.py.
    pause
    exit /b 1
)

echo Restored the pre-Phase-8 frontend.
echo The extra mobile companion modules can remain in the folder; without the integration block they are not started.
pause
exit /b 0
