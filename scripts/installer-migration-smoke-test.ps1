param(
    [Parameter(Mandatory = $true)]
    [string]$UserInstaller,
    [Parameter(Mandatory = $true)]
    [string]$MachineInstaller,
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$userTarget = Join-Path $root "build\installer-migration-user"
$machineTarget = Join-Path $env:ProgramFiles "SoundMixer"
$userRegistry = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GetItSimple.SoundMixer"
$machineRegistry = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GetItSimple.SoundMixer"
$userShortcuts = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Sound Mixer"
$machineShortcuts = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\Sound Mixer"
$dataDirectory = Join-Path $env:LOCALAPPDATA "GetItSimple\SoundMixer"
$settingsPath = Join-Path $dataDirectory "settings.json"
$temporaryRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$backupRoot = Join-Path $temporaryRoot "sound-mixer-migration-$([guid]::NewGuid())"

function Invoke-Checked([string]$Path, [string[]]$Arguments) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = [System.IO.Path]::GetFullPath($Path)
    $startInfo.UseShellExecute = $false
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::Start($startInfo)
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "$Path exited with $($process.ExitCode)" }
}

function Wait-Until([scriptblock]$Condition, [string]$Description, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Description"
}

foreach ($path in @($userRegistry, $machineRegistry, $userTarget, $machineTarget, $userShortcuts, $machineShortcuts)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite migration test state: $path" }
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
if (Test-Path -LiteralPath $dataDirectory) {
    Move-Item -LiteralPath $dataDirectory -Destination (Join-Path $backupRoot "SoundMixer")
}

try {
    Invoke-Checked $UserInstaller @("/S", "/D=$userTarget")
    if (-not (Test-Path -LiteralPath $userRegistry)) { throw "User ARP entry was not created" }

    New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
    [System.IO.File]::WriteAllText($settingsPath, '{"version":5,"migration_marker":"preserve"}', [System.Text.UTF8Encoding]::new($false))

    Invoke-Checked $MachineInstaller @("/S")
    Wait-Until { -not (Test-Path -LiteralPath $userRegistry) } "user ARP removal"
    Wait-Until { -not (Test-Path -LiteralPath $userTarget) } "user files removal"

    if (-not (Test-Path -LiteralPath $machineRegistry)) { throw "Machine ARP entry was not created" }
    $entry = Get-ItemProperty -LiteralPath $machineRegistry
    if ($entry.InstallLocation -ne $machineTarget -or $entry.DisplayVersion -ne $Version) {
        throw "Machine ARP metadata is incorrect after migration"
    }
    if (Test-Path -LiteralPath $userShortcuts) { throw "User shortcuts survived machine migration" }
    if (-not (Test-Path -LiteralPath $machineShortcuts)) { throw "Machine shortcuts were not created" }
    if ((Get-Content -LiteralPath $settingsPath -Raw) -notmatch 'migration_marker') {
        throw "Settings were not preserved during user-to-machine migration"
    }

    $machineUninstaller = Join-Path $machineTarget "Uninstall.exe"
    Invoke-Checked $machineUninstaller @("/S")
    Wait-Until { -not (Test-Path -LiteralPath $machineRegistry) } "machine ARP cleanup"
    Wait-Until { -not (Test-Path -LiteralPath $machineTarget) } "machine files cleanup"
    if (-not (Test-Path -LiteralPath $settingsPath)) { throw "Machine uninstall removed settings without /PURGE" }
}
finally {
    foreach ($target in @($userTarget, $machineTarget)) {
        $uninstaller = Join-Path $target "Uninstall.exe"
        if (Test-Path -LiteralPath $uninstaller) {
            Start-Process -FilePath $uninstaller -ArgumentList @("/S") -Wait | Out-Null
        }
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
