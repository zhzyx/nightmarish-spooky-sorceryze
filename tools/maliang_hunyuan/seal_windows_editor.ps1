# Include a portable extractor so a stock Windows install can open the private package.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$EditorDirectory,
    [Parameter(Mandatory)][string]$Destination,
    [Parameter(Mandatory)][string]$RecipientModulus
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $EditorDirectory).Path
$dest = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $dest) { throw 'Use a new delivery directory.' }
$model = Join-Path $source 'maliang-hunyuan/models/checkpoints/hunyuan3d-mini.safetensors'
if (!(Test-Path -LiteralPath $model -PathType Leaf) -or !(Test-Path "$source/*.exe" -PathType Leaf)) {
    throw 'The accepted Windows distribution must contain its model and editor.'
}
$sevenZip = (Get-Command 7z.exe -CommandType Application).Source
$sevenZipDirectory = [IO.Path]::GetDirectoryName($sevenZip)
$parameters = [Security.Cryptography.RSAParameters]::new()
$parameters.Modulus = [Convert]::FromBase64String($RecipientModulus)
$parameters.Exponent = [byte[]](1,0,1)
if ($parameters.Modulus.Length -notin 256,384,512) { throw 'Use a 2048, 3072 or 4096 bit RSA recipient key.' }
$rsa = [Security.Cryptography.RSA]::Create()
try {
    $rsa.ImportParameters($parameters)
    $password = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(16))
    $wrapped = $rsa.Encrypt([Text.Encoding]::ASCII.GetBytes($password), [Security.Cryptography.RSAEncryptionPadding]::OaepSHA256)
} finally {
    $rsa.Dispose()
}
New-Item -ItemType Directory -Path $dest | Out-Null
$extractor = New-Item -ItemType Directory -Path "$dest/extract"
foreach ($file in @('7z.exe','7z.dll','License.txt')) {
    Copy-Item -LiteralPath (Join-Path $sevenZipDirectory $file) -Destination $extractor.FullName
}
Set-Content "$extractor/SOURCE.txt" -Encoding ascii -Value '7-Zip by Igor Pavlov. Source code: https://www.7-zip.org/download.html'
Copy-Item -LiteralPath "$PSScriptRoot/Start-Maliang.cmd" -Destination $dest
$archive = Join-Path $dest 'Maliang-Windows-x64.7z'
Push-Location -LiteralPath $source
try {
    & $sevenZip a -t7z -mx=1 -mhe=on -bso0 -bsp0 "-p$password" $archive '.'
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Windows package failed.' }
    & $sevenZip t -bso0 -bsp0 "-p$password" $archive
    if ($LASTEXITCODE -ne 0) { throw 'The Windows package failed its integrity test.' }
} finally {
    Pop-Location
}
[ordered]@{
    archive = [IO.Path]::GetFileName($archive)
    sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    bytes = (Get-Item -LiteralPath $archive).Length
    wrapped_password = [Convert]::ToBase64String($wrapped)
    password_wrapping = 'RSA-OAEP-SHA256'
} | ConvertTo-Json | Set-Content "$dest/delivery.json" -Encoding utf8NoBOM
