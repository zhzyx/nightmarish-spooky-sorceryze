[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Out,
    [string]$SourceRuntime,
    [string]$Components = 'python,node,git',
    [string]$PythonPath,
    [string]$NodePath,
    [string]$GitPath,
    [string]$GhPath,
    [string]$HostSourceRoot,
    [string]$Rollback
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($Workspace)
$runtime = Join-Path $root 'project/runtime'
$entries = @{python='python/python.exe'; node='node/node.exe'; git='git/cmd/git.exe'; gh='gh/bin/gh.exe'}
$provided = @{python=$PythonPath; node=$NodePath; git=$GitPath; gh=$GhPath}
$changed = @()
$receipt = $null
function Assert-Within([string]$Path, [string]$Base) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Base).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path leaves deployment boundary' }
    $cursor = $full
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked deployment paths are not supported' }
        $parent = Split-Path -Parent $cursor
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}
function Write-Json([string]$Path, $Value) {
    # Replace a complete same-directory journal; never expose a truncated JSON receipt.
    $temporary = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 12))
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
        finally { $stream.Dispose() }
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    }
}
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
function Probe([string]$Name, [string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
    if ($Name -eq 'python') { $result = & $Path -I -c 'import sys,ssl,sqlite3,json,hashlib,subprocess; assert sys.version_info >= (3,10); print(sys.version)' 2>&1 }
    else { $result = & $Path --version 2>&1 }
    return $LASTEXITCODE -eq 0
    } catch { return $false }
}
function Restore($Records, [string]$Folder) {
    $folderPath = Assert-Within $Folder (Join-Path $runtime '.gonggong-setup')
    $seen = @{}
    # Validate every path before withdrawing any component, including absent backups.
    foreach ($item in @($Records)) {
        if (-not $entries.ContainsKey([string]$item.name) -or $seen.ContainsKey([string]$item.name)) { throw 'Invalid deployment component record' }
        $seen[[string]$item.name] = $true
        $target = Assert-Within $item.target $runtime
        if ($target -ne (Join-Path $runtime $item.name)) { throw 'Unexpected deployment target' }
        if ($item.backup) {
            $backup = Assert-Within $item.backup $folderPath
            if ($backup -ne (Join-Path $folderPath ($item.name + '-previous'))) { throw 'Unexpected deployment backup' }
            if (-not (Test-Path -LiteralPath $backup) -and $item.phase -ne 'prepared') { throw 'Original runtime backup is missing; retain files for recovery' }
        }
        if ($item.phase -and $item.phase -notin @('prepared','deployed')) { throw 'Unsupported deployment journal phase' }
    }
    for ($index = $Records.Count - 1; $index -ge 0; $index--) {
        $item = $Records[$index]
        $target = $item.target
        # A prepared record precedes moving the original. If its backup is absent,
        # the original destination must be preserved. Existing configured receipts
        # without a phase retain their previous deployed-record semantics.
        if ($item.backup -and -not (Test-Path -LiteralPath $item.backup)) { continue }
        if (Test-Path -LiteralPath $target) {
            $retained = Join-Path $folderPath ($item.name + '-withdrawn-' + [guid]::NewGuid().ToString('N'))
            Move-Item -LiteralPath $target -Destination $retained
        }
        if ($item.backup) { Move-Item -LiteralPath $item.backup -Destination $target }
    }
}
try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'CURRENT_FRAMEWORK.json'))) { throw 'Select the GongGong workspace containing CURRENT_FRAMEWORK.json' }
    if ($Rollback) {
        $file = Assert-Within $Rollback (Join-Path $runtime '.gonggong-setup')
        $prior = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($prior.workspace -ne $root -or $prior.state -notin @('configured','deploying')) { throw 'No matching active deployment to roll back' }
        if (@($prior.changed).Count) { Restore @($prior.changed) (Split-Path -Parent $file) }
        $prior.state = 'rolled_back'; Write-Json $file $prior
        Write-Json $Out @{ok=$true;state='rolled_back';receipt=$file;global_environment_changed=$false}
        exit 0
    }
    $selected = @($Components.Split(',') | Where-Object { $_ })
    if ($selected.Count -eq 0 -or @($selected | Where-Object { -not $entries.ContainsKey($_) }).Count) { throw 'Choose python, node, git, or gh' }
    $transaction = Assert-Within (Join-Path $runtime ('.gonggong-setup/' + [guid]::NewGuid().ToString('N'))) $root
    New-Item -ItemType Directory -Force -Path $transaction | Out-Null
    $receipt = Join-Path $transaction 'receipt.json'
    Write-Json $receipt @{state='deploying';workspace=$root;changed=$changed;journal_version=1}
    $paths = @{}
    $required = @('python','node','git')
    if ('gh' -in $selected -or $GhPath) { $required += 'gh' }
    foreach ($name in $required) {
        $local = Join-Path $runtime $entries[$name]
        if (Probe $name $local) { $paths[$name] = $local; continue }
        if ($provided[$name]) {
            $candidate = [IO.Path]::GetFullPath($provided[$name])
            if (-not (Probe $name $candidate)) { throw ('AI-selected component failed execution check: ' + $name) }
            $paths[$name] = $candidate
            continue
        }
        if (-not $SourceRuntime) {
            $command = Get-Command ($name + '.exe') -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($command -and (Probe $name $command.Source)) { $paths[$name] = $command.Source; continue }
        }
        if ($name -notin $selected) { throw ('Missing unselected component: ' + $name) }
        if (-not $SourceRuntime) { throw ('Missing ' + $name + ': choose the project/runtime directory from an extracted complete GongGong Windows package') }
        $source = [IO.Path]::GetFullPath($SourceRuntime)
        if ($source.TrimEnd('\','/') -eq ([IO.Path]::GetFullPath($runtime)).TrimEnd('\','/')) { throw 'The selected runtime is incomplete; choose another complete package' }
        $manifest = Get-Content -LiteralPath (Join-Path $source 'installed.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifest.schema_version -ne 1 -or $manifest.path_base -ne 'runtime_directory') { throw 'Unsupported source runtime manifest' }
        $records = @($manifest.files | Where-Object { $_.path.StartsWith($name + '/') })
        if (-not @($records | Where-Object { $_.path -eq $entries[$name] }).Count) { throw ('Source package lacks ' + $name) }
        $stage = Join-Path $transaction ($name + '-staged')
        New-Item -ItemType Directory -Path $stage | Out-Null
        foreach ($record in $records) {
            $original = Assert-Within (Join-Path $source $record.path) $source
            if ((Hash $original) -ne $record.sha256) { throw ('Runtime checksum mismatch: ' + $record.path) }
            $relative = $record.path.Substring($name.Length + 1)
            $target = Assert-Within (Join-Path $stage $relative) $stage
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $original -Destination $target
            if ((Hash $target) -ne $record.sha256) { throw 'Staged runtime checksum mismatch' }
        }
        $binary = Join-Path $stage $entries[$name].Substring($name.Length + 1)
        if (-not (Probe $name $binary)) { throw ('Staged component failed execution check: ' + $name) }
        $destination = Assert-Within (Join-Path $runtime $name) $runtime
        $backup = ''
        if (Test-Path -LiteralPath $destination) { $backup=Join-Path $transaction ($name+'-previous') }
        $item = @{name=$name;target=$destination;backup=$backup;phase='prepared';source_manifest_sha256=(Hash (Join-Path $source 'installed.local.json'));files=$records}
        $changed += $item
        # Journal the intended mutation before moving either the old or staged tree.
        Write-Json $receipt @{state='deploying';workspace=$root;changed=$changed;journal_version=1}
        if ($backup) { Move-Item -LiteralPath $destination -Destination $backup }
        Move-Item -LiteralPath $stage -Destination $destination
        $item.phase = 'deployed'
        Write-Json $receipt @{state='deploying';workspace=$root;changed=$changed;journal_version=1}
        $paths[$name] = Join-Path $runtime $entries[$name]
    }
    $env:GONGGONG_PYTHON=$paths.python; $env:GONGGONG_NODE=$paths.node; $env:GONGGONG_GIT=$paths.git
    if ($paths.gh) { $env:GONGGONG_GH=$paths.gh }
    $env:PATH=(Split-Path -Parent $paths.node)+';'+(Split-Path -Parent $paths.git)+';'+$env:PATH
    $doctorScript = Join-Path $root 'tools/gonggong_bridge.py'
    if ($HostSourceRoot) {
        if (-not [IO.Path]::IsPathRooted($HostSourceRoot)) { throw 'Host source root must be absolute' }
        $doctorScript = Assert-Within (Join-Path $HostSourceRoot 'tools/gonggong_bridge.py') $HostSourceRoot
    }
    $doctor = & $paths.python -X utf8 $doctorScript doctor --workspace $root 2>&1
    if ($LASTEXITCODE -ne 0) { throw ('Runtime probes passed; framework self-check did not pass. ' + ($doctor -join "`n")) }
    if ($receipt) { Write-Json $receipt @{state='configured';workspace=$root;changed=$changed;journal_version=1;paths=$paths;global_environment_changed=$false} }
    Write-Json $Out @{ok=$true;state='configured';python=$paths.python;node=$paths.node;git=$paths.git;gh=$paths.gh;receipt=$receipt;changed=$changed;global_environment_changed=$false;chat_verified=$false}
} catch {
    $failure=$_.Exception.Message
    $rollbackState='not_needed'
    if ($changed.Count) {
        try { Restore $changed (Split-Path -Parent $receipt); $rollbackState='restored' }
        catch { $rollbackState='needs_recovery'; $failure += "`nRollback: " + $_.Exception.Message }
    }
    if ($receipt) { Write-Json $receipt @{state='failed';workspace=$root;changed=$changed;journal_version=1;error=$failure;rollback=$rollbackState} }
    Write-Json $Out @{ok=$false;state='repair_environment';error=$failure;receipt=$receipt;rollback=$rollbackState;global_environment_changed=$false}
    exit 1
}
