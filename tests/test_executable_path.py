from pathlib import Path

import pytest

from sound_mixer import executable_path
from sound_mixer.executable_path import InvalidExecutablePathError, resolve_local_executable


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
