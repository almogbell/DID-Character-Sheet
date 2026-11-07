# DID Character Sheet 1.0.13 / Problem 20 -- Windows installer builder
# Run from the Windows source folder. Does not install or publish any files.
#requires -Version 5.1
param(
    [string] $AndroidProject = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'DIDAndroid')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:DID_ANDROID_PROJECT = $AndroidProject

function RequireFile([string] $file, [string] $description) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "$description missing: $file" }
}
function RunPython([string[]] $Arguments) {
    & python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python returned exit code ${LASTEXITCODE}: python $($Arguments -join ' ')" }
}
function ContainsText([string] $file, [string] $text) {
    RequireFile $file "Source to inspect"
    return (Get-Content -LiteralPath $file -Raw).Contains($text)
}

Write-Host 'DID Character Sheet 1.0.13 -- Problem 20 installer build' -ForegroundColor Cyan
Write-Host 'This builds a new installer only. No installation, publishing, or data deletion.'
RequireFile (Join-Path $root 'DID_Character_Sheet.spec') 'PyInstaller spec'
RequireFile (Join-Path $root 'DID_Character_Sheet_Installer_with_icon.iss') 'Inno Setup installer config'
RequireFile (Join-Path $root 'mobile_sync_frontend_adapter.py') 'Windows sync code'
RequireFile (Join-Path $root 'patch_problem20_auto_merge.py') 'Problem 20 patcher'
RequireFile (Join-Path $root 'mobile_sync_merge.py') 'Problem 20 merge module'
RequireFile (Join-Path $AndroidProject 'phase8\DidCompanionViewModel.kt') 'Android view model'
RequireFile (Join-Path $AndroidProject 'phase8\DidOfflineStore.kt') 'Android offline store'
RequireFile (Join-Path $AndroidProject 'phase8\Phase9CompanionSheetV8.kt') 'Android character screen'
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found on PATH.' }

Push-Location $root
try {
    $windowsSync = Join-Path $root 'mobile_sync_frontend_adapter.py'
    $phoneVm = Join-Path $AndroidProject 'phase8\DidCompanionViewModel.kt'
    $windowsPatched = ContainsText $windowsSync 'HP_AT_CONFLICT:'
    $androidPatched = ContainsText $phoneVm 'requeueResourceDecision('
    if ($windowsPatched -ne $androidPatched) {
        throw 'Problem 20 is only partially applied across Windows/Android. STOP and review existing code before rebuilding.'
    }
    if (-not $windowsPatched) {
        Write-Host 'Applying Problem 20 to current Windows and Android source (with timestamped backups)...'
        RunPython @('.\patch_problem20_auto_merge.py', $AndroidProject)
    } else {
        Write-Host 'Problem 20 markers already present. Keeping existing patched source.'
    }
    if (-not (ContainsText $windowsSync 'merge_v2') -or
        -not (ContainsText $phoneVm 'requeueResourceDecision(')) {
        throw 'Problem 20 merge contract was not found after patch. Cannot package an incomplete update.'
    }
    Write-Host 'Running Problem 20 regression tests...'
    RequireFile (Join-Path $root 'DID_Important_Tests\test_problem20_merge_logic.py') 'Problem 20 tests'
    RunPython @('-m', 'unittest', 'discover', '-s', 'DID_Important_Tests', '-p', 'test_problem20*.py', '-v')

    $preflight = Join-Path $root 'release_preflight.py'
    if (Test-Path -LiteralPath $preflight -PathType Leaf) {
        Write-Host 'Running Windows release preflight...'
        RunPython @('.\release_preflight.py')
    } else {
        Write-Host 'Note: release_preflight.py not found. Existing Inno validation will still run.' -ForegroundColor Yellow
    }

    $start = Get-Date
    Write-Host 'Building a NEW Windows EXE using the current sources...'
    RunPython @('-m', 'PyInstaller', '--clean', '--noconfirm', 'DID_Character_Sheet.spec')
    $builtExe = Join-Path $root 'dist\DID Character Sheet.exe'
    RequireFile $builtExe 'Rebuilt Windows EXE'
    if ((Get-Item $builtExe).LastWriteTime -lt $start.AddSeconds(-5)) {
        throw 'Packaged EXE is older than this build; refusing to package a stale executable.'
    }

    $outputDir = Join-Path $root 'installer_output'
    $output = Join-Path $outputDir 'DID_Character_Sheet_Setup_1.0.13.exe'
    if (Test-Path -LiteralPath $output -PathType Leaf) {
        $saved = Join-Path $outputDir ('DID_Character_Sheet_Setup_1.0.13.before_problem20_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.exe')
        Copy-Item -LiteralPath $output -Destination $saved -ErrorAction Stop
        Write-Host "Preserved earlier installer: $saved"
    }

    $helper = Join-Path $root 'BUILD_DID_1.0.13_INSTALLER.ps1'
    if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
        $bundledHelper = Join-Path $root 'problem20_support\BUILD_DID_1.0.13_INSTALLER.ps1'
        RequireFile $bundledHelper 'Bundled Inno Setup builder'
        Copy-Item -LiteralPath $bundledHelper -Destination $helper
    }
    Write-Host 'Building Inno Setup 1.0.13 installer...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $helper
    if ($LASTEXITCODE -ne 0) { throw "Installer builder failed with exit code $LASTEXITCODE" }
    RequireFile $output 'Installer output'
    $file = Get-Item $output
    if ($file.LastWriteTime -lt $start.AddSeconds(-5)) {
        throw 'Installer timestamp is older than the new EXE build. Packaging may have reused an earlier installer.'
    }
    $sum = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
    Write-Host ''
    Write-Host 'SUCCESS: NEW WINDOWS INSTALLER BUILT (NOT INSTALLED OR PUBLISHED).' -ForegroundColor Green
    Write-Host "File: $output"
    Write-Host "Size: $([math]::Round($file.Length/1MB, 2)) MB"
    Write-Host "SHA256: $sum"
    Write-Host 'Please verify campaign screens and phone sync in the installed build before release.'
} finally {
    Pop-Location
}
