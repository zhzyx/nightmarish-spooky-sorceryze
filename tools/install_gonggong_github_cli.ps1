[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Workspace
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($Workspace)
if (-not (Test-Path -LiteralPath (Join-Path $root 'CURRENT_FRAMEWORK.json') -PathType Leaf)) {
    throw 'Select a complete GongGong workspace.'
}
$runtime = Join-Path $root 'project/runtime'
$destination = Join-Path $runtime 'gh'
$binary = Join-Path $destination 'bin/gh.exe'
if (Test-Path -LiteralPath $binary -PathType Leaf) {
    $versionOutput = & $binary --version
    if ($LASTEXITCODE -eq 0) { return $binary }
    throw 'The workspace GitHub CLI is invalid; retain it for recovery before reinstalling.'
}
# Pin the official release and its published SHA-256. Downloading never runs
# a remote installer and does not modify PATH or the system installation.
$version = '2.103.3'
$archiveHash = '98d0cfa794721665d7973dd728c78aff7bd836d58f10f6d7a03568eccb0a22e0'
$url = "https://github.com/cli/cli/releases/download/v$version/gh_${version}_windows_amd64.zip"
$transaction = Join-Path $runtime ('.gonggong-setup/gh-download-' + [guid]::NewGuid().ToString('N'))
foreach ($target in @($transaction, $destination)) {
    $cursor = [IO.Path]::GetFullPath($target)
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Linked runtime installation paths are not supported.'
        }
        $parent = Split-Path -Parent $cursor
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}
New-Item -ItemType Directory -Force -Path $transaction | Out-Null
$archive = Join-Path $transaction 'github-cli.zip'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive -TimeoutSec 120
$archiveStream = [IO.File]::OpenRead($archive)
$archiveAlgorithm = [Security.Cryptography.SHA256]::Create()
try { $actualArchiveHash = ([BitConverter]::ToString($archiveAlgorithm.ComputeHash($archiveStream))).Replace('-','').ToLowerInvariant() }
finally { $archiveStream.Dispose(); $archiveAlgorithm.Dispose() }
if ($actualArchiveHash -ne $archiveHash) {
    throw 'The official GitHub CLI archive checksum did not match; nothing was installed.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
$stage = Join-Path $transaction 'gh-staged'
New-Item -ItemType Directory -Path (Join-Path $stage 'bin') | Out-Null
try {
    $entries = @($zip.Entries | Where-Object { $_.FullName -match '^(?:gh_[^/]+/)?bin/gh\.exe$' })
    if ($entries.Count -ne 1) { throw 'The GitHub CLI archive does not contain exactly one expected executable.' }
    # Extract only the executable to a fixed path, never arbitrary ZIP paths.
    [IO.Compression.ZipFileExtensions]::ExtractToFile($entries[0], (Join-Path $stage 'bin/gh.exe'))
} finally {
    $zip.Dispose()
}
$versionOutput = & (Join-Path $stage 'bin/gh.exe') --version
if ($LASTEXITCODE -ne 0) { throw 'The downloaded GitHub CLI did not pass its execution probe.' }
$receipt = @{version=$version;source=$url;archive_sha256=$archiveHash;installed_at=[DateTime]::UtcNow.ToString('o')}
[IO.File]::WriteAllText((Join-Path $stage 'source.json'), ($receipt | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
if (Test-Path -LiteralPath $destination) { throw 'The GitHub CLI destination already exists; retained the verified download for recovery.' }
Move-Item -LiteralPath $stage -Destination $destination
return $binary
