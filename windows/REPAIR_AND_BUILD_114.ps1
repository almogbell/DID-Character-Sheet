# Fix outdated 1.0.14 tab width test, then run existing UI follow-up builder.
# Requires the existing 1.0.14 build scripts already extracted.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    if (-not (Test-Path -LiteralPath '.\BUILD_DID_1.0.14_UI_FOLLOWUP.ps1')) {
        throw 'Missing BUILD_DID_1.0.14_UI_FOLLOWUP.ps1. Keep your existing 1.0.14 project files.'
    }
    Write-Host 'Correcting the outdated 280px campaign-tab regression test...' -ForegroundColor Cyan
    & python '.\fix_did_114_conflicting_test.py'
    if ($LASTEXITCODE -ne 0) { throw 'Test repair stopped. No installer was built.' }
    Write-Host 'Running the full 1.0.14 test suite...' -ForegroundColor Cyan
    & python -m unittest discover -s DID_Important_Tests -p 'test_1_0_14*.py' -v
    if ($LASTEXITCODE -ne 0) {
        throw 'Other tests still fail. Copy the FAIL/ERROR block from this output; no installer built.'
    }
    Write-Host 'Rebuilding the 1.0.14 installer with the existing follow-up script...' -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\BUILD_DID_1.0.14_UI_FOLLOWUP.ps1'
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed. See DID_1.0.14_build.log for details.' }
} finally { Pop-Location }
