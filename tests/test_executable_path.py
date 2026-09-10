import sys
from pathlib import Path

import pytest

from sound_mixer import executable_path
from sound_mixer.executable_path import InvalidExecutablePathError, resolve_application_path, resolve_local_executable


def make_executable(tmp_path: Path, name: str = "App.exe") -> Path:
    path = tmp_path / name
    path.write_bytes(b"MZ")
    return path


def test_resolves_existing_local_executable(tmp_path):
    path = make_executable(tmp_path)

    assert resolve_local_executable(str(path)) == str(path.resolve())


@pytest.mark.parametrize(
    "path",
    [
        r"\\server\share\App.exe",
        r"\\?\C:\Apps\App.exe",
        r"\\.\C:\Apps\App.exe",
        r"\??\C:\Apps\App.exe",
        r"\Device\HarddiskVolume1\Apps\App.exe",
    ],
)
def test_rejects_network_and_device_paths_without_access(path):
    with pytest.raises(InvalidExecutablePathError):
        resolve_local_executable(path)


def test_rejects_relative_missing_directory_and_non_exe_paths(tmp_path):
    directory = tmp_path / "folder.exe"
    directory.mkdir()
    text_file = tmp_path / "file.txt"
    text_file.write_text("not executable", encoding="utf-8")

    for path in ("relative.exe", str(tmp_path / "missing.exe"), str(directory), str(text_file)):
        with pytest.raises(InvalidExecutablePathError):
            resolve_local_executable(path)


def test_rejects_mapped_network_drive(monkeypatch, tmp_path):
    path = make_executable(tmp_path)
    monkeypatch.setattr(executable_path.ctypes.windll.kernel32, "GetDriveTypeW", lambda _: 4)

    with pytest.raises(InvalidExecutablePathError):
        resolve_local_executable(str(path))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts")
def test_resolves_real_windows_shortcut_with_spaces_and_unicode(tmp_path):
    from PySide6.QtCore import QFile

    target = make_executable(tmp_path, "Програма з пробілами.exe")
    shortcut = tmp_path / "Ярлик.LNK"
    assert QFile(str(target)).link(str(shortcut))
    before = shortcut.read_bytes()

    assert resolve_application_path(str(shortcut)) == str(target.resolve())
    assert shortcut.read_bytes() == before


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts")
@pytest.mark.parametrize("target_kind", ["missing", "document", "directory"])
def test_rejects_shortcuts_without_existing_executable_target(tmp_path, target_kind):
    from PySide6.QtCore import QFile

    target = tmp_path / ("App.txt" if target_kind == "document" else "App.exe")
    if target_kind == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"MZ")
    shortcut = tmp_path / "Application.lnk"
    assert QFile(str(target)).link(str(shortcut))
    if target_kind == "missing":
        target.unlink()

    with pytest.raises(InvalidExecutablePathError):
        resolve_application_path(str(shortcut))


def test_rejects_malformed_shortcut(tmp_path):
    shortcut = tmp_path / "Invalid.lnk"
    shortcut.write_bytes(b"not a shortcut")
    with pytest.raises(InvalidExecutablePathError):
        resolve_application_path(str(shortcut))


def test_rejects_remote_shortcut_before_resolving_it(monkeypatch):
    from PySide6.QtCore import QFileInfo

    def fail_if_called(*args):
        raise AssertionError("Remote shortcut must not be read")

    monkeypatch.setattr(QFileInfo, "symLinkTarget", fail_if_called)
    with pytest.raises(InvalidExecutablePathError):
        resolve_application_path(r"\\server\share\App.lnk")
