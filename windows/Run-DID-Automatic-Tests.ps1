# DID Character Sheet 1.0.14 - offline automated test launcher
# Example: powershell -NoProfile -ExecutionPolicy Bypass -File .\Run-DID-Automatic-Tests.ps1
# Optional: -Quick, -ProjectDir "C:\...\current code - Copy", -AndroidProject "C:\...\DIDAndroid"
[CmdletBinding()]
param(
    [string]$ProjectDir = '',
    [switch]$Quick,
    [string]$AndroidProject = '',
    [string]$ReportDir = ''
)
$ErrorActionPreference = 'Stop'

try {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $driver = Join-Path $here 'DID_Automatic_Tests.py'
    if (-not (Test-Path -LiteralPath $driver)) {
        throw "Missing DID_Automatic_Tests.py beside this script. Extract both files from the test ZIP."
    }

    if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
        if (Test-Path -LiteralPath (Join-Path $here 'frontend_2_8.py')) {
            $ProjectDir = $here
        } elseif (Test-Path -LiteralPath (Join-Path $here 'current code - Copy\frontend_2_8.py')) {
            $ProjectDir = Join-Path $here 'current code - Copy'
        } else {
            $ProjectDir = Join-Path ([Environment]::GetFolderPath('Desktop')) 'DID_1_0_14_Test\current code - Copy'
        }
    }
    $ProjectDir = (Resolve-Path -LiteralPath $ProjectDir -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir 'frontend_2_8.py'))) {
        throw "frontend_2_8.py not found in project folder: $ProjectDir"
    }

    $python = Join-Path $ProjectDir '.venv\Scripts\python.exe'
    $pyArgs = @()
    if (-not (Test-Path -LiteralPath $python)) {
        $cmd = Get-Command py -ErrorAction SilentlyContinue
        if ($cmd) {
            $python = $cmd.Source
            $pyArgs = @('-3')
        } else {
            $cmd = Get-Command python -ErrorAction SilentlyContinue
            if ($cmd) {
                $python = $cmd.Source
            } else {
                throw "Python not found. Activate or create a .venv in the DID project."
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ReportDir)) {
        $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
        $ReportDir = Join-Path ([Environment]::GetFolderPath('Desktop')) "DID_Test_Reports\$stamp"
    }
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

    Write-Host "";
    Write-Host 'DID Character Sheet - Automated Tests' -ForegroundColor Cyan
    Write-Host "Project: $ProjectDir"
    Write-Host "Python:  $python"
    Write-Host "Reports: $ReportDir"
    Write-Host 'Your actual character files and campaign data will not be used for these tests.'
    Write-Host ""

    $argsForPython = @() + $pyArgs + @($driver, '--project-dir', $ProjectDir, '--report-dir', $ReportDir)
    if ($Quick) { $argsForPython += '--quick' }
    if (-not [string]::IsNullOrWhiteSpace($AndroidProject)) {
        $argsForPython += @('--android-project', $AndroidProject)
    } else {
        $defaultAndroid = Join-Path ([Environment]::GetFolderPath('Desktop')) 'DIDAndroid'
        if (Test-Path -LiteralPath (Join-Path $defaultAndroid 'phase8\DidOfflineStore.kt')) {
            $argsForPython += @('--android-project', $defaultAndroid)
        }
    }
    & $python @argsForPython
    $code = $LASTEXITCODE

    $html = Join-Path $ReportDir 'DID_Test_Report.html'
    Write-Host ""
    if (Test-Path -LiteralPath $html) {
        Write-Host "Opening results: $html" -ForegroundColor Cyan
        Start-Process -FilePath $html
    }
    if ($code -eq 0) {
        Write-Host 'Automatic checks completed without reported failures.' -ForegroundColor Green
    } else {
        Write-Warning "One or more checks failed or were blocked. Read the report for details (exit code $code)."
    }
    exit $code
} catch {
    Write-Error $_.Exception.Message
    exit 2
}
