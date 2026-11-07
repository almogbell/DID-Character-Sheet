# DID Character Sheet 1.0.14 - Player Campaign UI polish and Windows installer builder.
# No installation, publication, cloud/database mutation, or removal of local characters.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    Write-Host 'DID Character Sheet v1.0.14 - Player UI Polish and Installer' -ForegroundColor Cyan
    Write-Host 'This builder does NOT rerun any earlier 1.0.14 source patchers.'
    foreach ($rel in @('patch_did114_player_polish.py','campaign_role_ui.py','party_dashboard\app.js',
                      'dm_dashboard\app.js','DID_Character_Sheet.spec','DID_Character_Sheet_Installer_with_icon.iss')) {
        if (-not (Test-Path -LiteralPath $rel -PathType Leaf)) { throw "Missing required file: $rel" }
    }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found on PATH.' }

    $log = Join-Path $root 'DID_114_player_polish_build.log'
    Set-Content -LiteralPath $log -Value ("DID 1.0.14 player polish: " + (Get-Date -Format 'u'))
    function RunPython([string]$label,[string]$arguments) {
        Write-Host "`n$label" -ForegroundColor Cyan
        Add-Content -LiteralPath $log -Value "`n== $label =="
        # cmd handles stderr redirection without PowerShell 5.1 turning each unittest
        # progress line into NativeCommandError.
        & cmd.exe /d /s /c "python $arguments >> DID_114_player_polish_build.log 2>&1"
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Write-Host 'Last diagnostic lines:' -ForegroundColor Yellow
            Get-Content -LiteralPath $log -Tail 70 | ForEach-Object { Write-Host $_ }
            throw "$label failed (exit $code). Read DID_114_player_polish_build.log. No installer built."
        }
        Get-Content -LiteralPath $log -Tail 6 | ForEach-Object { Write-Host $_ }
    }

    RunPython 'Applying guarded player-campaign UI polish (backups included)...' '.\patch_did114_player_polish.py'
    RunPython 'Checking Python syntax...' '-m py_compile campaign_role_ui.py patch_did114_player_polish.py'
    RunPython 'Running the full 1.0.14 regression suite...' '-m unittest discover -s DID_Important_Tests -p test_1_0_14*.py -v'

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        & node --check '.\party_dashboard\app.js'
        if ($LASTEXITCODE -ne 0) { throw 'Party Dashboard JavaScript has a syntax error.' }
        & node --check '.\dm_dashboard\app.js'
        if ($LASTEXITCODE -ne 0) { throw 'DM Dashboard JavaScript has a syntax error.' }
    } else {
        Write-Warning 'Node.js not found. JavaScript syntax checks were not run on Windows.'
    }

    $iss = Get-Content -LiteralPath '.\DID_Character_Sheet_Installer_with_icon.iss' -Raw
    if ($iss -notmatch '(?m)^#define MyAppVersion "1\.0\.14"\s*$') {
        throw 'Installer definition is not 1.0.14; refusing an incorrectly labelled installer.'
    }
    if (-not $iss.Contains('AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}')) {
        throw 'Installer AppId does not match existing DID Character Sheet installation.'
    }
    $buildStarted = Get-Date
    RunPython 'Building the Windows EXE with PyInstaller...' '-m PyInstaller --clean --noconfirm DID_Character_Sheet.spec'
    $exe = Join-Path $root 'dist\DID Character Sheet.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "PyInstaller output missing: $exe" }
    $app = Get-Item -LiteralPath $exe
    if ($app.Length -lt 1048576 -or $app.LastWriteTime -lt $buildStarted.AddSeconds(-5)) {
        throw 'Windows EXE appears stale or incomplete; no installer built.'
    }

    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue)
    $compiler = if ($iscc) { $iscc.Source } else { $null }
    if (-not $compiler) {
        foreach ($base in @(${env:ProgramFiles(x86)},$env:ProgramFiles,$env:LOCALAPPDATA)) {
            if (-not $base) { continue }
            foreach ($dir in @('Inno Setup 6','Inno Setup 7','Programs\Inno Setup 6','Programs\Inno Setup 7')) {
                $candidate=Join-Path (Join-Path $base $dir) 'ISCC.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $compiler=$candidate; break }
            }
            if ($compiler) { break }
        }
    }
    if (-not $compiler) { throw 'ISCC.exe was not found. Install Inno Setup 6 or 7.' }

    $outDir=Join-Path $root 'installer_output'
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    $installer=Join-Path $outDir 'DID_Character_Sheet_Setup_1.0.14.exe'
    if (Test-Path -LiteralPath $installer -PathType Leaf) {
        $copy=Join-Path $outDir ('DID_Character_Sheet_Setup_1.0.14.previous_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.exe')
        Copy-Item -LiteralPath $installer -Destination $copy
    }
    Write-Host 'Packaging installer with Inno Setup...' -ForegroundColor Cyan
    & $compiler '.\DID_Character_Sheet_Installer_with_icon.iss'
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw "Installer missing: $installer" }
    $file=Get-Item -LiteralPath $installer
    if ($file.Length -lt 1048576 -or $file.LastWriteTime -lt $buildStarted.AddSeconds(-5)) {
        throw 'Inno Setup output appears stale or incomplete.'
    }
    Write-Host "`nSUCCESS: $installer" -ForegroundColor Green
    Write-Host "SHA256: $((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash)"
    Write-Host 'Verify the new inline details, checkbox sizing, and character double-click before publishing.'
} finally {
    Pop-Location
}
