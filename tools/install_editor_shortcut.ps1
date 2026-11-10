[CmdletBinding()]
param(
    [string] $Name = "Godot Editor (latest build)",
    [string] $Project
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot 'installed_editor_workspace.ps1')
$root = Get-EditorWorkspace (Split-Path -Parent $PSScriptRoot)
$launcher = Join-Path $root 'tools/launch_gonggong_editor.ps1'
$probe = & $launcher -Probe -Project $Project -ProjectManager:(!$Project)
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
if ($Project) {
    $arguments += " -Project `"$Project`""
} else {
    $arguments += ' -ProjectManager'
}

$link = Join-Path ([Environment]::GetFolderPath("Desktop")) ($Name + ".lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $root
$shortcut.Description = "Launch the verified installed GongGong editor"
$shortcut.WindowStyle = 7  # Minimised, so the launcher shell stays out of the way.
$shortcut.IconLocation = $probe.Editor + ',0'
$shortcut.Save()

[pscustomobject]@{
    Shortcut = $link
    Target   = $shortcut.TargetPath
    Launcher = $launcher
    Icon     = $probe.Editor
} | Format-List
