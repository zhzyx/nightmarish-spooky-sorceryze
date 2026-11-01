# Launch the most recently built Godot editor from bin/.
#
# The in-editor self-update alternates between the self_update_a and
# self_update_b slots, so no single binary stays current and a desktop shortcut
# pointing straight at one of them breaks on every other build. Resolving the
# newest binary at launch time keeps one shortcut valid regardless of which slot
# the last build used, and also covers binaries produced by a manual SCons run.
#
# Usage:
#   launch_latest_editor.ps1                 # open the project manager
#   launch_latest_editor.ps1 <project dir>   # open a project directly
#   launch_latest_editor.ps1 -Probe          # report the choice, launch nothing
#   launch_latest_editor.ps1 -Console        # use the console build for stdout

[CmdletBinding()]
param(
    [string] $Project,
    [switch] $Console,
    [switch] $Probe
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$binaries = Join-Path $root "bin"

# Editor builds share a "godot.<platform>.editor..." prefix. The console variant
# differs only in its suffix, so it has to be selected explicitly rather than
# picked up as merely the newest file.
$candidates = @(Get-ChildItem -Path $binaries -Filter "godot.windows.editor.*.exe" -File -ErrorAction SilentlyContinue |
    Where-Object { $Console -eq $_.Name.EndsWith(".console.exe") })

if ($candidates.Count -eq 0) {
    $variant = if ($Console) { "console editor" } else { "editor" }
    Write-Error "No $variant binary in $binaries. Build one first, then retry."
    exit 1
}

$editor = ($candidates | Sort-Object LastWriteTime -Descending)[0]

# Without DOTNET_ROOT the editor falls back to the system .NET and reports
# "Unable to load .NET runtime, no compatible version was found".
$dotnet = Join-Path $root ".dotnet"
if (Test-Path (Join-Path $dotnet "dotnet.exe")) {
    $env:DOTNET_ROOT = $dotnet
    $env:DOTNET_ROOT_X64 = $dotnet
    $env:PATH = $dotnet + [IO.Path]::PathSeparator + $env:PATH
}

$arguments = @()
if ($Project) {
    if (-not (Test-Path -PathType Container $Project)) {
        Write-Error "Project directory not found: $Project"
        exit 1
    }
    $arguments = @("--editor", "--path", $Project)
}

if ($Probe) {
    [pscustomobject]@{
        Editor     = $editor.FullName
        Built      = $editor.LastWriteTime
        DotnetRoot = $env:DOTNET_ROOT
        Arguments  = ($arguments -join " ")
        Candidates = $candidates.Count
    } | Format-List
    exit 0
}

if ($arguments.Count -gt 0) {
    Start-Process -FilePath $editor.FullName -ArgumentList $arguments
} else {
    Start-Process -FilePath $editor.FullName
}
