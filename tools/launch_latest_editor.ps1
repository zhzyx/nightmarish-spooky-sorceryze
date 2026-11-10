# Compatibility entry for existing project-manager and project shortcuts.
[CmdletBinding()]
param([string]$Project, [switch]$Console, [switch]$Probe)

& (Join-Path $PSScriptRoot 'launch_gonggong_editor.ps1') @PSBoundParameters -ProjectManager:(!$Project)
exit $LASTEXITCODE
