@echo off
setlocal
cd /d "%~dp0"

echo DID Character Sheet - Phase 8 mobile companion setup
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    set "PY=python"
)

if not exist "frontend_2_8.py" (
    echo ERROR: frontend_2_8.py was not found in this folder.
    echo Extract this Phase 8 package into a COPY of your finished DID current code folder.
    pause
    exit /b 1
)

echo Installing the QR-code dependency...
%PY% -m pip install "qrcode[pil]>=7.4.2,<9"
if errorlevel 1 goto :failed

echo Integrating Mobile Companion into frontend_2_8.py...
%PY% integrate_mobile_companion.py frontend_2_8.py --version 1.0.11
if errorlevel 1 goto :failed

echo.
echo Phase 8 integration completed.
echo A one-time frontend backup is kept as frontend_2_8.py.phase8.bak.
echo You can now start DID normally with: %PY% frontend_2_8.py
echo.
pause
exit /b 0

:failed
echo.
echo Phase 8 setup failed. Your original frontend is preserved by the integration patcher.
pause
exit /b 1
