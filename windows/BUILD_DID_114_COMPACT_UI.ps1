# DID Character Sheet v1.0.14: compact campaign toolbar + loading notice installer.
# Requires Python/PyInstaller, Node.js for JS validation when available, and Inno Setup 6/7.
# Does not rerun earlier 1.0.14 patch scripts, alter Supabase, or publish releases.
#Requires -Version 5.1
param([switch]$PatchOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  Write-Host 'DID Character Sheet 1.0.14 - compact Campaigns toolbar and loading notice' -ForegroundColor Cyan
  foreach ($required in @('patch_did114_toolbar_loading.py','repair_did114_toolbar_tests.py','test_did114_toolbar_loading.py',
                          'campaign_role_ui.py','ui_feedback.py','DID_Character_Sheet.spec',
                          'DID_Character_Sheet_Installer_with_icon.iss')) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing file: $required" }
  }
  $log = Join-Path $root 'DID_114_compact_ui_build.log'
  Set-Content -LiteralPath $log -Encoding UTF8 -Value "DID 1.0.14 compact UI: $(Get-Date -Format u)"
  # Get-Command can return several executables. Start-Process needs exactly one string path.
  # Probe candidates so Windows' python.exe App Execution Alias cannot be selected by mistake.
  [string]$pythonExe = ''
  $pythonCandidates = @(Get-Command -Name python -All -CommandType Application -ErrorAction SilentlyContinue)
  foreach ($candidate in $pythonCandidates) {
    [string]$candidatePath = $candidate.Source
    if ([string]::IsNullOrWhiteSpace($candidatePath)) { continue }
    try {
      $probe = @(& $candidatePath -c 'import sys; print(sys.executable)' 2>$null)
      if ($LASTEXITCODE -eq 0 -and $probe.Count -gt 0) {
        [string]$resolvedPath = [string]$probe[-1]
        $resolvedPath = $resolvedPath.Trim()
        if (Test-Path -LiteralPath $resolvedPath -PathType Leaf) {
          $pythonExe = $resolvedPath
        } else {
          $pythonExe = $candidatePath
        }
        break
      }
    } catch {
      # Try the next Python installation instead of failing on an App Execution Alias.
    }
  }
  if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    throw 'Cannot find a working Python executable. Run python --version in PowerShell.'
  }
  Write-Host "Using Python: $pythonExe" -ForegroundColor DarkGray
  Add-Content -LiteralPath $log -Encoding UTF8 -Value "Using Python: $pythonExe"
  $env:PYTHONIOENCODING = 'utf-8'
  # A native process without cmd.exe keeps output observable and avoids shell redirection stalls.
  function RunPython([string]$label, [string]$arguments, [int]$timeoutSeconds = 0) {
    Write-Host "`n== $label ==" -ForegroundColor Cyan
    Add-Content -LiteralPath $log -Encoding UTF8 -Value "`n== $label =="
    $stdoutPath = Join-Path $root 'DID_114_last_step_stdout.txt'
    $stderrPath = Join-Path $root 'DID_114_last_step_stderr.txt'
    foreach ($file in @($stdoutPath, $stderrPath)) {
      if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
    $begin = Get-Date
    try {
      $proc = Start-Process -FilePath ([string]$pythonExe) -ArgumentList ("-u " + $arguments) `
        -WorkingDirectory $root -NoNewWindow -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    } catch {
      throw "Cannot start Python: $($_.Exception.Message)"
    }
    $lastProgress = 0
    $timedOut = $false
    while ($true) {
      $proc.Refresh()
      if ($proc.HasExited) { break }
      Start-Sleep -Milliseconds 500
      $elapsed = [int]((Get-Date) - $begin).TotalSeconds
      if ($timeoutSeconds -gt 0 -and $elapsed -ge $timeoutSeconds) {
        $timedOut = $true
        try { $proc.Kill(); $proc.WaitForExit(2000) | Out-Null } catch { }
        break
      }
      if ($elapsed -ge $lastProgress + 8) {
        $lastProgress = $elapsed
        Write-Host "Running $label ($elapsed seconds)..." -ForegroundColor DarkGray
        $lastError = @(Get-Content -LiteralPath $stderrPath -Tail 2 -ErrorAction SilentlyContinue)
        if ($lastError.Count -gt 0) { Write-Host ($lastError -join ' | ') -ForegroundColor DarkGray }
      }
    }
    $proc.Refresh()
    $output = @(Get-Content -LiteralPath $stdoutPath -ErrorAction SilentlyContinue)
    $errors = @(Get-Content -LiteralPath $stderrPath -ErrorAction SilentlyContinue)
    foreach ($line in $output) { Add-Content -LiteralPath $log -Encoding UTF8 -Value $line }
    foreach ($line in $errors) { Add-Content -LiteralPath $log -Encoding UTF8 -Value $line }
    if ($timedOut) {
      Write-Host 'Python patch did not finish within the safe time limit.' -ForegroundColor Yellow
      @($output + $errors) | Select-Object -Last 45 | ForEach-Object { Write-Host $_ }
      throw "STOP: $label timed out after $timeoutSeconds seconds. See $log. No installer built."
    }
    if ($proc.ExitCode -ne 0) {
      Write-Host "Python returned exit code $($proc.ExitCode). Diagnostic output:" -ForegroundColor Yellow
      @($output + $errors) | Select-Object -Last 60 | ForEach-Object { Write-Host $_ }
      throw "STOP: $label failed. See $log. No installer built."
    }
    @($output + $errors) | Select-Object -Last 8 | ForEach-Object { Write-Host $_ }
    Write-Host "Completed: $label" -ForegroundColor Green
  }
  RunPython 'Apply the guarded 1.0.14 UI fix (automatic source backups)' '.\patch_did114_toolbar_loading.py' 45
  if ($PatchOnly) {
    Write-Host 'PATCH-ONLY SUCCESS. Source patch finished; installer was not built.' -ForegroundColor Green
    return
  }
  RunPython 'Update superseded exact-width UI test expectations (test backups)' '.\repair_did114_toolbar_tests.py'
  RunPython 'Check changed Python files' '-m py_compile campaign_role_ui.py ui_feedback.py'
  RunPython 'Run compact toolbar and loading regression checks' '.\test_did114_toolbar_loading.py'
  RunPython 'Run the existing 1.0.14 regression suite' '-m unittest discover -s DID_Important_Tests -p test_1_0_14*.py -v'
  $node=Get-Command node -ErrorAction SilentlyContinue
  if ($node) {
    foreach ($js in @('party_dashboard\app.js','dm_dashboard\app.js')) {
      if (Test-Path -LiteralPath $js) {
        & node --check $js
        if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax error: $js" }
      }
    }
  } else { Write-Warning 'Node.js unavailable. Dashboard JS syntax checks skipped.' }
  $iss = Get-Content -LiteralPath '.\DID_Character_Sheet_Installer_with_icon.iss' -Raw
  if ($iss -notmatch '(?m)^#define MyAppVersion "1\.0\.14"\s*$') { throw 'Installer version is not 1.0.14' }
  if (-not $iss.Contains('AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}')) { throw 'Installer AppId differs from the installed DID Character Sheet' }
  $buildStart = Get-Date
  RunPython 'Build Windows app using existing PyInstaller spec' '-m PyInstaller --clean --noconfirm DID_Character_Sheet.spec'
  $exe=Join-Path $root 'dist\DID Character Sheet.exe'
  if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Missing PyInstaller output: $exe" }
  $app=Get-Item -LiteralPath $exe
  if ($app.Length -lt 1048576 -or $app.LastWriteTime -lt $buildStart.AddSeconds(-5)) { throw 'Windows exe looks stale or incomplete' }
  # Also choose a single path when more than one Inno Setup version is installed.
  $cmd=Get-Command ISCC.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  [string]$compiler=if ($cmd) { [string]$cmd.Source } else { '' }
  if (-not $compiler) {
    foreach ($base in @(${env:ProgramFiles(x86)},$env:ProgramFiles,$env:LOCALAPPDATA)) {
      if (-not $base) {continue}
      foreach ($dir in @('Inno Setup 6','Inno Setup 7','Programs\Inno Setup 6','Programs\Inno Setup 7')) {
        $candidate=Join-Path (Join-Path $base $dir) 'ISCC.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $compiler=$candidate; break }
      }
      if ($compiler) {break}
    }
  }
  if (-not $compiler) { throw 'Inno Setup ISCC.exe is not installed or cannot be located.' }
  $out=Join-Path $root 'installer_output'
  New-Item -ItemType Directory -Path $out -Force | Out-Null
  $installer=Join-Path $out 'DID_Character_Sheet_Setup_1.0.14.exe'
  if (Test-Path -LiteralPath $installer -PathType Leaf) {
    $old=Join-Path $out ('DID_Character_Sheet_Setup_1.0.14.previous_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.exe')
    Copy-Item -LiteralPath $installer -Destination $old
  }
  & $compiler '.\DID_Character_Sheet_Installer_with_icon.iss'
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit $LASTEXITCODE)" }
  if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw "Installer not created: $installer" }
  $result=Get-Item -LiteralPath $installer
  if ($result.Length -lt 1048576 -or $result.LastWriteTime -lt $buildStart.AddSeconds(-5)) { throw 'Installer is stale or incomplete' }
  Write-Host "SUCCESS: $installer" -ForegroundColor Green
  Write-Host "SHA256: $((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash)"
} finally {
  Pop-Location
}
