param(
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+$')]
    [string]$Version,
    [string]$AppExe = "dist\SoundMixer.exe",
    [string]$OutputDirectory = "dist\installers",
    [string]$MakeNsis,
    [switch]$Build,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $PSBoundParameters.ContainsKey("Version")) {
    $versionPath = Join-Path $root "sound_mixer\__init__.py"
    $versionMatch = [regex]::Match(
        (Get-Content -LiteralPath $versionPath -Raw),
        '(?m)^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"'
    )
    if (-not $versionMatch.Success) {
        throw "Could not read application version from $versionPath. Use -Version X.Y.Z to override it."
    }
    $Version = $versionMatch.Groups[1].Value
}

if ($PSBoundParameters.ContainsKey("MakeNsis")) {
    $compiler = Get-Command -Name $MakeNsis -CommandType Application, ExternalScript -ErrorAction SilentlyContinue | Select-Object -First 1
} else {
    $compiler = Get-Command -Name "makensis" -CommandType Application, ExternalScript -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $compiler) {
        foreach ($programDirectory in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
            if ([string]::IsNullOrWhiteSpace($programDirectory)) { continue }
            $candidate = Join-Path $programDirectory "NSIS\makensis.exe"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $compiler = Get-Command -Name $candidate -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($null -ne $compiler) { break }
            }
        }
    }
}
if ($null -eq $compiler) {
    throw "NSIS compiler not found. Install NSIS, add makensis to PATH, or pass -MakeNsis with its executable path."
}
$MakeNsis = $compiler.Source

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

if ($Build) {
    & $Python (Join-Path $root "build.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Application build failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
    throw "Application executable not found: $appPath"
}

Write-Host "Building installers for version $Version"
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
