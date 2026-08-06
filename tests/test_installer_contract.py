import re
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
    assert "Scope: user" in winget
    assert "Scope: machine" in winget
