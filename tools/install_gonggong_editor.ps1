[CmdletBinding()]
param(
    [Parameter(ParameterSetName='Local')][string]$BuildDirectory,
    [Parameter(Mandatory,ParameterSetName='Actions')][string]$ActionsRun,
    [string]$Python = $env:GONGGONG_PYTHON
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'installed_editor_workspace.ps1')
$checkout = Split-Path -Parent $PSScriptRoot
$workspace = Get-EditorWorkspace $checkout
$runtime = & (Join-Path $PSScriptRoot 'run_issue_gate.ps1') -Repo $checkout -Python $Python -ProbeOnly | ConvertFrom-Json
if (-not $BuildDirectory) { $BuildDirectory = Join-Path $checkout 'bin' }
$destination = Join-Path $workspace 'project/godot/bin'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$installRoot = Split-Path -Parent $destination
$lockPath = Join-Path $installRoot '.editor-install.lock'
$lock = [IO.FileStream]::new($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None, 4096, [IO.FileOptions]::DeleteOnClose)
$stage = Join-Path $installRoot ('.editor-install-' + [guid]::NewGuid().ToString('N'))
$changes = @()
$installed = @()
$cleanup = $true
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    $sourceArgs = if ($ActionsRun) { @('--actions-run', $ActionsRun) } else { @('--build-directory', $BuildDirectory) }
    $revision = & $runtime.python (Join-Path $PSScriptRoot 'stage_installed_editor.py') --workspace $workspace --stage $stage @sourceArgs
    if ($LASTEXITCODE -ne 0 -or $revision -notmatch '^[a-f0-9]{40}$') { throw 'Main editor staging failed.' }
    $records = @()
    $names = @([IO.Directory]::GetFiles($stage) | ForEach-Object { [IO.Path]::GetFileName($_) })
    foreach ($name in $names) {
        $staged = Join-Path $stage $name
        $digest = Get-EditorDigest $staged
        $records += @{path="bin/$name";sha256=$digest;bytes=(Get-Item -LiteralPath $staged).Length}
        $changes += @{source=$staged;target=(Join-Path $destination $name)}
    }
    $consoleName = 'godot.windows.editor.x86_64.console.exe'
    $console = if ($names -contains $consoleName) { "bin/$consoleName" } else { 'bin/godot.windows.editor.x86_64.exe' }
    # Remove previously managed runtime components that the new build no longer ships.
    $previous = Join-Path $installRoot 'installed.local.json'
    if ([IO.File]::Exists($previous)) {
        $old = Get-Content -LiteralPath $previous -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($item in $old.files) {
            if ($item.path -match '^bin/([a-zA-Z0-9_.-]+[.]dll|godot[.]windows[.]editor[.]x86_64[.]console[.]exe)$') {
                $name = $Matches[1]
                $target = Join-Path $destination $name
                if ($names -notcontains $name -and [IO.File]::Exists($target)) {
                    if ((Get-EditorDigest $target) -ne $item.sha256) { throw "Changed previous runtime file: $target" }
                    $changes += @{target=$target;remove=$true;backup=(Join-Path $stage ($name + '.prev'))}
                }
            }
        }
    }
    $manifest = @{console_editor=$console;schema_version=2;main_revision=$revision;path_base='installation_directory';workspace='../..';source_root='../..';default_editor='bin/godot.windows.editor.x86_64.exe';files=$records}
    $stagedManifest = Join-Path $stage 'installed.local.json'
    [IO.File]::WriteAllText($stagedManifest, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    $changes += @{source=$stagedManifest;target=(Join-Path $installRoot 'installed.local.json')}
    foreach ($change in $changes) {
        if ($change['remove']) {
            [IO.File]::Move($change.target, $change.backup)
        } elseif ([IO.File]::Exists($change.target)) {
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
            if ($change['remove']) {
                [IO.File]::Move($change.backup, $change.target)
            } elseif ($change.backup) {
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
