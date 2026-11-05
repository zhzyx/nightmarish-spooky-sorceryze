[CmdletBinding()]
param(
    [string]$Repo,
    [int]$Issue,
    [string]$RequestId,
    [string]$Tenant = 'gonggong-workspace',
    [string]$BaseRef = 'origin/main',
    [string]$Python = $env:GONGGONG_PYTHON,
    [switch]$IntakeOnly,
    [switch]$ProbeOnly
)
$ErrorActionPreference = 'Stop'
if (-not $PSBoundParameters.ContainsKey('Repo')) {
    $Repo = Split-Path $PSScriptRoot -Parent
}
$root = (Resolve-Path -LiteralPath $Repo).Path
function Test-Python([string]$Candidate) {
    if (-not $Candidate -or $Candidate -match '[\\/]WindowsApps[\\/]' -or
        -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $false }
    try {
        $probe = & $Candidate -I -c "import sys,json,hashlib,subprocess; assert sys.version_info >= (3,11); print('gonggong-python-ok')" 2>$null
        return ($LASTEXITCODE -eq 0 -and $probe -eq 'gonggong-python-ok')
    } catch { return $false }
}
if ($Python) {
    if (-not (Test-Python $Python)) { throw 'PYTHON_RUNTIME: explicit interpreter failed Python 3.11+ probe; correct -Python or GONGGONG_PYTHON' }
} else {
    $common = & git -C $root rev-parse --path-format=absolute --git-common-dir
    if ($LASTEXITCODE -ne 0) { throw 'GIT_REPOSITORY: cannot resolve worktree; select the intended repository' }
    $candidates = @((Join-Path $root 'project/runtime/python/python.exe'),
        (Join-Path (Split-Path $common -Parent) 'project/runtime/python/python.exe'))
    $candidates += @(Get-Command python,python3 -CommandType Application -All -ErrorAction SilentlyContinue | ForEach-Object Source)
    if ($env:LOCALAPPDATA) { $candidates += Join-Path $env:LOCALAPPDATA 'Python/bin/python.exe' }
    if ($env:USERPROFILE) { $candidates += Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Python $candidate) { $Python = $candidate; break }
    }
    if (-not $Python) { throw 'PYTHON_RUNTIME: no working Python 3.11+ found; supply -Python; WindowsApps aliases are excluded' }
}
if ($ProbeOnly) {
    [ordered]@{python=$Python; repo=$root; state='runtime_verified'} | ConvertTo-Json
    exit 0
}
if ($Issue -lt 1 -or -not $RequestId) { throw 'ISSUE_BINDING: -Issue and -RequestId are required' }
$headCommit = & git -C $root rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'GIT_REPOSITORY: cannot read HEAD' }
Write-Verbose "Candidate repository=$root HEAD=$headCommit Python=$Python base=$BaseRef"
$gateArgs = @('-X', 'utf8', (Join-Path $root 'customizations/components/issue-workorders/issue_gate.py'),
    '--repo', $root, '--issue', $Issue, '--request-id', $RequestId, '--base-ref', $BaseRef)
if ($IntakeOnly) { $gateArgs += @('--intake-only', '--tenant', $Tenant) }
& $Python @gateArgs
exit $LASTEXITCODE
