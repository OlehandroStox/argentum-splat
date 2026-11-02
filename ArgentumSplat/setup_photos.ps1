param([string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\photos-runtime'))
$ErrorActionPreference = 'Stop'
$photosMutex = [System.Threading.Mutex]::new($false, 'Local\ArgentumSplatPhotosSetup')
$locked = $false
try {
    try { $locked = $photosMutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Photos setup is already running.' }
    . (Join-Path $PSScriptRoot 'setup_python.ps1')
    $photosPython = Ensure-ArgentumPython -RuntimeDir $RuntimeDir
    & $photosPython -m pip install --only-binary=:all: 'pycolmap==4.2.1' 'numpy==2.2.6' 'Pillow==11.3.0' --timeout 60 --retries 3
    if ($LASTEXITCODE -ne 0) { throw 'Photos package installation failed.' }
    & $photosPython (Join-Path $PSScriptRoot 'backend\setup_photos.py') --runtime-dir $RuntimeDir
    if ($LASTEXITCODE -ne 0) { throw 'Photos runtime verification failed.' }
} finally {
    if ($locked) { $photosMutex.ReleaseMutex() }
    $photosMutex.Dispose()
}
