[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$git = Join-Path $workspace 'project/runtime/git/cmd/git.exe'
if (-not (Test-Path -LiteralPath $git -PathType Leaf)) { throw 'Extract the complete release package first.' }
if (Test-Path -LiteralPath (Join-Path $workspace '.git')) { Write-Output 'Existing Git checkout preserved.'; exit 0 }
& $git -C $workspace init --initial-branch=main
if ($LASTEXITCODE -ne 0) { throw 'Git initialization failed.' }
& $git -C $workspace -c core.autocrlf=false add -- .
if ($LASTEXITCODE -ne 0) { throw 'Snapshot staging failed.' }
& $git -C $workspace -c user.name='Olympus release import' -c user.email='release-import@example.invalid' -c commit.gpgsign=false commit -m 'Import verified Olympus release snapshot'
if ($LASTEXITCODE -ne 0) { throw 'Snapshot commit failed.' }
Write-Output 'Release snapshot initialized. Original source commit is recorded in bundle-manifest.json.'
