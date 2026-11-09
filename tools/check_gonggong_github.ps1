[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Gh,
    [Parameter(Mandatory=$true)][string]$Out,
    [switch]$Login
)

$ErrorActionPreference = 'Stop'
$result = @{ok=$false;authenticated=$false;repository_access=$false;error='gh_unavailable'}
try {
    if (-not (Test-Path -LiteralPath $Gh -PathType Leaf)) { throw 'gh_unavailable' }
    $ErrorActionPreference = 'Continue'
    $status = & $Gh auth status --hostname github.com 2>&1
    $statusExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($Login -and $statusExit -ne 0) {
        $ErrorActionPreference = 'Continue'
        & $Gh auth login --hostname github.com --git-protocol https --web
        $loginExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($loginExit -ne 0) { throw 'gh_unauthenticated' }
        $ErrorActionPreference = 'Continue'
        $status = & $Gh auth status --hostname github.com 2>&1
        $statusExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
    }
    if ($statusExit -ne 0) { throw 'gh_unauthenticated' }
    $result.authenticated = $true
    $settings = Get-Content -LiteralPath (Join-Path $Workspace 'work-items.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $repository = [string]$settings.repository
    if ($repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'github_repository_not_configured' }
    $ErrorActionPreference = 'Continue'
    $repositoryJson = & $Gh api ("repos/$repository") --method GET --jq '{full_name,has_issues}' 2>$null
    $repositoryExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($repositoryExit -ne 0) { throw 'github_repository_unavailable' }
    $remote = ($repositoryJson -join "`n") | ConvertFrom-Json
    if ($remote.full_name -ine $repository) { throw 'github_repository_mismatch' }
    if ($remote.has_issues -eq $false) { throw 'repository_issues_disabled' }
    $result.ok = $true
    $result.repository_access = $true
    $result.repository = $repository
    $result.error = ''
} catch {
    $result.error = $_.Exception.Message
}
$parent = Split-Path -Parent ([IO.Path]::GetFullPath($Out))
New-Item -ItemType Directory -Force -Path $parent | Out-Null
[IO.File]::WriteAllText($Out, ($result | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
if (-not $result.ok) { exit 1 }
