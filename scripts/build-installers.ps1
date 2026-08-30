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
$signScript = Join-Path $root "scripts\sign-artifacts.ps1"
$signingValues = @(
    $env:WINDOWS_SIGNING_CERTIFICATE_BASE64,
    $env:WINDOWS_SIGNING_CERTIFICATE_PASSWORD,
    $env:WINDOWS_TIMESTAMP_URL
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

if ($signingValues.Count -ne 0 -and $signingValues.Count -ne 3) {
    throw "Signing requires WINDOWS_SIGNING_CERTIFICATE_BASE64, WINDOWS_SIGNING_CERTIFICATE_PASSWORD, and WINDOWS_TIMESTAMP_URL together."
}

if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
    throw "Application executable not found: $appPath"
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

foreach ($scope in @("user", "machine")) {
    $fileName = "SoundMixer-$Version-x64-$scope-setup.exe"
    $target = Join-Path $outputPath $fileName
    $arguments = @(
        "/WX",
        "/DAPP_VERSION=$Version",
        "/DAPP_EXE=$appPath",
        "/DINSTALL_SCOPE=$scope",
        "/DOUTPUT_FILE=$target"
    )
    if ($signingValues.Count -eq 3) {
        $signCommand = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}" -Paths "%1"' -f $signScript
        $arguments += "/DSIGNED_BUILD=1"
        $arguments += "/DUNINSTALL_SIGN_COMMAND=$signCommand"
    } else {
        $arguments += "/DSIGNED_BUILD=0"
    }
    $arguments += $scriptPath
    & $MakeNsis @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "NSIS failed for $scope scope with exit code $LASTEXITCODE"
    }
}
