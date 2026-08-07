param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,
    [string]$AssetsDirectory = "dist\release",
    [string]$OutputDirectory = "dist\winget",
    [string]$Repository = "get-it-simple/Windows-Sound-Mixer",
    [string]$ReleaseDate = (Get-Date -Format "yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$assets = [System.IO.Path]::GetFullPath((Join-Path $root $AssetsDirectory))
$output = [System.IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
$packageId = "GetItSimple.SoundMixer"
$machineName = "SoundMixer-$Version-x64-machine-setup.exe"
$machinePath = Join-Path $assets $machineName

if (-not (Test-Path -LiteralPath $machinePath -PathType Leaf)) {
    throw "Release asset not found: $machinePath"
}

New-Item -ItemType Directory -Path $output -Force | Out-Null
$machineHash = (Get-FileHash -LiteralPath $machinePath -Algorithm SHA256).Hash
$baseUrl = "https://github.com/$Repository/releases/download/$Version"

$versionManifest = @"
# yaml-language-server: `$schema=https://aka.ms/winget-manifest.version.1.12.0.schema.json
PackageIdentifier: $packageId
PackageVersion: $Version
DefaultLocale: en-US
ManifestType: version
ManifestVersion: 1.12.0
"@

$installerManifest = @"
# yaml-language-server: `$schema=https://aka.ms/winget-manifest.installer.1.12.0.schema.json
PackageIdentifier: $packageId
PackageVersion: $Version
Platform:
- Windows.Desktop
MinimumOSVersion: 10.0.17763.0
InstallerType: nullsoft
InstallerSwitches:
  Silent: /S
  SilentWithProgress: /SILENTWITHPROGRESS
InstallModes:
- interactive
- silent
- silentWithProgress
UpgradeBehavior: install
ReleaseDate: $ReleaseDate
Installers:
- Architecture: x64
  Scope: machine
  InstallerUrl: $baseUrl/$machineName
  InstallerSha256: $machineHash
  AppsAndFeaturesEntries:
  - DisplayName: Sound Mixer
    Publisher: Get it Simple
    DisplayVersion: $Version
    ProductCode: $packageId
ManifestType: installer
ManifestVersion: 1.12.0
"@

$defaultLocaleManifest = @"
# yaml-language-server: `$schema=https://aka.ms/winget-manifest.defaultLocale.1.12.0.schema.json
PackageIdentifier: $packageId
PackageVersion: $Version
PackageLocale: en-US
Publisher: Get it Simple
PublisherUrl: https://github.com/get-it-simple
PublisherSupportUrl: https://github.com/$Repository/issues
Author: Get it Simple
PackageName: Sound Mixer
PackageUrl: https://github.com/$Repository
License: MIT
LicenseUrl: https://github.com/$Repository/blob/main/LICENSE
Copyright: Copyright (c) 2026 Get it Simple
ShortDescription: Per-application volume mixer for Windows
Description: Control per-application and system volume from an always-on-top overlay, tray menu, and global hotkeys.
Moniker: soundmixer
Tags:
- audio
- mixer
- sound
- volume
- windows
ReleaseNotesUrl: https://github.com/$Repository/releases/tag/$Version
ManifestType: defaultLocale
ManifestVersion: 1.12.0
"@

$ukLocaleManifest = @"
# yaml-language-server: `$schema=https://aka.ms/winget-manifest.locale.1.12.0.schema.json
PackageIdentifier: $packageId
PackageVersion: $Version
PackageLocale: uk-UA
Publisher: Get it Simple
PackageName: Sound Mixer
License: MIT
ShortDescription: Мікшер гучності окремих застосунків для Windows
Description: Керування гучністю окремих застосунків і системи через накладку, системний трей та глобальні гарячі клавіші.
ManifestType: locale
ManifestVersion: 1.12.0
"@

$files = @{
    "$packageId.yaml" = $versionManifest
    "$packageId.installer.yaml" = $installerManifest
    "$packageId.locale.en-US.yaml" = $defaultLocaleManifest
    "$packageId.locale.uk-UA.yaml" = $ukLocaleManifest
}

foreach ($entry in $files.GetEnumerator()) {
    $path = Join-Path $output $entry.Key
    [System.IO.File]::WriteAllText($path, $entry.Value.Trim() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

Get-ChildItem -LiteralPath $output -Filter "*.yaml" | Sort-Object Name | Select-Object -ExpandProperty FullName
