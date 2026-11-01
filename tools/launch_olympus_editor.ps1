[CmdletBinding()]
param([string]$Python, [string]$Node, [string]$Project, [switch]$Probe)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = $env:OLYMPUS_PYTHON }
if (-not $Python) {
    $found = Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $Python = $found.Source }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Pass -Python with an installed Python 3.10+ executable.' }
if (-not $Node) { $Node = $env:OLYMPUS_NODE }
if (-not $Node) {
    $found = Get-Command node -ErrorAction SilentlyContinue
    if ($found) { $Node = $found.Source }
}
if (-not $Node -or -not (Test-Path -LiteralPath $Node -PathType Leaf)) { throw 'Node.js is required for Olympus context checks. Pass -Node or add node to PATH.' }
$editor = Join-Path $workspace 'bin/godot.windows.editor.x86_64.exe'
if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) { throw 'Build the editor with tools/build_olympus_editor.ps1 or extract the release executable into bin/.' }
$env:OLYMPUS_WORKSPACE = $workspace
$env:OLYMPUS_PYTHON = $Python
$env:OLYMPUS_NODE = $Node
if (-not $Project) { $Project = Join-Path $workspace 'samples/olympus-workbench' }
if ($Probe) { [pscustomobject]@{Editor=$editor;Workspace=$workspace;Python=$Python;Node=$Node;Project=$Project}; exit 0 }
& $editor --editor --path $Project
exit $LASTEXITCODE
