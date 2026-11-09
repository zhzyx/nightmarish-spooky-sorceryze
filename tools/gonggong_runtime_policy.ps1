# Trusted installed-host context for one bounded model data-selection step.
# These hashes are part of the reviewed host implementation, not a workspace lock.
$script:RuntimePolicyHostRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:RuntimePolicyPins = @'
{
  "CURRENT_FRAMEWORK.json": "451d14611bbb451e5ec183a3c40bb2e27057e8a8c4a6f507c391e2c9c154f83b",
  "framework/framework-manifest.json": "2235d4517f951c9bedc7d05c651b8c9f1df45a4516ebc1d741b25fa2a2a0dd07",
  "framework/foundation.lock.json": "deb2b662be355e3357a55acecc9e5946830c36571d800346ff7d712d720a999c",
  "framework/FOUNDATION.md": "af0b14934f8998ac7e751475f8192f52adbeb3a26e3d709ee083bcbfeb42148f",
  "framework/AGENTS.md": "359b2243eb576a4fbde944c0d23d7b434797c2643f885f707f9dc3a73e2dd2cc",
  "framework/GOVERNANCE.md": "7e4dbfeaf5e407be43247717a6b7cb6743757b446813ca4b7b128c6dbb377724",
  "framework/specs/model-runtime.md": "a25cb86c8c4f8ec479e34a9e131c280680ba06280d0fd1e02f7e275b936a0e6a",
  "framework/upstream/yuanheng/core.md": "13baad2a5bcf0ff72c10fd2cc7481894179e66f03617e2db0f1221694073c202",
  "framework/upstream/yuanheng/agents/yuanheng.md": "bb2eb701555ee0d391efcb013075f3bd9e59ba1648e18b8a400a29794db4c00b",
  "customizations/components/godot-host/README.md": "66a0acf47cbef976d4572bfd4e8f7e3bbb26e534e41860c20db435c880d1c434"
}
'@ | ConvertFrom-Json

function Read-RuntimeHostPolicy([string]$OperationId, [string]$InventoryHash) {
    if ($OperationId -notmatch '^[a-f0-9]{32}$' -or $InventoryHash -notmatch '^[a-f0-9]{64}$') {
        throw 'Invalid runtime-selection host operation binding.'
    }
    $texts = @{}
    $hashes = [ordered]@{}
    $hostRoot = $script:RuntimePolicyHostRoot.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))
    $prefix = $hostRoot + [IO.Path]::DirectorySeparatorChar
    foreach ($property in $script:RuntimePolicyPins.PSObject.Properties) {
        $relative = $property.Name
        $file = [IO.Path]::GetFullPath((Join-Path $hostRoot $relative))
        if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Host policy path escaped its installation.' }
        $cursor = $file
        while ($cursor -and $cursor.Length -ge $hostRoot.Length) {
            if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked host policy sources are not supported.' }
            $cursor = Split-Path -Parent $cursor
        }
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw ('Trusted host policy source is missing: ' + $relative) }
        $stream = [IO.File]::OpenRead($file)
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $actual = ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $stream.Dispose(); $algorithm.Dispose() }
        if ($actual -ne [string]$property.Value) { throw ('Trusted host policy changed; revalidate this host release: ' + $relative) }
        $hashes[$relative] = $actual
        $texts[$relative] = [IO.File]::ReadAllText($file, [Text.UTF8Encoding]::new($false, $true))
    }
    $pointer = $texts['CURRENT_FRAMEWORK.json'] | ConvertFrom-Json
    if ($pointer.path_base -ne 'this_file_directory' -or $pointer.root -ne 'framework' -or $pointer.manifest -ne 'framework-manifest.json' -or $pointer.version -ne '0.10.0') { throw 'Host current-framework binding changed.' }
    $foundation = $texts['framework/foundation.lock.json'] | ConvertFrom-Json
    if ($foundation.state -ne 'frozen' -or $foundation.foundation -ne 'FOUNDATION.md' -or $foundation.sha256 -ne $hashes['framework/FOUNDATION.md']) { throw 'Host frozen foundation binding changed.' }
    $mandate = [ordered]@{
        operation_id=$OperationId
        source='invoking_editor_runtime_setup_operation'
        responsibility='existing editor/operator host; this is a bounded structured selection step, not a newly admitted independent Agent'
        scope='select exactly one already-probed path per component from this inventory'
        inventory_sha256=$InventoryHash
        tools=@()
        writes=@()
        delegation=$false
        publication_authority=$false
        framework_operation_authority=$false
        consumption='one provider invocation; no automatic retry; actual usage unknown'
        acceptance='existing host revalidates paths and alone applies the original user-requested setup'
    }
    $context = ''
    foreach ($name in @('framework/upstream/yuanheng/core.md','framework/upstream/yuanheng/agents/yuanheng.md','framework/FOUNDATION.md','framework/AGENTS.md','framework/GOVERNANCE.md','framework/specs/model-runtime.md','customizations/components/godot-host/README.md')) {
        $context += "`n--- VERIFIED HOST POLICY: $name ---`n" + $texts[$name] + "`n"
    }
    $context += "`n--- CURRENT HOST STEP MANDATE ---`n" + ($mandate | ConvertTo-Json -Depth 8)
    return @{context=$context;hashes=$hashes;mandate=$mandate;trusted_basis='pinned installed-host implementation; workspace lock alone is not authority'}
}
