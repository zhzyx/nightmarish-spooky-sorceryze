# Create (or refresh) a desktop shortcut that always opens the newest editor
# build. The shortcut targets launch_latest_editor.ps1 instead of a binary, so it
# survives the self_update_a/self_update_b slot alternation.

[CmdletBinding()]
param(
    [string] $Name = "Godot Editor (latest build)",
    [string] $Project
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_latest_editor.ps1"
if (-not (Test-Path $launcher)) {
    Write-Error "Launcher not found: $launcher"
    exit 1
}

$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
if ($Project) {
    $arguments += " -Project `"$Project`""
}

# Borrow the icon from the newest build; the shortcut itself stays slot-agnostic.
$icon = Get-ChildItem -Path (Join-Path $root "bin") -Filter "godot.windows.editor.*.exe" -File -ErrorAction SilentlyContinue |
    Where-Object { -not $_.Name.EndsWith(".console.exe") } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$link = Join-Path ([Environment]::GetFolderPath("Desktop")) ($Name + ".lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $root
$shortcut.Description = "Launch the newest editor build in bin/, following the self_update slot in use"
$shortcut.WindowStyle = 7  # Minimised, so the launcher shell stays out of the way.
if ($icon) {
    $shortcut.IconLocation = $icon.FullName + ",0"
}
$shortcut.Save()

[pscustomobject]@{
    Shortcut = $link
    Target   = $shortcut.TargetPath
    Launcher = $launcher
    Icon     = if ($icon) { $icon.Name } else { "(default)" }
} | Format-List
