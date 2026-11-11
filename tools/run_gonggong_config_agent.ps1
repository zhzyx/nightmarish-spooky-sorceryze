[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Out,
    [string]$Progress,
    # Deprecated compatibility arguments: generic setup never starts a model.
    [string]$Codex,
    [string]$Model
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($Workspace)
$outFile = [IO.Path]::GetFullPath($Out)
$stateRoot = Join-Path $root 'project/runtime/.gonggong-setup'
$hostPolicy = $null
$providerStarted = $false
$providerCompleted = $false

function Write-Json([string]$Path, $Value) {
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 16), [Text.UTF8Encoding]::new($false))
}

function Write-AgentProgress([string]$Stage, [string]$Message) {
    if (-not $Progress) { return }
    $progressFile = [IO.Path]::GetFullPath($Progress)
    $parent = Split-Path -Parent $progressFile
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $temporary = $progressFile + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    $value = @{stage=$Stage;message=$Message;updated_at=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::WriteAllText($temporary, ($value | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $progressFile -Force
}

function Probe-Candidate([string]$Name, [string]$Path, [string]$Origin) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $full = [IO.Path]::GetFullPath($Path)
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Name -eq 'python') {
            $output = & $full -I -c 'import sys,ssl,sqlite3,json,hashlib,subprocess; assert sys.version_info >= (3,10); print(sys.version)' 2>&1
        } else {
            $output = & $full --version 2>&1
        }
        $exitCode = $LASTEXITCODE
    } catch {
        $output = $_.Exception.Message
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($exitCode -ne 0) { return $null }
    return @{component=$Name;path=$full;origin=$Origin;version=([string]($output -join ' ')).Trim()}
}

function Add-Candidate($List, $Seen, [string]$Name, [string]$Path, [string]$Origin) {
    if (-not $Path) { return }
    try { $full = [IO.Path]::GetFullPath($Path) } catch { return }
    $key = $Name + '|' + $full.ToLowerInvariant()
    if (-not $Seen.Add($key)) { return }
    $candidate = Probe-Candidate $Name $full $Origin
    if ($candidate) { [void]$List.Add($candidate) }
}

function Get-ValidatedInventory([string]$Workspace) {
    $list = [Collections.ArrayList]::new()
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $local = Join-Path $Workspace 'project/runtime'
    Add-Candidate $list $seen python (Join-Path $local 'python/python.exe') 'workspace_runtime'
    Add-Candidate $list $seen node (Join-Path $local 'node/node.exe') 'workspace_runtime'
    Add-Candidate $list $seen git (Join-Path $local 'git/cmd/git.exe') 'workspace_runtime'
    Add-Candidate $list $seen gh (Join-Path $local 'gh/bin/gh.exe') 'workspace_runtime'
    foreach ($name in @('python','node','git','gh')) {
        $configured = [Environment]::GetEnvironmentVariable('GONGGONG_' + $name.ToUpperInvariant())
        Add-Candidate $list $seen $name $configured 'session_configuration'
        $command = Get-Command ($name + '.exe') -CommandType Application -All -ErrorAction SilentlyContinue
        foreach ($item in @($command)) { Add-Candidate $list $seen $name $item.Source 'PATH' }
    }
    if ($env:LOCALAPPDATA) {
        Add-Candidate $list $seen gh (Join-Path $env:LOCALAPPDATA 'Programs/GitHub CLI/gh.exe') 'local_app'
        Add-Candidate $list $seen gh (Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Links/gh.exe') 'local_app'
        foreach ($path in @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python*/python.exe') -File -ErrorAction SilentlyContinue)) {
            Add-Candidate $list $seen python $path.FullName 'local_app'
        }
    }
    if ($env:ProgramFiles) {
        Add-Candidate $list $seen node (Join-Path $env:ProgramFiles 'nodejs/node.exe') 'program_files'
        Add-Candidate $list $seen git (Join-Path $env:ProgramFiles 'Git/cmd/git.exe') 'program_files'
        Add-Candidate $list $seen gh (Join-Path $env:ProgramFiles 'GitHub CLI/gh.exe') 'program_files'
        foreach ($path in @(Get-ChildItem -Path (Join-Path $env:ProgramFiles 'Python*/python.exe') -File -ErrorAction SilentlyContinue)) {
            Add-Candidate $list $seen python $path.FullName 'program_files'
        }
    }
    if ($env:GONGGONG_RUNTIME_SOURCE -and (Test-Path -LiteralPath $env:GONGGONG_RUNTIME_SOURCE -PathType Container)) {
        Add-Candidate $list $seen python (Join-Path $env:GONGGONG_RUNTIME_SOURCE 'python/python.exe') 'explicit_runtime_source'
        Add-Candidate $list $seen node (Join-Path $env:GONGGONG_RUNTIME_SOURCE 'node/node.exe') 'explicit_runtime_source'
        Add-Candidate $list $seen git (Join-Path $env:GONGGONG_RUNTIME_SOURCE 'git/cmd/git.exe') 'explicit_runtime_source'
        Add-Candidate $list $seen gh (Join-Path $env:GONGGONG_RUNTIME_SOURCE 'gh/bin/gh.exe') 'explicit_runtime_source'
    }
    return @($list)
}

try {
    . (Join-Path $PSScriptRoot 'gonggong_runtime_policy.ps1')
    Write-AgentProgress 'context' 'Checking the workspace and trusted host prerequisites.'
    if (-not (Test-Path -LiteralPath (Join-Path $root 'CURRENT_FRAMEWORK.json') -PathType Leaf)) {
        throw 'The selected workspace is not a complete GongGong workspace.'
    }
    Write-AgentProgress 'discovery' 'Discovering Python, Node.js, Git and GitHub CLI; each candidate is being executed and probed.'
    $inventory = Get-ValidatedInventory $root
    $inventoryJson = $inventory | ConvertTo-Json -Depth 5 -Compress

    New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
    $operationId = [guid]::NewGuid().ToString('N')
    $run = Join-Path $stateRoot ('agent-' + $operationId)
    New-Item -ItemType Directory -Path $run | Out-Null
    $planFile = Join-Path $run 'plan.json'
    $deploymentOut = Join-Path $run 'deployment.json'
    $inventoryBytes = [Text.UTF8Encoding]::new($false).GetBytes($inventoryJson)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $inventoryHash = ([BitConverter]::ToString($hasher.ComputeHash($inventoryBytes))).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
    $hostPolicy = Read-RuntimeHostPolicy $operationId $inventoryHash
    Write-Json (Join-Path $run 'host-step.json') @{state='policy_verified';policy_hashes=$hostPolicy.hashes;mandate=$hostPolicy.mandate;requested_model=$null;observed_model=$null;provider_started=$false;usage=$null}
    # Installation is permitted only after the trusted host policy is verified.
    if (-not @($inventory | Where-Object { $_.component -eq 'gh' }).Count) {
        Write-AgentProgress 'github_install' 'GitHub CLI is missing. Downloading the pinned official release and verifying its SHA-256 in this workspace.'
        $installer = Join-Path $PSScriptRoot 'install_gonggong_github_cli.ps1'
        $installedGh = & $installer -Workspace $root
        $candidate = Probe-Candidate gh ([string]$installedGh) 'workspace_runtime'
        if (-not $candidate) { throw 'GitHub CLI installation did not produce a working executable.' }
        $inventory = @($inventory) + @($candidate)
    }
    # Bind the selection mandate to the final inventory, including a newly installed gh.
    $inventoryJson = $inventory | ConvertTo-Json -Depth 5 -Compress
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $inventoryHash = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($inventoryJson)))).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
    $hostPolicy = Read-RuntimeHostPolicy $operationId $inventoryHash
    # Stable priority and ordinal path ordering make selection reproducible.
    $priority = @{workspace_runtime=0;session_configuration=1;explicit_runtime_source=2;PATH=3;local_app=4;program_files=5}
    $plan = @{ok=$true;summary='Deterministic host selection of execution-probed runtime paths.';source_runtime=''}
    foreach ($name in @('python','node','git','gh')) {
        $candidates = @($inventory | Where-Object { $_.component -eq $name })
        if (-not $candidates.Count) { throw ('Missing validated runtime component: ' + $name + '. Install it or configure GONGGONG_' + $name.ToUpperInvariant() + ' and retry.') }
        $best = $null
        foreach ($candidate in $candidates) {
            if ($null -eq $best -or $priority[$candidate.origin] -lt $priority[$best.origin] -or
                ($priority[$candidate.origin] -eq $priority[$best.origin] -and [StringComparer]::OrdinalIgnoreCase.Compare($candidate.path, $best.path) -lt 0)) { $best = $candidate }
        }
        $plan[$name] = $best.path
    }
    Write-Json $planFile $plan
    Write-Json (Join-Path $run 'host-step.json') @{state='selection_completed';policy_hashes=$hostPolicy.hashes;mandate=$hostPolicy.mandate;requested_model=$null;observed_model=$null;provider_started=$false;usage=$null;plan=$planFile}
    $allowed = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in $inventory) {
        [void]$allowed.Add(([string]$candidate.component) + '|' + [IO.Path]::GetFullPath([string]$candidate.path))
    }
    foreach ($name in @('python','node','git','gh')) {
        $selected = [string]$plan.$name
        if (-not $selected -or -not $allowed.Contains($name + '|' + [IO.Path]::GetFullPath($selected))) {
            throw ('The host selected a path outside the validated inventory: ' + $name)
        }
    }
    if ([string]$plan.source_runtime) { throw 'The host returned a forbidden runtime source.' }

    Write-AgentProgress 'validation' 'The deterministic plan is ready; the host is enforcing the path allowlist and deploying to this workspace.'
    $configure = Join-Path $PSScriptRoot 'configure_gonggong_runtime.ps1'
    if (-not (Test-Path -LiteralPath $configure -PathType Leaf)) { throw 'The validated runtime deployment script is missing.' }
    $deploy = @{
        Workspace=$root
        Out=$deploymentOut
        Components='python,node,git,gh'
        PythonPath=[string]$plan.python
        NodePath=[string]$plan.node
        GitPath=[string]$plan.git
        GhPath=[string]$plan.gh
        HostSourceRoot=$script:RuntimePolicyHostRoot
    }
    & $configure @deploy
    $deployExit = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $deploymentOut -PathType Leaf)) {
        throw 'The validated runtime deployment script returned no result.'
    }
    $result = Get-Content -LiteralPath $deploymentOut -Raw -Encoding UTF8 | ConvertFrom-Json
    $result | Add-Member -NotePropertyName agent -NotePropertyValue @{
        kind='deterministic-runtime-config'
        independent_from_gonggong=$false
        bootstrap_without_configured_runtime=$true
        registered_framework_agent=$false
        operation_id=$operationId
        policy_hashes=$hostPolicy.hashes
        provider_started=$false
        provider_completed=$false
        requested_model=$null
        observed_model=$null
        usage=$null
        read_only_discovery=$true
        summary=[string]$plan.summary
        plan=$planFile
    } -Force
    if ($deployExit -ne 0 -or -not $result.ok) {
        Write-Json $outFile $result
        Write-AgentProgress 'failed' ([string]$result.error)
        exit 1
    }
    Write-AgentProgress 'self_check' 'Runtime probes passed. Checking GitHub login and read-only repository access.'
    $githubOut = Join-Path $run 'github.json'
    # Deployment is already committed locally. Optional GitHub diagnostics must
    # never discard its paths or rollback receipt when the checker fails.
    try {
        & (Join-Path $PSScriptRoot 'check_gonggong_github.ps1') -Workspace $root -Gh ([string]$result.gh) -Out $githubOut
        if (-not (Test-Path -LiteralPath $githubOut -PathType Leaf)) { throw 'github_check_result_missing' }
        $github = Get-Content -LiteralPath $githubOut -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $github -or $github -is [Array] -or $github.ok -isnot [bool]) { throw 'github_check_result_invalid' }
    } catch {
        $github = @{ok=$false;authenticated=$false;repository_access=$false;action_required=$true;error='github_check_failed';detail=$_.Exception.Message}
    }
    $result | Add-Member -NotePropertyName github -NotePropertyValue $github -Force
    Write-Json $outFile $result
    if ($github.ok) {
        Write-AgentProgress 'completed' 'Runtime probes, GitHub login and read-only repository access all passed.'
    } else {
        Write-AgentProgress 'github_action_required' ('Runtimes are ready; GitHub needs attention: ' + $github.error)
    }
} catch {
    Write-AgentProgress 'failed' $_.Exception.Message
    Write-Json $outFile @{
        ok=$false
        state='setup_failed'
        error=$_.Exception.Message
        global_environment_changed=$false
        agent=@{kind='deterministic-runtime-config';independent_from_gonggong=$false;registered_framework_agent=$false;read_only_discovery=$true;policy_verified=($null -ne $hostPolicy);provider_started=$providerStarted;provider_completed=$providerCompleted;usage=$null}
    }
    exit 1
}
