# Dot-source this helper, then call Ensure-ArgentumPython -RuntimeDir <path>.
# Downloaded CPython is private to Argentum Splat: no admin, registry or PATH changes.
function Ensure-ArgentumPython {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeDir,
        [string]$PythonExe = ""
    )
    $ErrorActionPreference = 'Stop'
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'Argentum Splat AI requires 64-bit Windows.'
    }
    $RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir).TrimEnd('\', '/')
    if ($RuntimeDir -eq [IO.Path]::GetPathRoot($RuntimeDir).TrimEnd('\', '/')) {
        throw 'RuntimeDir must be a dedicated folder, not a drive root.'
    }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $runtimePrefix = $RuntimeDir + [IO.Path]::DirectorySeparatorChar
    $venvDir = Join-Path $RuntimeDir '.venv'
    $runtimePython = Join-Path $venvDir 'Scripts\python.exe'

    function Assert-RuntimeChild([string]$Path) {
        $absolute = [IO.Path]::GetFullPath($Path)
        if (-not $absolute.StartsWith($runtimePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to change a path outside the runtime: $absolute"
        }
        # Never move through a junction/symlink supplied as a runtime child.
        $cursor = $absolute
        while ($cursor -and $cursor.StartsWith($runtimePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            if (Test-Path -LiteralPath $cursor) {
                $item = Get-Item -LiteralPath $cursor -Force
                if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw "Refusing to replace a linked runtime path: $cursor"
                }
            }
            $cursor = Split-Path -Parent $cursor
        }
        return $absolute
    }

    function Backup-RuntimePath([string]$Path) {
        $source = Assert-RuntimeChild $Path
        if (-not (Test-Path -LiteralPath $source)) { return }
        $backupRoot = Assert-RuntimeChild (Join-Path $RuntimeDir 'setup-backups')
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        $name = (Split-Path -Leaf $source) + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 6)
        $destination = Assert-RuntimeChild (Join-Path $backupRoot $name)
        Move-Item -LiteralPath $source -Destination $destination
        Write-Host "Preserved incomplete/old files: $destination"
    }

    function Test-CompatiblePython([string]$Executable, [bool]$RequireVenv = $false) {
        if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
        $probe = 'import sys,struct,ssl,venv,ensurepip; assert sys.implementation.name==''cpython''; assert (3,10)<=sys.version_info[:2]<=(3,12); assert struct.calcsize(''P'')==8; '
        if ($RequireVenv) { $probe += 'import pip; assert sys.prefix!=sys.base_prefix; ' }
        $probe += 'print(''ARGENTUM_PYTHON_OK'')'
        $oldPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $reported = @(& $Executable -I -c $probe 2>$null)
            return ($LASTEXITCODE -eq 0 -and $reported.Count -eq 1 -and $reported[0] -eq 'ARGENTUM_PYTHON_OK')
        } catch { return $false }
        finally { $ErrorActionPreference = $oldPreference }
    }

    if ($PythonExe) {
        $PythonExe = [IO.Path]::GetFullPath($PythonExe)
        if (-not (Test-CompatiblePython $PythonExe)) {
            throw 'The supplied PythonExe must be working CPython 3.10-3.12 x64 with ssl, venv and ensurepip.'
        }
    }
    if (Test-CompatiblePython $runtimePython $true) {
        Write-Host 'Python environment already ready; reusing it.'
        return $runtimePython
    }

    if (-not $PythonExe) {
        $pythonVersion = '3.12.15'
        $buildVersion = '20261020'
        $archiveName = "cpython-$pythonVersion+$buildVersion-x86_64-pc-windows-msvc-install_only.tar.gz"
        $archiveSha256 = '5e7d27ae6181fcf1f992c5a221b8fa7a320e7fd576c476434886292ccf2e20fb'
        $archiveUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$buildVersion/" + [Uri]::EscapeDataString($archiveName)
        $toolchainRoot = Assert-RuntimeChild (Join-Path $RuntimeDir 'toolchain')
        $pythonRoot = Assert-RuntimeChild (Join-Path $toolchainRoot "cpython-$pythonVersion-$buildVersion")
        $PythonExe = Join-Path $pythonRoot 'python\python.exe'
        if (-not (Test-CompatiblePython $PythonExe)) {
            $downloadRoot = Assert-RuntimeChild (Join-Path $RuntimeDir 'downloads')
            New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
            New-Item -ItemType Directory -Force -Path $toolchainRoot | Out-Null
            $archivePath = Assert-RuntimeChild (Join-Path $downloadRoot $archiveName)
            if ((Test-Path -LiteralPath $archivePath) -and (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $archiveSha256) {
                Write-Host 'Cached Python download is incomplete or corrupt; downloading a verified copy.'
                Backup-RuntimePath $archivePath
            }
            if (-not (Test-Path -LiteralPath $archivePath)) {
                [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
                $partialPath = Assert-RuntimeChild ($archivePath + '.part')
                for ($attempt = 1; $attempt -le 2; $attempt++) {
                    if (Test-Path -LiteralPath $partialPath) { Backup-RuntimePath $partialPath }
                    Write-Host "Downloading private Python $pythonVersion (46 MB; attempt $attempt/2)..."
                    $client = [Net.WebClient]::new()
                    try {
                        $client.Headers['User-Agent'] = 'ArgentumSplat-Installer'
                        $download = $client.DownloadFileTaskAsync([Uri]$archiveUrl, $partialPath)
                        $watch = [Diagnostics.Stopwatch]::StartNew()
                        while (-not $download.IsCompleted) {
                            if ($watch.Elapsed.TotalSeconds -gt 600) { throw 'Python download timed out. Check the internet connection and rerun Install.cmd.' }
                            Start-Sleep -Milliseconds 200
                        }
                        $download.GetAwaiter().GetResult() | Out-Null
                        if ((Get-FileHash -LiteralPath $partialPath -Algorithm SHA256).Hash -ne $archiveSha256) {
                            throw 'Python download failed SHA-256 verification; the archive will not be executed.'
                        }
                        $null = Assert-RuntimeChild $partialPath
                        $null = Assert-RuntimeChild $archivePath
                        Move-Item -LiteralPath $partialPath -Destination $archivePath
                        break
                    } catch {
                        if ($attempt -eq 2) { throw }
                        Write-Host "Download failed: $($_.Exception.Message). Retrying..."
                        Start-Sleep -Seconds 2
                    } finally {
                        $client.CancelAsync()
                        $client.Dispose()
                    }
                }
            }
            $tar = Join-Path ([Environment]::GetFolderPath('System')) 'tar.exe'
            if (-not (Test-Path -LiteralPath $tar)) {
                throw 'Windows tar.exe is missing. Install current Windows 10/11 updates, then rerun Install.cmd.'
            }
            $stage = Assert-RuntimeChild (Join-Path $toolchainRoot ('extract-' + [Guid]::NewGuid().ToString('N')))
            New-Item -ItemType Directory -Path $stage | Out-Null
            Write-Host "Extracting verified Python $pythonVersion..."
            & $tar -xzf $archivePath -C $stage
            if ($LASTEXITCODE -ne 0) { throw "Python extraction failed; rerun Install.cmd. Partial files: $stage" }
            $stagedPython = Join-Path $stage 'python\python.exe'
            if (-not (Test-CompatiblePython $stagedPython)) {
                throw "Extracted Python did not pass its runtime check. Partial files: $stage"
            }
            if (Test-Path -LiteralPath $pythonRoot) { Backup-RuntimePath $pythonRoot }
            $null = Assert-RuntimeChild $stage
            $null = Assert-RuntimeChild $pythonRoot
            Move-Item -LiteralPath $stage -Destination $pythonRoot
        } else {
            Write-Host "Private Python $pythonVersion already ready."
        }
    }

    if (Test-Path -LiteralPath $venvDir) { Backup-RuntimePath $venvDir }
    Write-Host 'Creating the isolated Python environment...'
    # venv records its final location; never create it in staging and move it.
    $null = Assert-RuntimeChild $venvDir
    & $PythonExe -I -m venv $venvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-CompatiblePython $runtimePython $true)) {
        throw 'Python environment creation failed. Rerun Install.cmd; incomplete files will be preserved and rebuilt.'
    }
    Write-Host 'Private Python and pip are ready.'
    return $runtimePython
}
