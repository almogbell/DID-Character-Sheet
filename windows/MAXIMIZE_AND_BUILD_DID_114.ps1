param([switch]$PatchOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
Write-Host 'Applying DID 1.0.14 always-maximized main window fix...'
& python (Join-Path $root 'enforce_did_maximized_114.py')
if ($LASTEXITCODE -ne 0) { throw 'The maximize patch stopped; no installer was built. Read the STOP line above.' }
if ($PatchOnly) {
    Write-Host 'Patch applied. Installer build skipped (-PatchOnly).'
    exit 0
}
$builder = Join-Path $root 'BUILD_DID_1.0.14.ps1'
if (-not (Test-Path -LiteralPath $builder)) {
    throw 'BUILD_DID_1.0.14.ps1 is missing in this folder. The patch was applied; rerun with your existing 1.0.14 build script.'
}
Write-Host 'Building DID 1.0.14 with the existing installer workflow...'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $builder
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed. Check DID_1.0.14_build.log for the exact cause.' }
Write-Host 'Build complete. Check installer_output\DID_Character_Sheet_Setup_1.0.14.exe'
