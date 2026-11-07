# DID 1.0.14 sharing + automatic refresh. No install, publish or Supabase mutation.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    Write-Host 'DID Character Sheet 1.0.14 - Sharing and Auto-Refresh' -ForegroundColor Cyan
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python is not available on PATH.' }
    & python '.\patch_did114_sharing_refresh.py'
    if ($LASTEXITCODE -ne 0) { throw 'Patch stopped; see STOP: line. No installer built.' }

    Write-Host 'Running 1.0.14 tests (logging full output)...' -ForegroundColor Cyan
    $testLog = Join-Path $root 'DID_1.0.14_sharing_refresh_tests.log'
    # unittest writes test progress to stderr. Use cmd redirection so PS 5.1
    # does not misclassify every test line as NativeCommandError.
    & cmd.exe /d /s /c 'python -m unittest discover -s DID_Important_Tests -p test_1_0_14*.py -v > DID_1.0.14_sharing_refresh_tests.log 2>&1'
    $code = $LASTEXITCODE
    if (Test-Path -LiteralPath $testLog) { Get-Content -LiteralPath $testLog | Select-Object -Last 45 }
    if ($code -ne 0) { throw "Automated tests failed ($code). Read $testLog. No installer built." }

    if (-not (Test-Path -LiteralPath '.\BUILD_DID_1.0.14.ps1')) {
        throw 'Missing BUILD_DID_1.0.14.ps1. Keep your existing 1.0.14 installer build files.'
    }
    Write-Host 'Building existing DID Character Sheet 1.0.14 installer...' -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\BUILD_DID_1.0.14.ps1'
    if ($LASTEXITCODE -ne 0) { throw 'Installer builder failed; inspect DID_1.0.14_build.log.' }
    Write-Host 'SUCCESS: installer_output\DID_Character_Sheet_Setup_1.0.14.exe' -ForegroundColor Green
} finally { Pop-Location }
