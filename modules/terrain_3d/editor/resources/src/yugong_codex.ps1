# Windows PowerShell 5 compatible. Keep the editor environment and console untouched.
param([Parameter(Mandatory=$true)][string]$JobDirectory, [int]$EditorId)
$ErrorActionPreference = 'Stop'
$child = $null
try {
    $editorProcess = Get-Process -Id $EditorId
    $job = [IO.File]::ReadAllText((Join-Path $JobDirectory 'launch.json')) | ConvertFrom-Json
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $program = Get-Command $job.program -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($program) {
        $info.FileName = $program.Source
    } elseif ($job.program -eq 'codex.exe') {
        # Desktop installations may expose their CLI only inside a Codex session.
        $cli = $env:CODEX_APP_RUNTIME_CLI_PATH
        if (-not $cli -or -not [IO.File]::Exists($cli)) {
            $bin = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'OpenAI/Codex/bin'
            $cli = Get-ChildItem -LiteralPath $bin -Directory -ErrorAction SilentlyContinue |
                Where-Object { -not $_.Name.StartsWith('.') } |
                ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'codex.exe') -ErrorAction SilentlyContinue } |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
        }
        if (-not $cli) { exit 1 }
        $info.FileName = $cli
    } else {
        exit 1
    }
    $info.WorkingDirectory = $JobDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    # Standard Windows argv quoting. ProcessStartInfo launches the executable directly.
    $quoted = foreach ($argValue in $job.arguments) {
        $escaped = [regex]::Replace([string]$argValue, '(\\*)"', '$1$1\"')
        '"' + [regex]::Replace($escaped, '(\\+)$', '$1$1') + '"'
    }
    $info.Arguments = $quoted -join ' '
    foreach ($key in @($info.EnvironmentVariables.Keys)) {
        if ($key -like 'CODEX_*' -and $key -notin @('CODEX_HOME','CODEX_CA_CERTIFICATE','CODEX_CA_CERTIFICATES','CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY')) {
            $info.EnvironmentVariables.Remove($key)
        }
    }
    if (-not $info.EnvironmentVariables['HTTPS_PROXY']) {
        $proxy = [string]$job.proxy
        if (-not $proxy) {
            $service = [uri]'https://chatgpt.com/'
            $systemProxy = [Net.WebRequest]::GetSystemWebProxy().GetProxy($service)
            if ($systemProxy -and $systemProxy -ne $service) { $proxy = $systemProxy.AbsoluteUri }
        }
        if ($proxy) { $info.EnvironmentVariables['HTTPS_PROXY'] = $proxy }
    }
    $child = [Diagnostics.Process]::Start($info)
    $child.StandardInput.Close()
    while (-not $child.WaitForExit(200)) {
        if ($editorProcess.HasExited -or (Test-Path -LiteralPath (Join-Path $JobDirectory 'cancel'))) {
            $child.Kill()
            $child.WaitForExit()
            exit 2
        }
    }
    exit $child.ExitCode
} catch {
    exit 1
} finally {
    if ($child) { $child.Dispose() }
    if ((Test-Path -LiteralPath (Join-Path $JobDirectory 'cancel')) -or ($editorProcess -and $editorProcess.HasExited)) {
        foreach ($name in @('schema.json','result.json','reference.png','launch.json','cancel')) {
            $path = Join-Path $JobDirectory $name
            if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) }
        }
        if ([IO.Directory]::Exists($JobDirectory) -and [IO.Directory]::GetFileSystemEntries($JobDirectory).Count -eq 0) {
            [IO.Directory]::Delete($JobDirectory)
        }
    }
}
