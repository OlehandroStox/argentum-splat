param(
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA "ArgentumSplat\formats"),
    [string]$NodeExe = ""
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Local npm prefix only. No global package installation or system PATH changes.
$PackageVersion = "3.10.1"
$NodeVersion = "24.19.0"
$NodeArchiveName = "node-v$NodeVersion-win-x64.zip"
$NodeSha256 = "57f71ab3652e797d84acddc79c81cc9ff1c6ddb2a1974cdb83f00fee9bff4c73"
$RuntimeRoot = [IO.Path]::GetFullPath($RuntimeRoot)
$Sources = Join-Path $PSScriptRoot "backend\formats"
$PackageRoot = Join-Path $RuntimeRoot "packages-$PackageVersion"
$ManifestPath = Join-Path $RuntimeRoot "formats.json"

if (-not [Environment]::Is64BitOperatingSystem) { throw "The format runtime requires 64-bit Windows." }
if (-not (Test-Path -LiteralPath (Join-Path $Sources "package-lock.json"))) {
    throw "Pinned backend/formats/package-lock.json is missing. Re-extract the complete plugin."
}
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null

function Find-NpmCli([string]$CandidateNode) {
    if (-not $CandidateNode -or -not (Test-Path -LiteralPath $CandidateNode)) { return "" }
    $candidateNpm = Join-Path (Split-Path -Parent $CandidateNode) "node_modules\npm\bin\npm-cli.js"
    if (-not (Test-Path -LiteralPath $candidateNpm)) { return "" }
    $reported = (& $CandidateNode --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $reported -notmatch "^v(\d+)\.") { return "" }
    if ([int]$Matches[1] -lt 22) { return "" }
    return $candidateNpm
}

$NpmCli = ""
if ($NodeExe) {
    $NodeExe = [IO.Path]::GetFullPath($NodeExe)
    $NpmCli = Find-NpmCli $NodeExe
    if (-not $NpmCli) { throw "The supplied NodeExe needs Node 22+ and its sibling npm installation." }
} else {
    $available = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($available) {
        $NodeExe = $available.Source
        $NpmCli = Find-NpmCli $NodeExe
    }
}

if (-not $NpmCli) {
    $Toolchain = Join-Path $RuntimeRoot "toolchain"
    $NodeFolder = Join-Path $Toolchain "node-v$NodeVersion-win-x64"
    $NodeExe = Join-Path $NodeFolder "node.exe"
    $NpmCli = Find-NpmCli $NodeExe
    if (-not $NpmCli) {
        New-Item -ItemType Directory -Force -Path $Toolchain | Out-Null
        $Downloads = Join-Path $RuntimeRoot "downloads"
        New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
        $Archive = Join-Path $Downloads $NodeArchiveName
        Write-Output "Downloading official portable Node.js $NodeVersion..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://nodejs.org/dist/v$NodeVersion/$NodeArchiveName" -OutFile $Archive
        $ActualSha = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ActualSha -ne $NodeSha256) { throw "Node.js archive SHA-256 mismatch. Installation stopped." }
        # Absolute destination is contained in the explicit runtime folder.
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        if (Test-Path -LiteralPath $NodeFolder) {
            throw "An incomplete Node toolchain already exists at $NodeFolder. Choose a fresh RuntimeRoot."
        }
        [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Toolchain)
        $NpmCli = Find-NpmCli $NodeExe
        if (-not $NpmCli) { throw "Portable Node.js did not initialize correctly." }
    }
}

Write-Output "Installing exact format dependencies from the bundled lockfile..."
Copy-Item -LiteralPath (Join-Path $Sources "package.json") -Destination (Join-Path $PackageRoot "package.json") -Force
Copy-Item -LiteralPath (Join-Path $Sources "package-lock.json") -Destination (Join-Path $PackageRoot "package-lock.json") -Force
# CPU decoding uses the packaged WebP WASM. Native GPU install scripts are unnecessary.
& $NodeExe $NpmCli ci --prefix $PackageRoot --ignore-scripts --no-audit --no-fund --update-notifier=false --fetch-timeout=120000 --fetch-retries=1
if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE." }
$CliJs = Join-Path $PackageRoot "node_modules\@playcanvas\splat-transform\bin\cli.mjs"
& $NodeExe $CliJs --version
$CliExitCode = $LASTEXITCODE
$InstalledPackage = Get-Content -LiteralPath (Join-Path $PackageRoot "node_modules\@playcanvas\splat-transform\package.json") -Raw | ConvertFrom-Json
if ($CliExitCode -ne 0 -or $InstalledPackage.version -ne $PackageVersion) {
    throw "The installed splat-transform CLI failed its version check."
}
$LockSha = (Get-FileHash -LiteralPath (Join-Path $PackageRoot "package-lock.json") -Algorithm SHA256).Hash.ToLowerInvariant()
$Manifest = [ordered]@{
    schema_version = 1
    node_exe = $NodeExe
    cli_js = $CliJs
    version = $PackageVersion
    package_root = $PackageRoot
    package_lock_sha256 = $LockSha
    installed_at_utc = [DateTime]::UtcNow.ToString("o")
    source = "https://github.com/playcanvas/splat-transform"
    license = "MIT"
}
$PendingManifest = Join-Path $RuntimeRoot ("formats-" + [Guid]::NewGuid().ToString("N") + ".json")
[IO.File]::WriteAllText($PendingManifest, ($Manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $PendingManifest -Destination $ManifestPath -Force
Write-Output "Format runtime ready: SOG, KSPLAT, compressed PLY and SPZ v2-v4."
Write-Output $ManifestPath
