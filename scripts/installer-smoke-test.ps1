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
$target = if ($Scope -eq "machine") { Join-Path $env:ProgramFiles "SoundMixer" } else { Join-Path $root "build\installer-smoke-user" }
$registryRoot = if ($Scope -eq "machine") { "HKLM:" } else { "HKCU:" }
$registryPath = "$registryRoot\Software\Microsoft\Windows\CurrentVersion\Uninstall\GetItSimple.SoundMixer"
$installArgs = if ($Scope -eq "machine") { @("/S") } else { @("/S", "/D=$target") }
$progressInstallArgs = if ($Scope -eq "machine") { @("/SILENTWITHPROGRESS") } else { @("/SILENTWITHPROGRESS", "/D=$target") }
$uninstallArgs = @("/S")
$dataDirectory = Join-Path $env:LOCALAPPDATA "GetItSimple\SoundMixer"
$settingsPath = Join-Path $dataDirectory "settings.json"
$logsDirectory = Join-Path $dataDirectory "logs"
$runRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$runValueName = "SoundMixer"
$unrelatedRunValueName = "SoundMixerSmokeUnrelated"
$previousRunValue = (Get-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -ErrorAction SilentlyContinue).$runValueName
$previousUnrelatedRunValue = (Get-ItemProperty -LiteralPath $runRegistryPath -Name $unrelatedRunValueName -ErrorAction SilentlyContinue).$unrelatedRunValueName
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
if (Test-Path -LiteralPath $target) {
    throw "Refusing to replace an existing install directory during a smoke test: $target"
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
    $expectedRegistryValues = @(
        "DisplayIcon", "DisplayName", "DisplayVersion", "EstimatedSize", "HelpLink", "InstallDate",
        "InstallLocation", "NoModify", "NoRepair", "Publisher", "QuietUninstallString", "UninstallString",
        "URLInfoAbout", "URLUpdateInfo"
    )
    $actualRegistryValues = @($entry.PSObject.Properties.Name | Where-Object { $_ -notlike "PS*" } | Sort-Object)
    if (Compare-Object $expectedRegistryValues $actualRegistryValues) {
        throw "Unexpected uninstall registry value set: $($actualRegistryValues -join ', ')"
    }

    $app = Join-Path $target "SoundMixer.exe"
    $uninstaller = Join-Path $target "Uninstall.exe"
    foreach ($path in @($app, $uninstaller, (Join-Path $target ".sound-mixer-installed"))) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Installed file not found: $path"
        }
    }
    $expectedFiles = @(".sound-mixer-installed", "LICENSE", "SoundMixer.exe", "Uninstall.exe")
    $actualFiles = @(Get-ChildItem -LiteralPath $target -File | Select-Object -ExpandProperty Name | Sort-Object)
    if (Compare-Object $expectedFiles $actualFiles) {
        throw "Unexpected installed file set: $($actualFiles -join ', ')"
    }
    $marker = Get-Content -LiteralPath (Join-Path $target ".sound-mixer-installed") -Raw
    $signedBuild = -not [string]::IsNullOrWhiteSpace($env:WINDOWS_SIGNING_CERTIFICATE_BASE64)
    $expectedSignedMarker = if ($signedBuild) { "signed=1" } else { "signed=0" }
    if ($marker -notmatch "version=$([regex]::Escape($Version))" -or $marker -notmatch "scope=$Scope" -or $marker -notmatch $expectedSignedMarker) {
        throw "Installation marker metadata is incorrect"
    }
    foreach ($shortcut in @("Sound Mixer.lnk", "Uninstall Sound Mixer.lnk")) {
        if (-not (Test-Path -LiteralPath (Join-Path $shortcutRoot $shortcut) -PathType Leaf)) {
            throw "Start Menu shortcut not found: $shortcut"
        }
    }
    $actualShortcuts = @(Get-ChildItem -LiteralPath $shortcutRoot -File | Select-Object -ExpandProperty Name | Sort-Object)
    if (Compare-Object @("Sound Mixer.lnk", "Uninstall Sound Mixer.lnk") $actualShortcuts) {
        throw "Unexpected Start Menu shortcut set: $($actualShortcuts -join ', ')"
    }
    foreach ($signedPath in @($Installer, $app, $uninstaller)) {
        $status = (Get-AuthenticodeSignature -LiteralPath $signedPath).Status
        if ($signedBuild -and $status -ne "Valid") { throw "Expected valid Authenticode signature: $signedPath ($status)" }
        if (-not $signedBuild -and $status -ne "NotSigned") { throw "Expected unsigned artifact: $signedPath ($status)" }
    }
    if ($Scope -eq "machine") {
        $usersSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-545")
        $writeRights = [System.Security.AccessControl.FileSystemRights]::Write -bor
            [System.Security.AccessControl.FileSystemRights]::Modify -bor
            [System.Security.AccessControl.FileSystemRights]::FullControl
        $unsafeRule = (Get-Acl -LiteralPath $target).Access | Where-Object {
            $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]) -eq $usersSid -and
            $_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band $writeRights)
        }
        if ($unsafeRule) { throw "Users have write access to the machine installation directory" }
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

    New-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -Value '"C:\invalid\SoundMixer.exe"' -PropertyType String -Force | Out-Null
    New-ItemProperty -LiteralPath $runRegistryPath -Name $unrelatedRunValueName -Value 'preserve' -PropertyType String -Force | Out-Null
    Invoke-Checked $uninstaller $uninstallArgs
    Wait-AppState $app $false "uninstall shutdown"
    Wait-UninstallCleanup $app
    if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
        throw "Silent uninstall removed settings without /PURGE"
    }
    if ((Get-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -ErrorAction SilentlyContinue).$runValueName) {
        throw "Uninstall did not remove the current user's SoundMixer Run value"
    }
    if ((Get-ItemProperty -LiteralPath $runRegistryPath -Name $unrelatedRunValueName).$unrelatedRunValueName -ne "preserve") {
        throw "Uninstall changed an unrelated Run value"
    }

    Invoke-Checked $Installer $progressInstallArgs
    if (Test-AppRunning $app) {
        throw "Silent-with-progress installation unexpectedly launched the application"
    }
    $uninstaller = Join-Path $target "Uninstall.exe"
    New-Item -ItemType Directory -Path $logsDirectory -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $logsDirectory "sound-mixer.log") -Value "purge"
    New-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -Value '"C:\invalid\SoundMixer.exe"' -PropertyType String -Force | Out-Null
    Invoke-Checked $uninstaller @("/S", "/PURGE")
    Wait-UninstallCleanup $app
    $purgeDeadline = (Get-Date).AddSeconds(10)
    while ((Test-Path -LiteralPath $settingsPath) -and (Get-Date) -lt $purgeDeadline) {
        Start-Sleep -Milliseconds 200
    }
    if (Test-Path -LiteralPath $settingsPath) { throw "/PURGE did not remove current-user settings" }
    if (Test-Path -LiteralPath $logsDirectory) { throw "/PURGE did not remove current-user logs" }
    if ((Get-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -ErrorAction SilentlyContinue).$runValueName) {
        throw "/PURGE uninstall did not remove the SoundMixer Run value"
    }
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
    Remove-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -ErrorAction SilentlyContinue
    Remove-ItemProperty -LiteralPath $runRegistryPath -Name $unrelatedRunValueName -ErrorAction SilentlyContinue
    if ($null -ne $previousRunValue) {
        New-ItemProperty -LiteralPath $runRegistryPath -Name $runValueName -Value $previousRunValue -PropertyType String -Force | Out-Null
    }
    if ($null -ne $previousUnrelatedRunValue) {
        New-ItemProperty -LiteralPath $runRegistryPath -Name $unrelatedRunValueName -Value $previousUnrelatedRunValue -PropertyType String -Force | Out-Null
    }
    $backup = Join-Path $backupRoot "SoundMixer"
    if (Test-Path -LiteralPath $backup) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $dataDirectory) -Force | Out-Null
        Move-Item -LiteralPath $backup -Destination $dataDirectory
    }
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
}
