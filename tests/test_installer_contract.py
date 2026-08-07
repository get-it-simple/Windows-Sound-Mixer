import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_SOURCE = ROOT / "installer" / "SoundMixer.nsi"
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
