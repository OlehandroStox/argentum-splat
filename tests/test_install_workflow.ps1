param([Parameter(Mandatory = $true)][string]$TestRoot)
$ErrorActionPreference = 'Stop'
$TestRoot = [IO.Path]::GetFullPath($TestRoot)
if (Test-Path -LiteralPath $TestRoot) { throw 'Use a new TestRoot to preserve prior evidence.' }
New-Item -ItemType Directory -Path $TestRoot | Out-Null
$plugin = Join-Path (Split-Path -Parent $PSScriptRoot) 'ArgentumSplat'
$testSource = Join-Path $TestRoot 'source'
New-Item -ItemType Directory -Path $testSource | Out-Null
Copy-Item -LiteralPath (Join-Path $plugin 'setup_all.ps1') -Destination $testSource
Copy-Item -LiteralPath (Join-Path $plugin 'Install.ps1') -Destination $testSource
[IO.File]::WriteAllText((Join-Path $testSource 'ArgentumSplat.pyp'), '# installer fixture')
$runtime = Join-Path $TestRoot 'runtime'
$formats = Join-Path $TestRoot 'formats'
$prefs = Join-Path $TestRoot 'preferences'
New-Item -ItemType Directory -Path $prefs | Out-Null

# A converter failure must not prevent AI setup or claim that all is ready.
[IO.File]::WriteAllText((Join-Path $testSource 'setup_formats.ps1'), "param(`$RuntimeRoot, [switch]`$Repair); throw 'simulated offline converter'")
[IO.File]::WriteAllText((Join-Path $testSource 'setup_backend.ps1'), "param(`$RuntimeDir, [switch]`$Repair); Write-Host 'AI fixture ready'")
$install = Join-Path $testSource 'Install.ps1'
$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $install, '-PreferencesFolder', $prefs, '-RuntimeDir', $runtime, '-FormatsRoot', $formats)
$old = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& powershell.exe @arguments *> (Join-Path $TestRoot 'partial.log')
$partialCode = $LASTEXITCODE
$ErrorActionPreference = $old
if ($partialCode -eq 0) { throw 'Partial setup incorrectly returned success.' }
$partial = Get-Content -LiteralPath (Join-Path $runtime 'setup-result.json') -Raw | ConvertFrom-Json
if ($partial.formats -ne 'failed' -or $partial.ai -ne 'ready' -or -not $partial.run_id) { throw 'Partial result is inaccurate.' }
$installed = Join-Path $prefs 'plugins\ArgentumSplat'
if (-not (Test-Path -LiteralPath (Join-Path $installed 'ArgentumSplat.pyp'))) { throw 'AI/converter failure removed the installed plugin.' }

# Retry updates an installed plugin, preserves it, and bypasses AI in ImportOnly.
[IO.File]::WriteAllText((Join-Path $testSource 'setup_formats.ps1'), "param(`$RuntimeRoot, [switch]`$Repair); Write-Host 'Formats fixture ready'")
[IO.File]::WriteAllText((Join-Path $testSource 'setup_backend.ps1'), "throw 'AI must not execute in ImportOnly'")
& powershell.exe @arguments -ImportOnly *> (Join-Path $TestRoot 'import-only.log')
if ($LASTEXITCODE -ne 0) { throw 'ImportOnly retry failed.' }
$retried = Get-Content -LiteralPath (Join-Path $runtime 'setup-result.json') -Raw | ConvertFrom-Json
if ($retried.formats -ne 'ready' -or $retried.ai -ne 'skipped' -or $retried.run_id -eq $partial.run_id) { throw 'Retry has stale/incorrect status.' }
$backups = @(Get-ChildItem -LiteralPath (Join-Path $prefs 'ArgentumSplat-backups') -Directory)
if ($backups.Count -ne 1 -or -not (Test-Path -LiteralPath (Join-Path $backups[0].FullName 'ArgentumSplat.pyp'))) { throw 'Previous plugin was not backed up.' }

# Running the installer from its installed folder must still set up dependencies.
$installedScript = Join-Path $installed 'Install.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installedScript -PreferencesFolder $prefs -RuntimeDir $runtime -FormatsRoot $formats -ImportOnly *> (Join-Path $TestRoot 'installed-source.log')
if ($LASTEXITCODE -ne 0) { throw 'Already-installed source could not run setup.' }
$sameSource = Get-Content -LiteralPath (Join-Path $runtime 'setup-result.json') -Raw | ConvertFrom-Json
if ($sameSource.run_id -eq $retried.run_id) { throw 'Already-installed source skipped dependency setup.' }
[ordered]@{ passed = $true; partial_failure_retains_plugin = $true; other_component_still_installs = $true; import_only = $true; backup_verified = $true; installed_source_runs_setup = $true; run_ids_change = $true } | ConvertTo-Json
