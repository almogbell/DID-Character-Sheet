# DID Character Sheet 1.0.14 - verify audited sources, build Windows installer.
# Does NOT install, uninstall, publish, or modify cloud data.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
function Require-File([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required source file not found: $path" }
}
function Invoke-DidPython {
    param([string[]]$Arguments)
    $log = Join-Path $root 'DID_1.0.14_build.log'
    Add-Content -LiteralPath $log -Value ("`n== " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " == python " + ($Arguments -join ' '))
    # Native stderr is captured as text; always preserve Python's STOP line.
    $previousErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & python @Arguments 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            Add-Content -LiteralPath $log -Value $line
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    if ($code -ne 0) {
        throw "Python failed ($code): $($Arguments -join ' '). Read DID_1.0.14_build.log for the first STOP: line. No installer was built."
    }
}

Write-Host 'DID Character Sheet 1.0.14 - verify and package current sources' -ForegroundColor Cyan
Write-Host 'This only builds a Windows installer; nothing will be installed or published.'
Write-Host "Build log: $(Join-Path $root 'DID_1.0.14_build.log')"
Push-Location $root
try {
    Require-File (Join-Path $root 'campaign_role_ui.py')
    Require-File (Join-Path $root 'DID_Character_Sheet.spec')
    Require-File (Join-Path $root 'DID_Character_Sheet_Installer_with_icon.iss')
    Require-File (Join-Path $root 'frontend_2_8.py')
    Require-File (Join-Path $root 'party_dashboard\app.js')
    Require-File (Join-Path $root 'party_dashboard\index.html')
    Require-File (Join-Path $root 'suggestions_config.json')
    Require-File (Join-Path $root 'app_icon.ico')
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found on PATH.' }

    # IMPORTANT: do not rerun historical patch scripts here: doing so could
    # overwrite later corrections made to campaign sync and pairing.
    Write-Host 'Building the current checked-in code without rewriting sources...'
    Write-Host 'Checking Python sources...'
    Invoke-DidPython -Arguments @('-m', 'py_compile', 'campaign_role_ui.py', 'campaign_runtime.py', 'campaign_roll_outbox.py', 'mobile_companion_dialog.py', 'campaign_player_reveals.py', 'backend_2_1.py', 'frontend_2_8.py')
    Invoke-DidPython -Arguments @('-m', 'unittest', 'discover', '-s', 'DID_Important_Tests', '-p', 'test_1_0_14*.py', '-v')
    Invoke-DidPython -Arguments @('-m', 'unittest', 'discover', '-s', 'DID_Important_Tests', '-p', 'test_campaign_roll_outbox.py', '-v')
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        & node --check '.\party_dashboard\app.js'
        if ($LASTEXITCODE -ne 0) { throw 'Party Dashboard JavaScript syntax check failed.' }
    } else {
        Write-Warning 'Node.js not installed. JavaScript syntax was statically tested only.'
    }

    $iss = Get-Content -LiteralPath '.\DID_Character_Sheet_Installer_with_icon.iss' -Raw
    if ($iss -notmatch '(?m)^#define MyAppVersion "1\.0\.14"\s*$') {
        throw 'Installer version does not match 1.0.14.'
    }
    if (-not $iss.Contains('AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}')) {
        throw 'Stable AppId changed; refusing incompatible upgrade.'
    }

    Write-Host 'Building Windows executable...'
    $started = Get-Date
    Invoke-DidPython -Arguments @('-m', 'PyInstaller', '--clean', '--noconfirm', 'DID_Character_Sheet.spec')
    $exe = Join-Path $root 'dist\DID Character Sheet.exe'
    Require-File $exe
    if ((Get-Item $exe).LastWriteTime -lt $started.AddSeconds(-5)) { throw 'EXE was not rebuilt.' }
    $stream = [System.IO.File]::OpenRead($exe)
    try {
        if ($stream.Length -lt 1048576 -or $stream.ReadByte() -ne 77 -or $stream.ReadByte() -ne 90) {
            throw 'The rebuilt file is not a valid-sized Windows executable.'
        }
    } finally { $stream.Dispose() }

    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue)
    $compiler = if ($iscc) { $iscc.Source } else { $null }
    if (-not $compiler) {
        $candidates = @()
        foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA)) {
            if ($base) {
                $candidates += (Join-Path $base 'Inno Setup 6\ISCC.exe')
                $candidates += (Join-Path $base 'Inno Setup 7\ISCC.exe')
                $candidates += (Join-Path $base 'Programs\Inno Setup 6\ISCC.exe')
                $candidates += (Join-Path $base 'Programs\Inno Setup 7\ISCC.exe')
            }
        }
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $compiler = $candidate; break }
        }
    }
    if (-not $compiler) { throw 'Inno Setup ISCC.exe not found. Install Inno Setup and run again.' }
    $output = Join-Path $root 'installer_output\DID_Character_Sheet_Setup_1.0.14.exe'
    if (Test-Path -LiteralPath $output -PathType Leaf) {
        $backup = Join-Path $root ('installer_output\DID_Character_Sheet_Setup_1.0.14.previous_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.exe')
        Copy-Item -LiteralPath $output -Destination $backup
    }
    Write-Host "Packaging with Inno Setup: $compiler"
    & $compiler '.\DID_Character_Sheet_Installer_with_icon.iss'
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
    Require-File $output
    $built = Get-Item $output
    if ($built.Length -lt 1048576 -or $built.LastWriteTime -lt $started.AddSeconds(-5)) {
        throw 'Installer seems stale or incomplete.'
    }
    Write-Host ''
    Write-Host 'SUCCESS - DID CHARACTER SHEET 1.0.14 INSTALLER READY' -ForegroundColor Green
    Write-Host "Output: $output"
    Write-Host "SHA256: $((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)"
    Write-Host 'Next: Test the upgrade and DM/Player visibility with two accounts before release.'
} finally { Pop-Location }
