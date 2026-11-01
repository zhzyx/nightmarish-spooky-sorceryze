[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Python, [int]$Jobs=8)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    $env:MSYSTEM = ''
    & $Python -m SCons platform=windows target=editor arch=x86_64 tests=yes accesskit=no d3d12=no angle=no "-j$Jobs"
    if ($LASTEXITCODE -ne 0) { throw 'Editor build failed.' }
    & (Join-Path $workspace 'bin/godot.windows.editor.x86_64.console.exe') --headless --test '--test-case=[AIChat]*'
    if ($LASTEXITCODE -ne 0) { throw 'AIChat regression tests failed.' }
} finally { Pop-Location }
