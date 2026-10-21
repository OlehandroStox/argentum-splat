param([Parameter(Mandatory = $true)][string]$RuntimeDir, [switch]$TestRecovery)
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'ArgentumSplat\setup_python.ps1')

function Assert-Condition([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
$beforeUserPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
$beforeMachinePath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
$firstClock = [Diagnostics.Stopwatch]::StartNew()
$first = @(Ensure-ArgentumPython -RuntimeDir $RuntimeDir)
$firstClock.Stop()
Assert-Condition ($first.Count -eq 1) 'The helper must return exactly one Python path.'
$python = $first[0]
$version = & $python -I -c 'import sys,pip,struct,ssl,venv; assert sys.prefix!=sys.base_prefix; assert struct.calcsize(''P'')==8; print(sys.version.split()[0])'
Assert-Condition ($LASTEXITCODE -eq 0) 'The new venv, pip, ssl or architecture check failed.'
$venvStamp = (Get-Item -LiteralPath (Join-Path $RuntimeDir '.venv\pyvenv.cfg')).LastWriteTimeUtc
$repeatClock = [Diagnostics.Stopwatch]::StartNew()
$repeat = @(Ensure-ArgentumPython -RuntimeDir $RuntimeDir)
$repeatClock.Stop()
Assert-Condition ($repeat.Count -eq 1 -and $repeat[0] -eq $python) 'The repeated run did not reuse its environment.'
Assert-Condition ((Get-Item -LiteralPath (Join-Path $RuntimeDir '.venv\pyvenv.cfg')).LastWriteTimeUtc -eq $venvStamp) 'Repeated setup rewrote the venv.'
Assert-Condition ([Environment]::GetEnvironmentVariable('PATH', 'User') -eq $beforeUserPath) 'User PATH changed.'
Assert-Condition ([Environment]::GetEnvironmentVariable('PATH', 'Machine') -eq $beforeMachinePath) 'Machine PATH changed.'

$recoveryRoot = $null
if ($TestRecovery) {
    $recoveryRoot = $RuntimeDir + '-recovery-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
    New-Item -ItemType Directory -Path (Join-Path $recoveryRoot 'downloads') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $recoveryRoot '.venv') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $recoveryRoot 'toolchain\cpython-3.12.15-20261020') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $recoveryRoot '.venv\incomplete.txt'), 'preserve broken venv')
    [IO.File]::WriteAllText((Join-Path $recoveryRoot 'toolchain\cpython-3.12.15-20261020\incomplete.txt'), 'preserve partial extraction')
    [IO.File]::WriteAllText((Join-Path $recoveryRoot 'downloads\cpython-3.12.15+20261020-x86_64-pc-windows-msvc-install_only.tar.gz'), 'corrupt archive')
    $recovery = @(Ensure-ArgentumPython -RuntimeDir $recoveryRoot)
    Assert-Condition ($recovery.Count -eq 1 -and (Test-Path -LiteralPath $recovery[0])) 'Recovery failed.'
    $backups = @(Get-ChildItem -LiteralPath (Join-Path $recoveryRoot 'setup-backups'))
    Assert-Condition ($backups.Count -eq 3) 'Broken venv, old extraction and corrupt download were not all preserved.'
    & $recovery[0] -I -m pip --version
    Assert-Condition ($LASTEXITCODE -eq 0) 'Recovery pip check failed.'
}
[pscustomobject]@{
    python = $python
    version = $version
    first_seconds = [Math]::Round($firstClock.Elapsed.TotalSeconds, 3)
    repeat_seconds = [Math]::Round($repeatClock.Elapsed.TotalSeconds, 3)
    repeat_kept_venv = $true
    path_unchanged = $true
    recovery_root = $recoveryRoot
    passed = $true
} | ConvertTo-Json
