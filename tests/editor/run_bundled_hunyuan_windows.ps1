# Build on Windows x64 and exercise the moved editor in a new user profile.
# Run from PowerShell 7 with permission to manage per-program firewall rules.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Editor,
    [Parameter(Mandatory)][string]$WorkRoot,
    [string]$Runtime,
    [string]$Checkpoint,
    [string]$License,
    [string]$Image
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/../..").Path
$entry = (Resolve-Path -LiteralPath $Editor).Path
$work = [IO.Path]::GetFullPath($WorkRoot)
if (Test-Path -LiteralPath $work) { throw "Choose a new working directory: $work" }
foreach ($ancestor in @(for ($p = [IO.DirectoryInfo]::new($work); $p; $p = $p.Parent) { $p })) {
    if (Test-Path (Join-Path $ancestor.FullName 'gonggong-workspace.json')) {
        throw 'Choose a work directory outside a GongGong workspace.'
    }
}
$report = Join-Path $work 'report'
$project = Join-Path $work 'project'
$initial = Join-Path $work 'first connection'
$output = Join-Path $work 'native result'
$prepared = Join-Path $work 'assembled'
$relocated = Join-Path $work 'Relocated edition'
$isolatedProfile = Join-Path $work 'private profile'
New-Item -ItemType Directory -Path $report,$project,$initial,$output,$isolatedProfile | Out-Null
$source = (& git -C $repo rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the candidate source.' }
if (!$Image) { $Image = Join-Path $repo 'misc/logo/icon.png' }
$inputImage = Join-Path $work ([IO.Path]::GetFileName($Image))
Copy-Item -LiteralPath $Image -Destination $inputImage
$test = Join-Path $work 'bundled_hunyuan_acceptance.gd'
Copy-Item -LiteralPath "$repo/samples/ainative-workbench/bundled_hunyuan_acceptance.gd" -Destination $test
Set-Content -Path "$project/project.godot" -Encoding utf8NoBOM -Value @'
config_version=5
[application]
config/name="Bundled Hunyuan acceptance"
[rendering]
renderer/rendering_method="gl_compatibility"
'@
$pack = @("$repo/tools/package_maliang_editor.py", '--editor', $entry, '--output', $prepared)
if ($Runtime) { $pack += '--runtime',$Runtime }
if ($Checkpoint) { $pack += '--checkpoint',$Checkpoint }
if ($License) { $pack += '--license',$License }
& python @pack
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
$executableName = [IO.Path]::GetFileName($entry)
$exe = Join-Path $prepared $executableName
$bundle = Join-Path $prepared 'maliang-hunyuan'
$checkpointPath = Join-Path $bundle 'models/checkpoints/hunyuan3d-mini.safetensors'
$config = Get-Content "$bundle/config.json" -Raw | ConvertFrom-Json
$sha = (Get-FileHash -LiteralPath $checkpointPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sha -ne '3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b' -or $sha -ne $config.checkpoints.mesh.sha256) {
    throw 'The packaged model digest differs from the release identity.'
}
$platform = Get-CimInstance Win32_OperatingSystem
$record = [ordered]@{
    source_revision = $source
    windows = $platform.Caption
    os_version = $platform.Version
    architecture = $platform.OSArchitecture
    machine = $env:COMPUTERNAME
    logical_processors = [Environment]::ProcessorCount
    available_memory_bytes_at_start = [int64]$platform.FreePhysicalMemory * 1024
    editor_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    input_sha256 = (Get-FileHash -LiteralPath $inputImage -Algorithm SHA256).Hash.ToLowerInvariant()
    checkpoint_sha256 = $sha
    checkpoint_bytes = (Get-Item -LiteralPath $checkpointPath).Length
    backend_revision = $config.backend_revision
    runtime = (Get-Content "$bundle/sources.json" -Raw | ConvertFrom-Json).installed
    workflow_run = $env:GITHUB_RUN_ID
    first_connection = $false
    relocated = $false
    offline_firewall = $false
    completed = $false
}
$ruleNames = @()
$before = @{}
Push-Location $work
try {
    if (@(Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object Enabled -ne $true).Count) {
        throw 'Enable Windows Firewall on this test host for the offline acceptance.'
    }
    # The model protocol uses IPv4 loopback. Deny everything except 127.0.0.0/8.
    $outside = '0.0.0.0/2','64.0.0.0/3','96.0.0.0/4','112.0.0.0/5','120.0.0.0/6','124.0.0.0/7','126.0.0.0/8','128.0.0.0/1','::/0'
    if (Get-NetTCPConnection -State Listen -LocalPort 18788 -ErrorAction SilentlyContinue) {
        throw 'The acceptance port is already occupied on this host.'
    }
    $environment = @{
        APPDATA = "$isolatedProfile/roaming"; LOCALAPPDATA = "$isolatedProfile/local"; USERPROFILE = $isolatedProfile; HOME = $isolatedProfile
        TEMP = "$isolatedProfile/temp"; TMP = "$isolatedProfile/temp"; HF_HUB_OFFLINE = '1'; TRANSFORMERS_OFFLINE = '1'
        HTTP_PROXY = 'http://127.0.0.1:9'; HTTPS_PROXY = 'http://127.0.0.1:9'; NO_PROXY = '127.0.0.1,localhost'
        PATH = "$env:SystemRoot/System32;$env:SystemRoot"; PYTHONNOUSERSITE = '1'; GONGGONG_WORKSPACE = $null
        PYTHONHOME = $null; PYTHONPATH = $null; VIRTUAL_ENV = $null; CONDA_PREFIX = $null
    }
    New-Item -ItemType Directory -Path $environment.APPDATA,$environment.LOCALAPPDATA,$environment.TEMP | Out-Null
    foreach ($key in $environment.Keys) {
        $before[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $environment[$key], 'Process')
    }
    foreach ($location in @($prepared, $relocated)) {
        $first = $location -eq $prepared
        if (!$first) {
            Move-Item -LiteralPath $prepared -Destination $relocated
            $record.relocated = !(Test-Path -LiteralPath $prepared)
        }
        $exe = Join-Path $location $executableName
        $bundle = Join-Path $location 'maliang-hunyuan'
        $executables = @($exe, (Join-Path $bundle 'python/python.exe'))
        $pythonWindowed = Join-Path $bundle 'python/pythonw.exe'
        if (Test-Path $pythonWindowed) { $executables += $pythonWindowed }
        foreach ($application in $executables) {
            $name = 'Maliang-accept-' + [guid]::NewGuid().ToString('N')
            New-NetFirewallRule -Name $name -DisplayName $name -Program $application -Direction Outbound -Action Block -Profile Any -RemoteAddress $outside | Out-Null
            $ruleNames += $name
        }
        $record.offline_firewall = $true
        $record | ConvertTo-Json -Depth 8 | Set-Content "$report/windows.json" -Encoding utf8NoBOM
        $nativeArgs = @('--headless', '--editor', '--path', $project, '--script', $test, '--', $inputImage)
        if ($first) {
            $nativeArgs += $initial, 'connect'
            $result = $initial
            $receipt = Join-Path $report 'first-connection.json'
            $log = Join-Path $report 'first-connection.log'
        } else {
            $nativeArgs += $output
            $result = $output
            $receipt = Join-Path $report 'acceptance.json'
            $log = Join-Path $report 'editor.log'
        }
        & $exe @nativeArgs *> $log
        $status = $LASTEXITCODE
        if (Test-Path "$result/acceptance.json") { Copy-Item "$result/acceptance.json" $receipt }
        if ($status -ne 0) { throw "The native editor returned exit code $status. See $log." }
        if ($first) {
            $connection = Get-Content $receipt -Raw | ConvertFrom-Json
            if ($connection.ok -ne $true -or $connection.initial_configuration -ne 'fresh') {
                throw 'The editor could not connect from fresh settings on first launch.'
            }
            $record.first_configuration = $connection.initial_configuration
            $deadline = [DateTime]::UtcNow.AddSeconds(60)
            while (Get-NetTCPConnection -State Listen -LocalPort 18788 -ErrorAction SilentlyContinue) {
                if ([DateTime]::UtcNow -ge $deadline) { throw 'The first editor did not release its backend.' }
                Start-Sleep -Milliseconds 500
            }
            $record.first_connection = $true
        }
    }
    $acceptance = Get-Content "$report/acceptance.json" -Raw | ConvertFrom-Json
    if ($acceptance.ok -ne $true -or $acceptance.initial_configuration -ne 'saved' -or
        $acceptance.vertices -le 0 -or $acceptance.model_sha256 -ne $sha -or
        $acceptance.mesh_sha256 -notmatch '^[0-9a-f]{64}$' -or $null -eq $acceptance.devices -or @($acceptance.devices).Count -lt 1 -or
        !(Test-Path -LiteralPath "$output/mesh.tscn" -PathType Leaf) -or (Get-Item "$output/mesh.tscn").Length -eq 0) {
        throw 'Missing generated mesh, model identity, device, or scene-reopen evidence.'
    }
    $record.reopened_configuration = $acceptance.initial_configuration
    $record.completed = $true
} finally {
    foreach ($key in $before.Keys) { [Environment]::SetEnvironmentVariable($key, $before[$key], 'Process') }
    foreach ($rule in $ruleNames) { Remove-NetFirewallRule -Name $rule }
    $record | ConvertTo-Json -Depth 8 | Set-Content "$report/windows.json" -Encoding utf8NoBOM
    Pop-Location
}
Write-Output "Distribution: $relocated"
Write-Output "Acceptance: $report"
