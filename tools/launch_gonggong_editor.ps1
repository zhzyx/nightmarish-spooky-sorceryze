[CmdletBinding()]
param([string]$Python, [string]$Node, [string]$Project, [switch]$Probe, [switch]$Console, [switch]$ProjectManager)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'installed_editor_workspace.ps1')
$workspace = Get-EditorWorkspace (Split-Path -Parent $PSScriptRoot)
if (-not $Python) { $Python = $env:GONGGONG_PYTHON }
if (-not $Python -and (Test-Path -LiteralPath (Join-Path $workspace 'project/runtime/python/python.exe'))) { $Python = Join-Path $workspace 'project/runtime/python/python.exe' }
if (-not $Python) {
    $found = Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $Python = $found.Source }
}
$missing = @()
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) { $missing += 'Python'; $Python = '' }
if (-not $Node) { $Node = $env:GONGGONG_NODE }
if (-not $Node -and (Test-Path -LiteralPath (Join-Path $workspace 'project/runtime/node/node.exe'))) { $Node = Join-Path $workspace 'project/runtime/node/node.exe' }
if (-not $Node) {
    $found = Get-Command node -ErrorAction SilentlyContinue
    if ($found) { $Node = $found.Source }
}
if (-not $Node -or -not (Test-Path -LiteralPath $Node -PathType Leaf)) { $missing += 'Node.js'; $Node = '' }
$installation = Join-Path $workspace 'project/godot'
$inventory = Get-Content -LiteralPath (Join-Path $installation 'installed.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$gui = 'bin/godot.windows.editor.x86_64.exe'
$consolePath = 'bin/godot.windows.editor.x86_64.console.exe'
if ($inventory.default_editor -ne $gui) { throw 'Unexpected installed editor path.' }
if ($inventory.schema_version -eq 2 -and $inventory.console_editor -eq $gui) { $consolePath = $gui }
$required = @($gui)
if ($consolePath -ne $gui) { $required += $consolePath }
$hasGit = Test-Path -LiteralPath (Join-Path $workspace '.git')
if ($hasGit -or $inventory.schema_version -eq 2) {
    if ($inventory.schema_version -ne 2 -or $inventory.main_revision -notmatch '^[a-f0-9]{40}$') {
        throw 'Reinstall the verified main editor using tools/install_gonggong_editor.ps1.'
    }
    if ($hasGit) {
        $git = Get-EditorGit $workspace
        $base = $inventory.main_revision
        $snapshot = & $git -C $workspace config --local --get gonggong.releaseSnapshot
        if ($snapshot) {
            $bundle = Get-Content -LiteralPath (Join-Path $workspace 'bundle-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($bundle.source_commit -ne $base) { throw 'Installed editor differs from the release snapshot.' }
            $base = $snapshot
        }
        & $git -C $workspace diff --quiet $base HEAD -- . ':(exclude)design-docs' ':(exclude)data-collection' ':(exclude)gonggong-diting-data' ':(exclude)*.md'
        if ($LASTEXITCODE -ne 0) {
            throw 'The installed editor differs from this checkout. Run tools/install_gonggong_editor.ps1 for current main.'
        }
    }
    $required += 'bin/tianshu-ui.json'
    $required += @($inventory.files | Where-Object { $_.path -match '^bin/[a-zA-Z0-9_.-]+[.]dll$' } | ForEach-Object path)
}
foreach ($name in $required) {
    $file = @($inventory.files | Where-Object { $_.path -eq $name })
    if ($file.Count -ne 1 -or (Get-EditorDigest (Join-Path $installation $name)) -ne $file[0].sha256) {
        throw "Installed editor inventory check failed: $name"
    }
}
$editor = if ($Console) { Join-Path $installation $consolePath } else { Join-Path $installation $gui }
$env:GONGGONG_WORKSPACE = $workspace
$env:GONGGONG_PYTHON = $Python
$env:GONGGONG_NODE = $Node
$localGit = Join-Path $workspace 'project/runtime/git/cmd'
if (Test-Path -LiteralPath (Join-Path $localGit 'git.exe')) { $env:PATH = $localGit + [IO.Path]::PathSeparator + $env:PATH }
$arguments = @()
if (-not $ProjectManager -or $Project) {
    if (-not $Project) { $Project = Join-Path $workspace 'samples/gonggong-workbench' }
    if (-not (Test-Path -LiteralPath $Project -PathType Container)) { throw "Project directory not found: $Project" }
    $arguments = @('--editor', '--path', $Project)
}
if ($Probe) {
    [pscustomobject]@{Editor=$editor;Workspace=$workspace;Python=$Python;Node=$Node;Project=$Project;Missing=$missing;Arguments=$arguments;MainRevision=$inventory.main_revision}
    exit 0
}
& $editor @arguments
exit $LASTEXITCODE
