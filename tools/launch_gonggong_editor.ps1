[CmdletBinding()]
param([string]$Python, [string]$Node, [string]$Project, [switch]$Probe)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = $env:GONGGONG_PYTHON }
if (-not $Python -and (Test-Path -LiteralPath (Join-Path $workspace 'project/runtime/python/python.exe'))) { $Python = Join-Path $workspace 'project/runtime/python/python.exe' }
if (-not $Python) {
    $found = Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $Python = $found.Source }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Pass -Python with an installed Python 3.10+ executable.' }
if (-not $Node) { $Node = $env:GONGGONG_NODE }
if (-not $Node -and (Test-Path -LiteralPath (Join-Path $workspace 'project/runtime/node/node.exe'))) { $Node = Join-Path $workspace 'project/runtime/node/node.exe' }
if (-not $Node) {
    $found = Get-Command node -ErrorAction SilentlyContinue
    if ($found) { $Node = $found.Source }
}
if (-not $Node -or -not (Test-Path -LiteralPath $Node -PathType Leaf)) { throw 'Node.js is required for GongGong context checks. Pass -Node or add node to PATH.' }
$editor = Join-Path $workspace 'project/godot/bin/godot.windows.editor.x86_64.exe'
if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) { throw 'Build with tools/build_gonggong_editor.ps1, then run tools/install_gonggong_editor.ps1.' }
$env:GONGGONG_WORKSPACE = $workspace
$env:GONGGONG_PYTHON = $Python
$env:GONGGONG_NODE = $Node
$localGit = Join-Path $workspace 'project/runtime/git/cmd'
if (Test-Path -LiteralPath (Join-Path $localGit 'git.exe')) { $env:PATH = $localGit + [IO.Path]::PathSeparator + $env:PATH }
if (-not $Project) { $Project = Join-Path $workspace 'samples/gonggong-workbench' }
if ($Probe) { [pscustomobject]@{Editor=$editor;Workspace=$workspace;Python=$Python;Node=$Node;Project=$Project}; exit 0 }
& $editor --editor --path $Project
exit $LASTEXITCODE
