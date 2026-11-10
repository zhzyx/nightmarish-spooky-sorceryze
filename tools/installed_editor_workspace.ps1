function Get-EditorGit([string]$Workspace) {
    $bundled = Join-Path $Workspace 'project/runtime/git/cmd/git.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) { return $bundled }
    return 'git'
}

# Linked worktrees share the installation of their primary working tree.
function Get-EditorWorkspace([string]$Checkout) {
    if (-not (Test-Path -LiteralPath (Join-Path $Checkout '.git'))) { return $Checkout }
    $git = Get-EditorGit $Checkout
    $common = & $git -C $Checkout rev-parse --path-format=absolute --git-common-dir
    if ($LASTEXITCODE -ne 0 -or -not $common) { throw 'Cannot resolve the primary editor installation.' }
    if ((Split-Path -Leaf $common) -ne '.git') { throw 'Expected a non-bare primary checkout.' }
    return (Get-Item -Force -LiteralPath $common).Parent.FullName
}

function Get-EditorDigest([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    try {
        $hash = [Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $hash.Dispose() }
    } finally { $stream.Dispose() }
}
