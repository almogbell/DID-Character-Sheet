# DID Character Sheet 1.0.13 - Windows installer build helper.
# This script BUILDS ONLY. It does not install/uninstall anything or modify user data.
#requires -Version 5.1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$issPath = Join-Path $root 'DID_Character_Sheet_Installer_with_icon.iss'
$exePath = Join-Path $root 'dist\DID Character Sheet.exe'
$configPath = Join-Path $root 'suggestions_config.json'
$iconPath = Join-Path $root 'app_icon.ico'
$outputPath = Join-Path $root 'installer_output\DID_Character_Sheet_Setup_1.0.13.exe'

function Require-File([string] $path, [string] $description) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "$description is missing: $path"
    }
}

Require-File $issPath 'Inno Setup script'
Require-File $exePath 'Packaged Windows EXE (build with PyInstaller first)'
Require-File $configPath 'Public Supabase configuration required by existing installer'
Require-File $iconPath 'Installer icon'

$iss = Get-Content -LiteralPath $issPath -Raw
if ($iss -notmatch '(?m)^\s*#define\s+MyAppVersion\s+"1\.0\.13"\s*$') {
    throw 'Installer .iss version is not 1.0.13. Stop to avoid building an incorrectly versioned upgrade.'
}
if (-not $iss.Contains('AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}')) {
    throw 'Existing AppId is missing or changed. Do not overwrite a currently installed application.'
}
if ($iss -notmatch '(?m)^\s*UsePreviousAppDir\s*=\s*yes\s*$') {
    throw 'UsePreviousAppDir=yes is missing. Review the upgrade path before building.'
}
if (-not $iss.Contains('Source: "dist\DID Character Sheet.exe"')) {
    throw 'The installer script does not reference the expected EXE.'
}

# A fast sanity check catches accidentally copied text files / incomplete EXEs.
$stream = [System.IO.File]::OpenRead($exePath)
try {
    if ($stream.Length -lt 1024 * 1024) {
        throw 'The packaged EXE is unexpectedly small; rebuild it before packaging.'
    }
    $b0 = $stream.ReadByte()
    $b1 = $stream.ReadByte()
    if ($b0 -ne 77 -or $b1 -ne 90) {
        throw 'The packaged file does not have a Windows PE (MZ) signature.'
    }
} finally {
    $stream.Dispose()
}

# Support Inno Setup 6 or 7, both PATH and standard installation directories.
$iscc = $null
$onPath = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
if ($onPath) { $iscc = $onPath.Source }
if (-not $iscc) {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe')
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $iscc = $candidate
            break
        }
    }
}
if (-not $iscc) {
    throw 'Inno Setup compiler (ISCC.exe) not found. Install Inno Setup from https://jrsoftware.org/isinfo.php and rerun this script.'
}

Write-Host 'Validated: version 1.0.13, unchanged AppId, packaged EXE, installer resources.'
Write-Host "Using Inno Setup compiler: $iscc"
Write-Host 'Building installer only (no existing installation will be changed)...'
Push-Location $root
try {
    & $iscc $issPath
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Require-File $outputPath 'Compiled installer'
$file = Get-Item -LiteralPath $outputPath
if ($file.Length -lt 1024 * 1024) {
    throw 'Installer output is unexpectedly small; do not install it.'
}
$hash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash
Write-Host ''
Write-Host 'INSTALLER BUILD COMPLETED. NOT INSTALLED OR PUBLISHED.' -ForegroundColor Green
Write-Host "Installer: $outputPath"
Write-Host "Size: $([math]::Round($file.Length / 1MB, 2)) MB"
Write-Host "SHA256: $hash"
Write-Host 'Next: back up user data, test the installer upgrade from 1.0.12, and verify the dashboards.'
