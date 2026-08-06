param(
    [Parameter(Mandatory = $true)]
    [string[]]$Paths
)

$ErrorActionPreference = "Stop"
$certificate = $env:WINDOWS_SIGNING_CERTIFICATE_BASE64
$password = $env:WINDOWS_SIGNING_CERTIFICATE_PASSWORD
$timestamp = $env:WINDOWS_TIMESTAMP_URL
$configured = @($certificate, $password, $timestamp) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

if ($configured.Count -eq 0) {
    Write-Host "Windows signing secrets are not configured; artifacts remain unsigned."
    exit 0
}
if ($configured.Count -ne 3) {
    throw "Signing requires WINDOWS_SIGNING_CERTIFICATE_BASE64, WINDOWS_SIGNING_CERTIFICATE_PASSWORD, and WINDOWS_TIMESTAMP_URL together."
}

$signTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse |
    Where-Object FullName -Match '\\x64\\signtool\.exe$' |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $signTool) {
    throw "signtool.exe was not found in the Windows SDK."
}

$certificatePath = Join-Path $env:RUNNER_TEMP "sound-mixer-signing.pfx"
try {
    [System.IO.File]::WriteAllBytes($certificatePath, [Convert]::FromBase64String($certificate))
    foreach ($path in $Paths) {
        $resolved = (Resolve-Path -LiteralPath $path).Path
        & $signTool sign /fd SHA256 /td SHA256 /tr $timestamp /f $certificatePath /p $password $resolved
        if ($LASTEXITCODE -ne 0) {
            throw "signtool failed to sign $resolved"
        }
        & $signTool verify /pa /all $resolved
        if ($LASTEXITCODE -ne 0) {
            throw "Authenticode verification failed for $resolved"
        }
    }
}
finally {
    if (Test-Path -LiteralPath $certificatePath) {
        Remove-Item -LiteralPath $certificatePath -Force
    }
}
