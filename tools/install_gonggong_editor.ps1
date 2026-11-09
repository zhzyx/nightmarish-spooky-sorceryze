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
if (Test-Path -LiteralPath (Join-Path $buildRoot.FullName 'tools/package_tianshu_ui.py') -PathType Leaf) {
    $names += 'tianshu-ui.json'
}
foreach ($name in $names) {
    if (-not (Test-Path -LiteralPath (Join-Path $BuildDirectory $name) -PathType Leaf)) { throw "Missing build artifact: $name" }
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$installRoot = Split-Path -Parent $destination
$lockPath = Join-Path $installRoot '.editor-install.lock'
$lock = [IO.FileStream]::new($lockPath, 'OpenOrCreate', 'ReadWrite', 'None', 4096, [IO.FileOptions]::DeleteOnClose)
$stage = Join-Path $installRoot ('.editor-install-' + [guid]::NewGuid().ToString('N'))
$changes = @()
$installed = @()
$cleanup = $true
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    $records = @()
    foreach ($name in $names) {
        $source = Join-Path $BuildDirectory $name
        $staged = Join-Path $stage $name
        Copy-Item -LiteralPath $source -Destination $staged
        $digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        if ((Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) {
            throw "Installation hash mismatch: $name"
        }
        $records += @{path="bin/$name";sha256=$digest;bytes=(Get-Item -LiteralPath $staged).Length}
        $changes += @{source=$staged;target=(Join-Path $destination $name)}
    }
    $manifest = @{schema_version=1;path_base='installation_directory';workspace='../..';source_root='../..';default_editor='bin/godot.windows.editor.x86_64.exe';files=$records}
    $stagedManifest = Join-Path $stage 'installed.local.json'
    [IO.File]::WriteAllText($stagedManifest, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    $changes += @{source=$stagedManifest;target=(Join-Path $installRoot 'installed.local.json')}
    foreach ($change in $changes) {
        if ([IO.File]::Exists($change.target)) {
            $change.backup = $change.source + '.prev'
            [IO.File]::Replace($change.source, $change.target, $change.backup)
        } else {
            [IO.File]::Move($change.source, $change.target)
        }
        $installed += $change
    }
    $manifest
} catch {
    # Preserve old executables, package and inventory together when any replacement fails.
    for ($i = $installed.Count - 1; $i -ge 0; $i--) {
        $change = $installed[$i]
        try {
            if ($change.backup) {
                [IO.File]::Replace($change.backup, $change.target, $change.source)
            } else {
                [IO.File]::Delete($change.target)
            }
        } catch {
            $cleanup = $false
            Write-Warning "Installation rollback requires recovery from $stage for $($change.target)"
        }
    }
    throw
} finally {
    try {
        if ($cleanup -and [IO.Directory]::Exists($stage)) {
            foreach ($file in [IO.Directory]::GetFiles($stage)) { [IO.File]::Delete($file) }
            [IO.Directory]::Delete($stage)
        }
    } finally {
        $lock.Dispose()
    }
}
