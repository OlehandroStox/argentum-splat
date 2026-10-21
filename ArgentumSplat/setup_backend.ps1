param(
    [string]$PythonExe = "",
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\runtime')
)
$ErrorActionPreference = 'Stop'
$setupMutex = [System.Threading.Mutex]::new($false, 'Local\ArgentumSplatBackendSetup')
$lockAcquired = $false
try {
    try { $lockAcquired = $setupMutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $lockAcquired = $true }
    if (-not $lockAcquired) { throw 'Argentum Splat backend setup is already running.' }
$backendDir = Join-Path $PSScriptRoot 'backend'
$RuntimeDir = [System.IO.Path]::GetFullPath($RuntimeDir)
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
$venvDir = Join-Path $RuntimeDir '.venv'
$runtimePython = Join-Path $venvDir 'Scripts\python.exe'

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE : $Executable"
    }
}

if (-not (Test-Path -LiteralPath $runtimePython)) {
    if (-not $PythonExe) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            foreach ($version in @('3.12', '3.11', '3.10')) {
                $previousErrorPreference = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                $candidate = & $launcher.Source "-$version" -c 'import sys; print(sys.executable)' 2>$null
                $candidateExitCode = $LASTEXITCODE
                $ErrorActionPreference = $previousErrorPreference
                if ($candidateExitCode -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate)) {
                    $PythonExe = $candidate
                    break
                }
            }
        }
    }
    if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
        throw 'Python 3.10, 3.11 or 3.12 is required. Install Python and rerun, or pass -PythonExe.'
    }
    Invoke-Checked $PythonExe @('-c', 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), "Python 3.10-3.12 required"')
    Invoke-Checked $PythonExe @('-m', 'venv', $venvDir)
}
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
Invoke-Checked $runtimePython @('-m', 'pip', 'install', '--upgrade', 'pip')
$wheelCache = Join-Path $RuntimeDir 'wheel-cache'
Invoke-Checked $runtimePython @((Join-Path $backendDir 'download_torch.py'), '--cache-dir', $wheelCache)
$pythonTag = & $runtimePython -c 'import sys; print("cp%d%d" % sys.version_info[:2])'
$torchWheel = Join-Path $wheelCache "torch-2.9.1+cu128-$pythonTag-$pythonTag-win_amd64.whl"
Invoke-Checked $runtimePython @('-m', 'pip', 'install', $torchWheel, 'torchvision==0.24.1', '--index-url', 'https://download.pytorch.org/whl/cu128')
Invoke-Checked $runtimePython @('-m', 'pip', 'install', '-r', (Join-Path $backendDir 'requirements.txt'))
Invoke-Checked $runtimePython @((Join-Path $backendDir 'bootstrap.py'), '--runtime-dir', $RuntimeDir)
Write-Host 'Argentum Splat backend is ready.'
Write-Host (Join-Path $RuntimeDir 'runtime.json')
}
finally {
    if ($lockAcquired) { $setupMutex.ReleaseMutex() }
    $setupMutex.Dispose()
}
