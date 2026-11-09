[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Python,
    [ValidateRange(1, 1024)][int]$Jobs=8,
    [switch]$UseMinGW,
    [string]$CachePath,
    [ValidateRange(1, 65536)][int]$CacheLimitGiB=8
)
$ErrorActionPreference = 'Stop'
$buildArgs = @('--jobs', $Jobs)
if ($UseMinGW) { $buildArgs += '--use-mingw' }
if ($CachePath) { $buildArgs += @('--cache-path', $CachePath, '--cache-limit', $CacheLimitGiB) }
& $Python (Join-Path $PSScriptRoot 'build_gonggong_editor.py') @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Editor build or AIChat regression failed (exit $LASTEXITCODE)." }
