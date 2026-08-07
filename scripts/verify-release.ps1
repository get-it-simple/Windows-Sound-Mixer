param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [string]$ReleaseDirectory = "dist\release",
    [string]$ManifestDirectory = "dist\winget"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$release = [System.IO.Path]::GetFullPath((Join-Path $root $ReleaseDirectory))
$manifests = [System.IO.Path]::GetFullPath((Join-Path $root $ManifestDirectory))
$sumPath = Join-Path $release "SHA256SUMS.txt"
$expectedFiles = @(Get-ChildItem -LiteralPath $release -File | Where-Object Name -ne "SHA256SUMS.txt" | Sort-Object Name)
$sumLines = @(Get-Content -LiteralPath $sumPath)

if ($sumLines.Count -ne $expectedFiles.Count) {
    throw "SHA256SUMS.txt does not contain exactly one entry per release asset."
}

foreach ($file in $expectedFiles) {
    $line = $sumLines | Where-Object { $_ -match "^[0-9a-f]{64}  $([regex]::Escape($file.Name))$" }
    if (@($line).Count -ne 1) {
        throw "Missing or duplicate checksum entry for $($file.Name)"
    }
    $expectedHash = $line.Substring(0, 64)
    $actualHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Checksum mismatch for $($file.Name)"
    }
}

$manifestFiles = @(Get-ChildItem -LiteralPath $manifests -Filter "*.yaml" -File)
if ($manifestFiles.Count -ne 4) {
    throw "The WinGet bundle must contain exactly four YAML manifests."
}
$installerManifest = Get-Content -LiteralPath (Join-Path $manifests "GetItSimple.SoundMixer.installer.yaml") -Raw
$name = "SoundMixer-$Version-x64-machine-setup.exe"
$actualHash = (Get-FileHash -LiteralPath (Join-Path $release $name) -Algorithm SHA256).Hash
$pattern = "InstallerUrl:\s+\S+/$([regex]::Escape($name))\r?\n\s+InstallerSha256:\s+([0-9A-Fa-f]{64})"
$match = [regex]::Match($installerManifest, $pattern)
if (-not $match.Success -or $match.Groups[1].Value -ne $actualHash) {
    throw "WinGet hash mismatch for the machine installer."
}

Write-Host "Release checksums and WinGet installer hashes are consistent."
