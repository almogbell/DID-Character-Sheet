# DID Character Sheet v1.0.14 UI repair and installer build (no publishing).
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    if (-not (Test-Path '.\campaign_role_ui.py')) { throw 'campaign_role_ui.py is missing. Extract the ZIP into your current code folder.' }
    if (-not (Test-Path '.\BUILD_DID_1.0.14.ps1')) { throw 'BUILD_DID_1.0.14.ps1 is missing; extract the main v1.0.14 build package first.' }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found on PATH.' }
    $log = Join-Path $root 'DID_1.0.14_UI_followup.log'
    Write-Host 'Fixing 1.0.14 Campaign Manager UI (duplicate shared hooks / clipped tabs)...' -ForegroundColor Cyan
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & python '.\apply_did_1_0_14_ui_polish.py' 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            Add-Content -LiteralPath $log -Value $line
        }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($code -ne 0) { throw "Patch failed ($code). Copy the STOP line from $log. No installer was built." }
    & python -m py_compile '.\campaign_role_ui.py'
    if ($LASTEXITCODE -ne 0) { throw 'Syntax validation failed.' }
    & python -m unittest discover -s '.\DID_Important_Tests' -p 'test_1_0_14_ui_repair_v3.py' -v
    if ($LASTEXITCODE -ne 0) { throw '1.0.14 UI repair tests failed. No installer built.' }
    Write-Host 'Rebuilding and packaging v1.0.14...' -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\BUILD_DID_1.0.14.ps1'
    if ($LASTEXITCODE -ne 0) { throw 'The 1.0.14 installer build failed. Check DID_1.0.14_build.log.' }
    $output = Join-Path $root 'installer_output\DID_Character_Sheet_Setup_1.0.14.exe'
    if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw "Installer not found: $output" }
    Write-Host "Installer: $output" -ForegroundColor Green
} finally { Pop-Location }
