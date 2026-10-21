param(
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\runtime'),
    [string]$FormatsRoot = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\formats'),
    [switch]$ImportOnly,
    [switch]$Repair,
    [string]$RunId = ([Guid]::NewGuid().ToString('N'))
)
$ErrorActionPreference = 'Stop'
$mutex = [Threading.Mutex]::new($false, 'Local\ArgentumSplatCompleteSetup')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Argentum Splat setup is already running. Wait for it to finish.' }
    $RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    $result = [ordered]@{ schema_version = 1; run_id = $RunId; formats = 'pending'; ai = 'pending'; errors = @(); completed_at = $null }
    $pending = Join-Path $RuntimeDir 'setup-result.pending.json'
    [IO.File]::WriteAllText($pending, ($result | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $pending -Destination (Join-Path $RuntimeDir 'setup-result.json') -Force
    Write-Host '[1/2] Preparing SCAN format support...'
    try {
        & (Join-Path $PSScriptRoot 'setup_formats.ps1') -RuntimeRoot $FormatsRoot -Repair:$Repair
        $result.formats = 'ready'
    } catch {
        $result.formats = 'failed'
        $result.errors += ('Extra formats: ' + $_.Exception.Message)
        Write-Host $result.errors[-1] -ForegroundColor Yellow
    }
    if ($ImportOnly) { $result.ai = 'skipped' }
    else {
        Write-Host '[2/2] Preparing local Image to 3D (Python + CUDA packages + models)...'
        try {
            & (Join-Path $PSScriptRoot 'setup_backend.ps1') -RuntimeDir $RuntimeDir -Repair:$Repair
            $result.ai = 'ready'
        } catch {
            $result.ai = 'failed'
            $result.errors += ('Local AI: ' + $_.Exception.Message)
            Write-Host $result.errors[-1] -ForegroundColor Yellow
        }
    }
    $result.completed_at = [DateTime]::UtcNow.ToString('o')
    $pending = Join-Path $RuntimeDir 'setup-result.pending.json'
    [IO.File]::WriteAllText($pending, ($result | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $pending -Destination (Join-Path $RuntimeDir 'setup-result.json') -Force
    if ($result.errors.Count) {
        throw ('Setup partly completed. SCAN formats: ' + $result.formats + '; AI: ' + $result.ai + '. ' + ($result.errors -join ' | '))
    }
    Write-Host ('Ready. SCAN formats: ' + $result.formats + '; AI: ' + $result.ai + '.') -ForegroundColor Green
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
