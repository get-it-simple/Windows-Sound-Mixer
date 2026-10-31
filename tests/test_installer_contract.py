import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_SOURCE = ROOT / "installer" / "SoundMixer.nsi"
ELEVATION_SOURCE = ROOT / "installer" / "elevation.nsh"
VALIDATION_SOURCE = ROOT / "installer" / "uninstall_validation.nsh"
PROCESS_CONTROL_SOURCE = ROOT / "installer" / "process_control.nsh"
BUILD_INSTALLERS_SOURCE = ROOT / "scripts" / "build-installers.ps1"
INSTALLER_SMOKE_SOURCE = ROOT / "scripts" / "installer-smoke-test.ps1"
WINGET_SOURCE = ROOT / "scripts" / "generate-winget-manifests.ps1"


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^Function {re.escape(name)}\s*$\n(?P<body>.*?)^FunctionEnd\s*$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


@pytest.fixture(params=("powershell", "pwsh"))
def installer_build(tmp_path, request):
    shell = shutil.which(request.param)
    if shell is None:
        pytest.skip(f"{request.param} is not installed")

    root = tmp_path / "project with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(BUILD_INSTALLERS_SOURCE, scripts)
    version_file = root / "sound_mixer" / "__init__.py"
    version_file.parent.mkdir()
    version_file.write_text('__version__ = "2.3.4"\n', encoding="utf-8")
    app = root / "dist" / "SoundMixer.exe"
    app.parent.mkdir()
    app.write_bytes(b"test application")
    compiler = scripts / "record-nsis.ps1"
    compiler.write_text(
        'ConvertTo-Json -InputObject @($args) -Compress | Add-Content '
        '-LiteralPath (Join-Path $PSScriptRoot "nsis-arguments.jsonl") -Encoding UTF8\n'
        '$global:LASTEXITCODE = 0\n',
        encoding="utf-8",
    )
    python = scripts / "record-build.ps1"
    python.write_text(
        '$root = Split-Path -Parent $PSScriptRoot\n'
        'ConvertTo-Json -InputObject @($args) -Compress | Set-Content '
        '-LiteralPath (Join-Path $root "build-arguments.json") -Encoding UTF8\n'
        '$failurePath = Join-Path $root "build-failure.txt"\n'
        'if (Test-Path -LiteralPath $failurePath) {\n'
        '    $global:LASTEXITCODE = [int](Get-Content -LiteralPath $failurePath)\n'
        '    return\n'
        '}\n'
        '[System.IO.File]::WriteAllBytes((Join-Path $root "dist\\SoundMixer.exe"), '
        '[System.Text.Encoding]::UTF8.GetBytes("new test application"))\n'
        '$global:LASTEXITCODE = 0\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    for name in (
        "WINDOWS_SIGNING_CERTIFICATE_BASE64",
        "WINDOWS_SIGNING_CERTIFICATE_PASSWORD",
        "WINDOWS_TIMESTAMP_URL",
    ):
        environment.pop(name, None)

    runner = scripts / "run-build.ps1"
    runner.write_text(
        '$ErrorActionPreference = "Stop"\n'
        'if ($env:NSIS_TEST_PROGRAM_FILES) { $env:ProgramFiles = $env:NSIS_TEST_PROGRAM_FILES }\n'
        '& (Join-Path $PSScriptRoot "build-installers.ps1") @args\n'
        'exit $LASTEXITCODE\n',
        encoding="utf-8",
    )

    def build(*parameters, discover=False, env=None):
        compiler_arguments = [] if discover else ["-MakeNsis", str(compiler)]
        overrides = env or {}
        overridden_names = {name.casefold() for name in overrides}
        process_environment = {name: value for name, value in environment.items() if name.casefold() not in overridden_names}
        process_environment.update(overrides)
        result = subprocess.run(
            [
                shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(runner),
                *compiler_arguments, "-Python", str(python), *parameters,
            ],
            cwd=tmp_path,
            env=process_environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        log = scripts / "nsis-arguments.jsonl"
        invocations = (
            [json.loads(line) for line in log.read_text(encoding="utf-8-sig").splitlines()]
            if log.exists() else []
        )
        return result, invocations

    return root, build


@pytest.fixture(scope="session")
def nsis_recorder(tmp_path_factory):
    directory = tmp_path_factory.mktemp("nsis-recorder")
    source = directory / "Recorder.cs"
    source.write_text(
        'using System;\n'
        'using System.IO;\n'
        'using System.Web.Script.Serialization;\n'
        'class Recorder {\n'
        '    static void Main(string[] args) {\n'
        '        File.AppendAllText(Environment.GetEnvironmentVariable("NSIS_TEST_LOG"),\n'
        '            new JavaScriptSerializer().Serialize(args) + Environment.NewLine);\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
    executable = directory / "makensis.exe"
    result = subprocess.run(
        [str(compiler), "/nologo", "/reference:System.Web.Extensions.dll", f"/out:{executable}", str(source)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return executable


@pytest.mark.parametrize("location", ("explicit", "path", "x86", "native", "missing", "explicit_missing"))
def test_installer_discovers_compiler_without_machine_specific_paths(installer_build, nsis_recorder, location):
    root, build = installer_build
    tools = root / "tools with spaces"
    tools.mkdir()
    x86 = root / "programs x86"
    native = root / "programs native"
    environment = {
        "PATH": str(tools),
        "ProgramFiles(x86)": str(x86),
        "ProgramFiles": str(native),
        "NSIS_TEST_PROGRAM_FILES": str(native),
        "NSIS_TEST_LOG": str(root / "scripts" / "nsis-arguments.jsonl"),
    }
    parameters = []
    if location in ("explicit", "path"):
        target = tools / "makensis.exe"
    elif location == "x86":
        target = x86 / "NSIS" / "makensis.exe"
    else:
        target = native / "NSIS" / "makensis.exe"
    if location != "missing":
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nsis_recorder, target)
    if location == "explicit":
        parameters = ["-MakeNsis", str(target)]
    elif location == "explicit_missing":
        parameters = ["-MakeNsis", str(tools / "absent.exe")]

    result, invocations = build("-Build", *parameters, discover=True, env=environment)

    if location in ("missing", "explicit_missing"):
        assert result.returncode != 0
        assert "NSIS compiler not found" in result.stdout + result.stderr
        assert invocations == []
        assert not (root / "build-arguments.json").exists()
        assert not (root / "dist" / "installers").exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (root / "build-arguments.json").exists()
        assert len(invocations) == 2
        assert [next(arg for arg in args if arg.startswith("/DINSTALL_SCOPE=")) for args in invocations] == [
            "/DINSTALL_SCOPE=user", "/DINSTALL_SCOPE=machine",
        ]
        assert all("/DAPP_VERSION=2.3.4" in args for args in invocations)


@pytest.mark.parametrize("override", (None, "9.8.7"))
def test_installer_version_defaults_to_source_and_allows_override(installer_build, override):
    root, build = installer_build
    parameters = [] if override is None else ["-Version", override]

    result, invocations = build(*parameters)

    assert result.returncode == 0, result.stdout + result.stderr
    version = override or "2.3.4"
    assert len(invocations) == 2
    for arguments, scope in zip(invocations, ("user", "machine")):
        assert f"/DAPP_VERSION={version}" in arguments
        assert f"/DINSTALL_SCOPE={scope}" in arguments
        assert f"/DAPP_EXE={root / 'dist' / 'SoundMixer.exe'}" in arguments
        target = root / "dist" / "installers" / f"SoundMixer-{version}-x64-{scope}-setup.exe"
        assert f"/DOUTPUT_FILE={target}" in arguments
    assert (root / "dist" / "installers").is_dir()
    assert (root / "sound_mixer" / "__init__.py").read_text(encoding="utf-8") == '__version__ = "2.3.4"\n'
    assert (root / "dist" / "SoundMixer.exe").read_bytes() == b"test application"
    assert not (root / "build-arguments.json").exists()


@pytest.mark.parametrize("override", (None, "9.8.7"))
def test_installer_build_creates_application_before_packaging(installer_build, override):
    root, build = installer_build
    app = root / "dist" / "SoundMixer.exe"
    app.unlink()
    parameters = [] if override is None else ["-Version", override]

    result, invocations = build("-Build", *parameters)

    assert result.returncode == 0, result.stdout + result.stderr
    assert app.read_bytes() == b"new test application"
    arguments = json.loads((root / "build-arguments.json").read_text(encoding="utf-8-sig"))
    assert arguments == [str(root / "build.py")]
    assert len(invocations) == 2
    assert all(f"/DAPP_VERSION={override or '2.3.4'}" in arguments for arguments in invocations)


def test_failed_application_build_stops_packaging_even_with_existing_executable(installer_build):
    root, build = installer_build
    (root / "build-failure.txt").write_text("7", encoding="utf-8")

    result, invocations = build("-Build")

    assert result.returncode != 0
    assert "Application build failed with exit code 7" in result.stdout + result.stderr
    assert (root / "build-arguments.json").exists()
    assert (root / "dist" / "SoundMixer.exe").read_bytes() == b"test application"
    assert invocations == []
    assert not (root / "dist" / "installers").exists()


def test_installer_version_override_works_without_source_version(installer_build):
    root, build = installer_build
    (root / "sound_mixer" / "__init__.py").unlink()

    result, invocations = build("-Version", "9.8.7")

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(invocations) == 2
    assert all("/DAPP_VERSION=9.8.7" in arguments for arguments in invocations)


@pytest.mark.parametrize("missing", (False, True))
def test_installer_build_rejects_unreadable_source_version(installer_build, missing):
    root, build = installer_build
    version_file = root / "sound_mixer" / "__init__.py"
    if missing:
        version_file.unlink()
    else:
        version_file.write_text('__version__ = "invalid"\n', encoding="utf-8")

    result, invocations = build()

    assert result.returncode != 0
    assert "__init__.py" in result.stdout + result.stderr
    assert invocations == []
    assert not (root / "dist" / "installers").exists()


@pytest.mark.parametrize("version", ("invalid", "1.2"))
def test_installer_build_rejects_invalid_version_override(installer_build, version):
    root, build = installer_build

    result, invocations = build("-Version", version)

    assert result.returncode != 0
    assert "Version" in result.stdout + result.stderr
    assert invocations == []
    assert not (root / "dist" / "installers").exists()


def test_finish_option_launches_without_waiting_for_the_application():
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    body = _function_body(source, "FinishRun")

    assert "!define MUI_FINISHPAGE_RUN_FUNCTION FinishRun" in source
    assert "Exec '\"$INSTDIR\\${PRODUCT_EXE}\"'" in body
    assert "ExecWait" not in body
    assert "ExecShell" not in body
    assert "nsExec::" not in body


def test_silent_and_winget_installs_do_not_use_the_finish_launch_callback():
    installer = INSTALLER_SOURCE.read_text(encoding="utf-8")
    winget = WINGET_SOURCE.read_text(encoding="utf-8")

    assert '${GetOptions} $CMDLINE "/SILENTWITHPROGRESS"' in installer
    assert "SetAutoClose true" in installer
    assert re.search(
        r"!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipForProgressMode\s+"
        r"!insertmacro MUI_PAGE_FINISH",
        installer,
    )
    assert "Call FinishRun" not in installer
    assert "Silent: /S" in winget
    assert "SilentWithProgress: /SILENTWITHPROGRESS" in winget
    assert "Scope: machine" in winget


def test_winget_uses_only_the_self_elevating_machine_installer():
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell is not None

    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_dir) as temporary_directory:
        temporary_path = Path(temporary_directory)
        assets = temporary_path / "assets"
        output = temporary_path / "winget"
        assets.mkdir()
        (assets / "SoundMixer-0.9.3-x64-machine-setup.exe").write_bytes(b"machine")

        subprocess.run(
            [
                shell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(WINGET_SOURCE),
                "-Version",
                "0.9.3",
                "-AssetsDirectory",
                str(assets.relative_to(ROOT)),
                "-OutputDirectory",
                str(output.relative_to(ROOT)),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        manifest = (output / "GetItSimple.SoundMixer.installer.yaml").read_text(
            encoding="utf-8"
        )

    installers = manifest.split("- Architecture: x64")[1:]
    assert len(installers) == 1
    assert "Scope: machine" in installers[0]
    assert "ElevationRequirement:" not in installers[0]
    assert "SoundMixer-0.9.3-x64-machine-setup.exe" in installers[0]
    assert "SoundMixer-0.9.3-x64-user-setup.exe" not in manifest


def test_machine_migration_cleans_up_the_in_place_user_uninstaller():
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    body = _function_body(source, "RemovePreviousUserVersion")

    assert "_?=$UserInstallDir" in body
    assert 'Delete "$UserInstallDir\\Uninstall.exe"' in body
    assert 'RMDir "$UserInstallDir"' in body
    assert body.index('Delete "$UserInstallDir\\Uninstall.exe"') > body.index("ExecWait")


def test_elevation_uses_shell_execute_ex_without_powershell():
    installer = INSTALLER_SOURCE.read_text(encoding="utf-8")
    elevation = ELEVATION_SOURCE.read_text(encoding="utf-8")

    assert "powershell" not in installer.lower()
    assert "SetEnvironmentVariable" not in installer
    assert "ShellExecuteExW" in elevation
    assert 'w "runas"' in elevation
    assert "SEE_MASK" not in elevation or "0x140" in elevation
    assert "WaitForSingleObject" in elevation
    assert "GetExitCodeProcess" in elevation


def test_shutdown_never_forcibly_terminates_the_application():
    installer = INSTALLER_SOURCE.read_text(encoding="utf-8")
    process_control = PROCESS_CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "TerminateProcess" not in installer
    assert "TerminateProcess" not in process_control
    assert "shutdown_failed:" in installer


def test_machine_acl_check_skips_unresolvable_identities_and_tests_only_write_rights():
    source = INSTALLER_SMOKE_SOURCE.read_text(encoding="utf-8")

    assert "catch [System.Security.Principal.IdentityNotMappedException]" in source
    assert (
        "$writeRights = [System.Security.AccessControl.FileSystemRights]::Write"
        in source
    )
    assert "$identitySid -eq $usersSid" in source


def test_machine_install_path_is_fixed_to_program_files():
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")

    assert 'InstallDir "$PROGRAMFILES64\\SoundMixer"' in source
    assert re.search(r"!ifndef MACHINE_INSTALL\s+InstallDirRegKey", source)
    assert re.search(
        r"!ifndef MACHINE_INSTALL\s+"
        r"!define MUI_PAGE_CUSTOMFUNCTION_SHOW ApplySystemTheme\s+"
        r"!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipForProgressMode\s+"
        r"!insertmacro MUI_PAGE_DIRECTORY",
        source,
    )
    assert '${GetOptions} $CMDLINE "/D="' in source
    assert "$(InvalidInstallPath)" in source


def test_previous_uninstaller_is_derived_and_verified_before_execution():
    installer = INSTALLER_SOURCE.read_text(encoding="utf-8")
    validation = VALIDATION_SOURCE.read_text(encoding="utf-8")
    body = _function_body(installer, "RemovePreviousVersion")

    assert 'StrCpy $ExistingUninstaller "$ExistingDir\\Uninstall.exe"' in validation
    assert '.sound-mixer-installed' in validation
    assert "GetFinalPathNameByHandleW" in validation
    assert "WinVerifyTrust" in validation
    assert "Call ValidateExistingUninstaller" in body
    assert "ExecWait '$ExistingUninstaller" not in body
    assert 'ExecWait \'"$ExistingUninstaller"' in body


def test_signing_pipeline_supports_embedded_uninstaller():
    installer = INSTALLER_SOURCE.read_text(encoding="utf-8")
    build_script = BUILD_INSTALLERS_SOURCE.read_text(encoding="utf-8")

    assert "!uninstfinalize" in installer
    assert "version=${APP_VERSION}" in installer
    assert "signed=${SIGNED_BUILD}" in installer
    assert "/DSIGNED_BUILD=1" in build_script
    assert "/DUNINSTALL_SIGN_COMMAND=" in build_script


def test_uninstall_removes_only_sound_mixer_run_value_without_purge():
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    body = source.split('Section "Uninstall"', 1)[1].split("SectionEnd", 1)[0]

    assert body.count('DeleteRegValue HKCU "${RUN_KEY}" "${RUN_VALUE}"') == 2
    assert body.index('DeleteRegValue HKCU "${RUN_KEY}" "${RUN_VALUE}"') < body.index("Call un.RunElevated")
    assert 'DeleteRegKey HKCU "${RUN_KEY}"' not in body
    assert 'StrCmp $UpgradeMode 1 +2' in body


def test_purge_removes_rotating_logs():
    body = _function_body(INSTALLER_SOURCE.read_text(encoding="utf-8"), "un.PurgeCurrentUserData")

    for name in ("sound-mixer.log", "sound-mixer.log.1", "sound-mixer.log.2"):
        assert name in body
