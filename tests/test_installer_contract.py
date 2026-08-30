import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_SOURCE = ROOT / "installer" / "SoundMixer.nsi"
ELEVATION_SOURCE = ROOT / "installer" / "elevation.nsh"
VALIDATION_SOURCE = ROOT / "installer" / "uninstall_validation.nsh"
PROCESS_CONTROL_SOURCE = ROOT / "installer" / "process_control.nsh"
BUILD_INSTALLERS_SOURCE = ROOT / "scripts" / "build-installers.ps1"
WINGET_SOURCE = ROOT / "scripts" / "generate-winget-manifests.ps1"


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^Function {re.escape(name)}\s*$\n(?P<body>.*?)^FunctionEnd\s*$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


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
