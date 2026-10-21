param(
    [string]$PythonExe = "",
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\runtime'),
    [switch]$Repair
)
$ErrorActionPreference = 'Stop'
Write-Host 'Optional runtimes/models retain their own licenses (including DINOv3 for AI). MIT covers the integration only.'
Write-Host ('License details before downloads: ' + (Join-Path $PSScriptRoot 'LICENSE_SCOPE.md'))
$setupMutex = [System.Threading.Mutex]::new($false, 'Local\ArgentumSplatBackendSetup')
$lockAcquired = $false
try {
    try { $lockAcquired = $setupMutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $lockAcquired = $true }
    if (-not $lockAcquired) { throw 'Argentum Splat backend setup is already running.' }
    $backendDir = Join-Path $PSScriptRoot 'backend'
    $RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    . (Join-Path $PSScriptRoot 'setup_python.ps1')
    $runtimePython = Ensure-ArgentumPython -RuntimeDir $RuntimeDir -PythonExe $PythonExe

    function Invoke-Checked {
        param([string]$Executable, [string[]]$Arguments)
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE : $Executable" }
    }
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    if (-not $Repair) {
        & $runtimePython (Join-Path $backendDir 'runtime_check.py') --runtime-dir $RuntimeDir
        if ($LASTEXITCODE -eq 0) {
            Write-Host 'AI runtime is already ready. No packages or models need downloading.'
            return
        }
    }
    Write-Host '[AI 1/4] Checking the NVIDIA GPU before large downloads...'
    $gpuResult = (& $runtimePython (Join-Path $backendDir 'runtime_check.py') --preflight | Out-String).Trim()
    $gpuExit = $LASTEXITCODE
    Write-Host $gpuResult
    if ($gpuExit -ne 0) {
        $gpuMessage = 'NVIDIA GPU preflight failed. Read the setup log.'
        try { $gpuMessage = ($gpuResult | ConvertFrom-Json).message } catch { }
        throw $gpuMessage
    }
    Write-Host '[AI 2/4] Installing Python packages in the private environment...'
    Invoke-Checked $runtimePython @('-m', 'pip', 'install', '--upgrade', 'pip', '--timeout', '60', '--retries', '3')
    $wheelCache = Join-Path $RuntimeDir 'wheel-cache'
    Invoke-Checked $runtimePython @((Join-Path $backendDir 'download_torch.py'), '--cache-dir', $wheelCache)
    $pythonTag = (& $runtimePython -c 'import sys; print(''cp%d%d'' % sys.version_info[:2])' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $pythonTag -notmatch '^cp3(10|11|12)$') { throw 'Unsupported runtime Python.' }
    $torchWheel = Join-Path $wheelCache "torch-2.9.1+cu128-$pythonTag-$pythonTag-win_amd64.whl"
    Invoke-Checked $runtimePython @('-m', 'pip', 'install', $torchWheel, 'torchvision==0.24.1', '--index-url', 'https://download.pytorch.org/whl/cu128', '--timeout', '60', '--retries', '3')
    Invoke-Checked $runtimePython @('-m', 'pip', 'install', '-r', (Join-Path $backendDir 'requirements.txt'), '--timeout', '60', '--retries', '3')
    Write-Host '[AI 3/4] Downloading and verifying model weights (several GB)...'
    Invoke-Checked $runtimePython @((Join-Path $backendDir 'bootstrap.py'), '--runtime-dir', $RuntimeDir)
    Write-Host '[AI 4/4] Verifying the installed environment...'
    Invoke-Checked $runtimePython @((Join-Path $backendDir 'runtime_check.py'), '--runtime-dir', $RuntimeDir)
    Write-Host 'Argentum Splat AI is ready.'
}
finally {
    if ($lockAcquired) { $setupMutex.ReleaseMutex() }
    $setupMutex.Dispose()
}
