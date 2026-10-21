param(
    [string]$PreferencesFolder = '',
    [switch]$CoreOnly,
    [switch]$ImportOnly,
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\runtime'),
    [string]$FormatsRoot = (Join-Path $env:LOCALAPPDATA 'ArgentumSplat\formats')
)
$ErrorActionPreference = 'Stop'
$logRoot = Join-Path $env:LOCALAPPDATA 'ArgentumSplat\installer\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot ((Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.log')
$transcribing = $false
$mutex = [Threading.Mutex]::new($false, 'Local\ArgentumSplatPluginInstall')
$locked = $false
try {
    Start-Transcript -Path $logPath | Out-Null
    $transcribing = $true
    try { $locked = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another Argentum Splat installer is running.' }
    Write-Host 'Argentum Splat - automatic installation' -ForegroundColor Cyan
    Write-Host 'Close Cinema 4D before updating. Initial AI downloads need internet, several GB and an NVIDIA Ampere-or-newer GPU.'
    Write-Host ('Log: ' + $logPath)
    if (-not $PreferencesFolder) {
        $maxonRoot = Join-Path $env:APPDATA 'Maxon'
        $candidates = @()
        if (Test-Path -LiteralPath $maxonRoot) {
            $candidates = @(Get-ChildItem -LiteralPath $maxonRoot -Directory |
                Where-Object { $_.Name -like 'Maxon Cinema 4D 2027_*' } | Sort-Object Name)
        }
        if ($candidates.Count -eq 0) {
            throw 'Cinema 4D 2027 preferences were not found. Launch C4D 2027 once, close it and rerun Install.cmd. For a custom folder use Install.ps1 -PreferencesFolder <path>.'
        }
        if ($candidates.Count -eq 1) { $PreferencesFolder = $candidates[0].FullName }
        else {
            Write-Host 'Choose the Cinema 4D preferences folder to install into:'
            for ($i = 0; $i -lt $candidates.Count; $i++) { Write-Host ("{0}: {1}" -f ($i + 1), $candidates[$i].FullName) }
            $choice = 0
            $answer = Read-Host 'Folder number'
            if (-not [int]::TryParse($answer, [ref]$choice) -or $choice -lt 1 -or $choice -gt $candidates.Count) { throw 'No valid folder selected. Rerun Install.cmd to select one.' }
            $PreferencesFolder = $candidates[$choice - 1].FullName
        }
    }
    $prefs = [IO.Path]::GetFullPath($PreferencesFolder).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $prefs -PathType Container)) { throw 'Preferences folder does not exist.' }
    function Assert-PreferencesChild([string]$Path) {
        $full = [IO.Path]::GetFullPath($Path)
        if (-not $full.StartsWith($prefs + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe installation path.' }
        $cursor = $full
        while ($cursor.StartsWith($prefs + '\', [StringComparison]::OrdinalIgnoreCase)) {
            if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ('Refusing to replace a linked folder: ' + $cursor) }
            $cursor = Split-Path -Parent $cursor
        }
        return $full
    }
    $pluginParent = Assert-PreferencesChild (Join-Path $prefs 'plugins')
    New-Item -ItemType Directory -Path $pluginParent -Force | Out-Null
    $destination = Assert-PreferencesChild (Join-Path $pluginParent 'ArgentumSplat')
    $sourceDirectory = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not $destination.Equals($sourceDirectory, [StringComparison]::OrdinalIgnoreCase)) {
        # Prepare the complete replacement outside the C4D plugin search folder.
        $stage = Assert-PreferencesChild (Join-Path $prefs ('ArgentumSplat-installing-' + [Guid]::NewGuid().ToString('N')))
        New-Item -ItemType Directory -Path $stage | Out-Null
        foreach ($item in Get-ChildItem -LiteralPath $sourceDirectory -Force) {
            if ($item.Name -notin @('__pycache__', '.venv') -and $item.Extension -ne '.log') {
                Copy-Item -LiteralPath $item.FullName -Destination $stage -Recurse
            }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $stage 'ArgentumSplat.pyp'))) { throw 'Incomplete plugin archive. Re-extract the entire release ZIP.' }
        $backup = $null
        if (Test-Path -LiteralPath $destination) {
            $backupRoot = Assert-PreferencesChild (Join-Path $prefs 'ArgentumSplat-backups')
            New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
            $backup = Assert-PreferencesChild (Join-Path $backupRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
            Move-Item -LiteralPath $destination -Destination $backup
            Write-Host ('Previous plugin preserved: ' + $backup)
        }
        try { Move-Item -LiteralPath $stage -Destination $destination }
        catch {
            if ($backup -and -not (Test-Path -LiteralPath $destination)) { Move-Item -LiteralPath $backup -Destination $destination }
            throw
        }
    }
    Write-Host ('Plugin installed: ' + $destination) -ForegroundColor Green
    if (-not $CoreOnly) {
        try {
            & (Join-Path $destination 'setup_all.ps1') -RuntimeDir $RuntimeDir -FormatsRoot $FormatsRoot -ImportOnly:$ImportOnly
        } catch {
            Write-Host 'The plugin remains installed. Native PLY/SPLAT/SPZ import is available. Read the failed component above and rerun Install.cmd to retry.' -ForegroundColor Yellow
            throw
        }
    }
    Write-Host 'Installation complete. Restart Cinema 4D: Extensions > ArgentumSplat > Argentum Splat.' -ForegroundColor Green
} catch {
    Write-Host ('SETUP NEEDS ATTENTION: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Full log: ' + $logPath)
    throw
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
    if ($transcribing) { Stop-Transcript | Out-Null }
}
