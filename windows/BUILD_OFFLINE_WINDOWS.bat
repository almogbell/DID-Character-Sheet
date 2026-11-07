@echo off
setlocal
cd /d "%~dp0"
where npm >nul 2>&1
if errorlevel 1 (
 echo ERROR: Node.js/npm is required for this one-time BUILD step.
 echo Install Node.js LTS, then run this BAT again while online.
 pause
 exit /b 1
)
call npm install --no-audit --no-fund
if errorlevel 1 (
 echo ERROR: Could not download pinned libraries. Please check your internet connection.
 pause
 exit /b 1
)
call npm run build
if errorlevel 1 (
 echo ERROR: Offline asset creation failed; DO NOT build an installer yet.
 pause
 exit /b 1
)
if not exist "dice_libs\dice-box\dice-box.es.min.js" exit /b 1
if not exist "dice_libs\d100_deps.js" exit /b 1
if not exist "dice_libs\dice-box\assets" exit /b 1
echo.
echo Assets built. Now run: py -m PyInstaller --clean --noconfirm DID_Character_Sheet.spec
echo Then compile DID_Character_Sheet_Installer_with_icon.iss with Inno Setup.
pause
