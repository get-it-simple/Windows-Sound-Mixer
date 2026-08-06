param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$AppExe = "dist\SoundMixer.exe",
    [string]$OutputDirectory = "dist\installers",
    [string]$MakeNsis = "makensis"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$appPath = [System.IO.Path]::GetFullPath((Join-Path $root $AppExe))
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
$scriptPath = Join-Path $root "installer\SoundMixer.nsi"

if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
    throw "Application executable not found: $appPath"
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

foreach ($scope in @("user", "machine")) {
    $fileName = "SoundMixer-$Version-x64-$scope-setup.exe"
    $target = Join-Path $outputPath $fileName
    & $MakeNsis /WX "/DAPP_VERSION=$Version" "/DAPP_EXE=$appPath" "/DINSTALL_SCOPE=$scope" "/DOUTPUT_FILE=$target" $scriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "NSIS failed for $scope scope with exit code $LASTEXITCODE"
    }
}
