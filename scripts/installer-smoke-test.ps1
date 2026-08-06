param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("user", "machine")]
    [string]$Scope,
    [Parameter(Mandatory = $true)]
    [string]$Installer,
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root "build\installer-smoke-$Scope"
$registryRoot = if ($Scope -eq "machine") { "HKLM:" } else { "HKCU:" }
$registryPath = "$registryRoot\Software\Microsoft\Windows\CurrentVersion\Uninstall\GetItSimple.SoundMixer"
$installArgs = @("/S", "/D=$target")
$progressInstallArgs = @("/SILENTWITHPROGRESS", "/D=$target")
$uninstallArgs = @("/S")
$dataDirectory = Join-Path $env:LOCALAPPDATA "GetItSimple\SoundMixer"
$settingsPath = Join-Path $dataDirectory "settings.json"
$temporaryRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$backupRoot = Join-Path $temporaryRoot "sound-mixer-smoke-$Scope-$([guid]::NewGuid())"
$shortcutRoot = if ($Scope -eq "machine") {
    Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\Sound Mixer"
} else {
    Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Sound Mixer"
}

function Test-AppRunning([string]$Path) {
    $expected = [System.IO.Path]::GetFullPath($Path)
    $matches = @(Get-Process -Name SoundMixer -ErrorAction SilentlyContinue | Where-Object {
        try { [System.IO.Path]::GetFullPath($_.Path) -eq $expected } catch { $false }
    })
    return $matches.Count -gt 0
}

function Wait-AppState([string]$Path, [bool]$Running, [string]$Stage, [int]$TimeoutSeconds = 20) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Test-AppRunning $Path) -eq $Running) { return }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    throw "Sound Mixer did not reach running=$Running during $Stage for $Path"
}

function Invoke-Checked([string]$Path, [string[]]$Arguments) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = [System.IO.Path]::GetFullPath($Path)
    $startInfo.UseShellExecute = $false
    foreach ($argument in $Arguments) {
        $startInfo.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::Start($startInfo)
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "$Path exited with $($process.ExitCode)"
    }
}

function Wait-UninstallCleanup([string]$AppPath, [int]$TimeoutSeconds = 20) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Test-Path -LiteralPath $AppPath) -and
            -not (Test-Path -LiteralPath $registryPath) -and
            -not (Test-Path -LiteralPath $shortcutRoot)) {
            return
        }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    throw "Uninstall cleanup timed out (app=$(Test-Path -LiteralPath $AppPath), registry=$(Test-Path -LiteralPath $registryPath), shortcuts=$(Test-Path -LiteralPath $shortcutRoot))"
}

if (Test-Path -LiteralPath $registryPath) {
    throw "Refusing to replace an existing $Scope installation during a smoke test."
}
if (Test-Path -LiteralPath $shortcutRoot) {
    throw "Refusing to replace an existing Start Menu folder during a smoke test: $shortcutRoot"
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
if (Test-Path -LiteralPath $dataDirectory) {
    Move-Item -LiteralPath $dataDirectory -Destination (Join-Path $backupRoot "SoundMixer")
}

try {
    Invoke-Checked $Installer $installArgs

    $entry = Get-ItemProperty -LiteralPath $registryPath
    if ($entry.DisplayName -ne "Sound Mixer" -or $entry.DisplayVersion -ne $Version -or $entry.Publisher -ne "Get it Simple") {
        throw "Apps & Features metadata is incorrect"
    }
    if ($entry.InstallLocation -ne $target) {
        throw "Unexpected install path: $($entry.InstallLocation)"
    }

    $app = Join-Path $target "SoundMixer.exe"
    $uninstaller = Join-Path $target "Uninstall.exe"
    foreach ($path in @($app, $uninstaller, (Join-Path $target ".sound-mixer-installed"))) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Installed file not found: $path"
        }
    }
    foreach ($shortcut in @("Sound Mixer.lnk", "Uninstall Sound Mixer.lnk")) {
        if (-not (Test-Path -LiteralPath (Join-Path $shortcutRoot $shortcut) -PathType Leaf)) {
            throw "Start Menu shortcut not found: $shortcut"
        }
    }

    $versionInfo = (Get-Item -LiteralPath $app).VersionInfo
    if ($versionInfo.ProductVersion -ne $Version -or $versionInfo.FileVersion -ne "$Version.0" -or $versionInfo.CompanyName -ne "Get it Simple") {
        throw "Executable version resource is incorrect"
    }
    if (Test-AppRunning $app) {
        throw "Fresh silent installation unexpectedly launched the application"
    }

    New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
    [System.IO.File]::WriteAllText($settingsPath, '{"version":5,"smoke_marker":"preserve"}', [System.Text.UTF8Encoding]::new($false))
    Start-Process -FilePath $app | Out-Null
    Wait-AppState $app $true "initial launch"

    Invoke-Checked $Installer $installArgs
    Wait-AppState $app $false "upgrade leaves the application stopped"
    if ((Get-Content -LiteralPath $settingsPath -Raw) -notmatch 'smoke_marker') {
        throw "Settings were not preserved during upgrade"
    }

    Invoke-Checked $uninstaller $uninstallArgs
    Wait-AppState $app $false "uninstall shutdown"
    Wait-UninstallCleanup $app
    if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
        throw "Silent uninstall removed settings without /PURGE"
    }

    Invoke-Checked $Installer $progressInstallArgs
    if (Test-AppRunning $app) {
        throw "Silent-with-progress installation unexpectedly launched the application"
    }
    $uninstaller = Join-Path $target "Uninstall.exe"
    Invoke-Checked $uninstaller @("/S", "/PURGE")
    Wait-UninstallCleanup $app
    $purgeDeadline = (Get-Date).AddSeconds(10)
    while ((Test-Path -LiteralPath $settingsPath) -and (Get-Date) -lt $purgeDeadline) {
        Start-Sleep -Milliseconds 200
    }
    if (Test-Path -LiteralPath $settingsPath) { throw "/PURGE did not remove current-user settings" }
}
finally {
    $app = Join-Path $target "SoundMixer.exe"
    if (Test-AppRunning $app) {
        Start-Process -FilePath $app -ArgumentList "--shutdown-for-update" -Wait | Out-Null
    }
    $uninstaller = Join-Path $target "Uninstall.exe"
    if (Test-Path -LiteralPath $uninstaller) {
        Start-Process -FilePath $uninstaller -ArgumentList @("/S", "/PURGE") -Wait | Out-Null
    }
    if (Test-Path -LiteralPath $dataDirectory) {
        Remove-Item -LiteralPath $dataDirectory -Recurse -Force
    }
    $backup = Join-Path $backupRoot "SoundMixer"
    if (Test-Path -LiteralPath $backup) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $dataDirectory) -Force | Out-Null
        Move-Item -LiteralPath $backup -Destination $dataDirectory
    }
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
}
