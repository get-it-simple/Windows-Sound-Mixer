param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [string]$Repository = "get-it-simple/Windows-Sound-Mixer"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$release = Join-Path $root "dist\release"
$winget = Join-Path $root "dist\winget"
$portableSource = Join-Path $root "dist\SoundMixer.exe"
$portableTarget = Join-Path $release "SoundMixer-$Version-x64.exe"

New-Item -ItemType Directory -Path $release -Force | Out-Null
Copy-Item -LiteralPath $portableSource -Destination $portableTarget -Force

foreach ($scope in @("user", "machine")) {
    $name = "SoundMixer-$Version-x64-$scope-setup.exe"
    Copy-Item -LiteralPath (Join-Path $root "dist\installers\$name") -Destination (Join-Path $release $name) -Force
}

& (Join-Path $PSScriptRoot "generate-winget-manifests.ps1") -Version $Version -AssetsDirectory "dist\release" -OutputDirectory "dist\winget" -Repository $Repository

$zip = Join-Path $release "GetItSimple.SoundMixer-$Version-winget.zip"
Compress-Archive -Path (Join-Path $winget "*.yaml") -DestinationPath $zip -Force
$hashLines = Get-ChildItem -LiteralPath $release -File | Where-Object Name -ne "SHA256SUMS.txt" | Sort-Object Name | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
}
[System.IO.File]::WriteAllLines((Join-Path $release "SHA256SUMS.txt"), $hashLines, [System.Text.UTF8Encoding]::new($false))

Get-ChildItem -LiteralPath $release -File | Sort-Object Name | Select-Object Name, Length
