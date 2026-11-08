[CmdletBinding()]
param([string]$BuildDirectory)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $BuildDirectory) { $BuildDirectory = Join-Path $workspace 'bin' }
# An external build will load the bridge scripts from this installation's workspace.
# Check the producer's scripts before touching either installed executable.
$buildRoot = Get-Item -LiteralPath $BuildDirectory
while ($buildRoot -and -not (Test-Path -LiteralPath (Join-Path $buildRoot.FullName 'SConstruct') -PathType Leaf)) {
    $buildRoot = $buildRoot.Parent
}
if (-not $buildRoot) { throw 'Cannot locate build source. Supply a build directory inside its Godot checkout.' }
if ($buildRoot.FullName -ne $workspace) {
    foreach ($script in @('codex_cli/godot_bridge.js','codex_cli/action_schema.js','codex_cli/attach_job.ps1',
                          'codebuddy_cli/godot_bridge.js','codebuddy_cli/godot_acp.js','codebuddy_cli/godot_terminal.js','codebuddy_cli/package-lock.json')) {
        $relative = "tools/$script"
        if ((Get-FileHash -LiteralPath (Join-Path $buildRoot.FullName $relative)).Hash -ne
            (Get-FileHash -LiteralPath (Join-Path $workspace $relative)).Hash) {
            throw "CLI bridge version mismatch: $relative. Align the installation with the build source first."
        }
    }
}
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
