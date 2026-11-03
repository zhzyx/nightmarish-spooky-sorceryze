[CmdletBinding()]
param([string]$BuildDirectory)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $BuildDirectory) { $BuildDirectory = Join-Path $workspace 'bin' }
$destination = Join-Path $workspace 'project/godot/bin'
$names = @('godot.windows.editor.x86_64.exe', 'godot.windows.editor.x86_64.console.exe')
foreach ($name in $names) {
    if (-not (Test-Path -LiteralPath (Join-Path $BuildDirectory $name) -PathType Leaf)) { throw "Missing build artifact: $name" }
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$records = @()
foreach ($name in $names) {
    $source = Join-Path $BuildDirectory $name
    $target = Join-Path $destination $name
    Copy-Item -LiteralPath $source -Destination $target -Force
    $digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) { throw "Installation hash mismatch: $name" }
    $records += @{path="bin/$name";sha256=$digest;bytes=(Get-Item -LiteralPath $target).Length}
}
$manifest = @{schema_version=1;path_base='installation_directory';workspace='../..';source_root='../..';default_editor='bin/godot.windows.editor.x86_64.exe';files=$records}
$json = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $workspace 'project/godot/installed.local.json'), $json, [Text.UTF8Encoding]::new($false))
$manifest
