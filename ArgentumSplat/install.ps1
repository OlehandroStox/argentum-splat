param([string]$PreferencesFolder = "")
$ErrorActionPreference = 'Stop'
if (-not $PreferencesFolder) {
    $candidates = @(Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'Maxon') -Directory |
        Where-Object { $_.Name -like 'Maxon Cinema 4D 2027_*' })
    if ($candidates.Count -ne 1) {
        throw 'Specify -PreferencesFolder with your Cinema 4D 2027 preferences folder.'
    }
    $PreferencesFolder = $candidates[0].FullName
}
$prefs = [IO.Path]::GetFullPath($PreferencesFolder)
if (-not (Test-Path -LiteralPath $prefs -PathType Container)) { throw 'Preferences folder does not exist.' }
$pluginParent = Join-Path $prefs 'plugins'
New-Item -ItemType Directory -Path $pluginParent -Force | Out-Null
$destination = [IO.Path]::GetFullPath((Join-Path $pluginParent 'ArgentumSplat'))
$sourceDirectory = [IO.Path]::GetFullPath($PSScriptRoot)
if ($destination.TrimEnd('\').Equals($sourceDirectory.TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase)) {
    Write-Host 'This copy is already in the Cinema 4D plugin folder. Restart Cinema 4D to load it.'
    exit 0
}
if (-not $destination.StartsWith($pluginParent + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Unsafe destination.'
}
if (Test-Path -LiteralPath $destination) {
    $backupRoot = Join-Path $prefs 'ArgentumSplat-backups'
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $backup = [IO.Path]::GetFullPath((Join-Path $backupRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')))
    if (-not $backup.StartsWith($backupRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unsafe backup destination.'
    }
    Move-Item -LiteralPath $destination -Destination $backup
}
New-Item -ItemType Directory -Path $destination | Out-Null
foreach ($item in Get-ChildItem -LiteralPath $PSScriptRoot -Force) {
    if ($item.Name -notin @('__pycache__','.venv')) {
        Copy-Item -LiteralPath $item.FullName -Destination $destination -Recurse
    }
}
Write-Host ('Installed: ' + $destination)
Write-Host 'Restart Cinema 4D, then choose Extensions > ArgentumSplat > Argentum Splat.'
