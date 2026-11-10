[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [Parameter(Mandatory=$true)][string]$GodotExe,
    [string]$Config,
    [string]$Project = (Join-Path $PSScriptRoot '../../samples/ainative-workbench'),
    [switch]$BackendOnly
)
$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path
if (-not $Config) { $Config = Join-Path $runtime 'config.json' }
$configPath = (Resolve-Path -LiteralPath $Config).Path
$settings = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$endpoint = [uri]$settings.endpoint
if ($endpoint.Scheme -notin @('http','https') -or $endpoint.UserInfo -or $endpoint.Query -or $endpoint.Fragment) { throw 'Invalid trusted endpoint' }
$pythonPath = Join-Path $runtime 'venv/Scripts/python.exe'
$comfyMain = Join-Path $runtime 'ComfyUI-src/main.py'
foreach ($required in @($pythonPath,$comfyMain,$GodotExe,(Join-Path $Project 'project.godot'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing installed file: $required" }
}
function Test-ComfyHealth {
    try {
        $info = Invoke-RestMethod -Uri ($settings.endpoint.TrimEnd('/') + '/system_stats') -TimeoutSec 3
        return $null -ne $info.system
    } catch { return $false }
}
if (-not (Test-ComfyHealth)) {
    if ($endpoint.Host -notin @('127.0.0.1','localhost') -or $endpoint.Scheme -ne 'http') { throw 'Remote backend must already be running' }
    $arguments = @(('"' + $comfyMain + '"'),'--base-directory',('"' + $runtime + '"'),'--listen','127.0.0.1','--port',([string]$endpoint.Port),'--lowvram','--disable-dynamic-vram','--reserve-vram','1.5','--disable-smart-memory','--disable-all-custom-nodes','--disable-api-nodes','--disable-auto-launch')
    $backend = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $runtime -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'comfy.stdout.log') -RedirectStandardError (Join-Path $runtime 'comfy.stderr.log')
    $deadline = (Get-Date).AddSeconds(120)
    while (-not (Test-ComfyHealth)) {
        if ($backend.HasExited) { throw 'ComfyUI exited; inspect runtime/comfy.stderr.log' }
        if ((Get-Date) -gt $deadline) { throw 'ComfyUI startup timed out; process remains available for inspection' }
        Start-Sleep -Milliseconds 500
    }
}
$objectInfo = Invoke-RestMethod -Uri ($settings.endpoint.TrimEnd('/') + '/object_info') -TimeoutSec 30
foreach ($node in @('CheckpointLoaderSimple','ImageOnlyCheckpointLoader','Hunyuan3Dv2Conditioning','VAEDecodeHunyuan3D','VoxelToMesh','MeshSmoothNormals','SaveGLB')) {
    if ($null -eq $objectInfo.$node) { throw "Backend missing required node: $node" }
}
$env:AINATIVE_COMFY_CONFIG = $configPath
$env:AINATIVE_PYTHON = $pythonPath
$env:AINATIVE_PROVIDER_FACTORY = 'comfy_provider:factory'
if (-not $BackendOnly) {
    Start-Process -FilePath $GodotExe -ArgumentList @('--editor','--path',('"' + (Resolve-Path -LiteralPath $Project).Path + '"')) -WindowStyle Hidden | Out-Null
}
Write-Output 'ComfyUI ready. Workbench local factory: comfy_provider:factory. Configuration is scoped to launched processes.'
