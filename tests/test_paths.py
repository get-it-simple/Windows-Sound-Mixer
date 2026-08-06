from pathlib import Path

from sound_mixer import paths


def configure_frozen(monkeypatch, install_dir: Path, local_app_data: Path) -> None:
    executable = install_dir / "SoundMixer.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))


def test_portable_frozen_build_keeps_settings_next_to_executable(monkeypatch, tmp_path):
    install_dir = tmp_path / "portable"
    configure_frozen(monkeypatch, install_dir, tmp_path / "data")

    assert paths.default_settings_path() == install_dir / "settings.json"


def test_installed_build_uses_local_app_data(monkeypatch, tmp_path):
    install_dir = tmp_path / "installed"
    local_app_data = tmp_path / "data"
    configure_frozen(monkeypatch, install_dir, local_app_data)
    (install_dir / paths.INSTALL_MARKER).touch()

    assert paths.default_settings_path() == local_app_data / "GetItSimple" / "SoundMixer" / "settings.json"


def test_installed_build_migrates_legacy_settings_without_overwrite(monkeypatch, tmp_path):
    install_dir = tmp_path / "installed"
    local_app_data = tmp_path / "data"
    configure_frozen(monkeypatch, install_dir, local_app_data)
    (install_dir / paths.INSTALL_MARKER).touch()
    legacy = install_dir / "settings.json"
    legacy.write_text('{"source": "legacy"}', encoding="utf-8")

    target = paths.default_settings_path()

    assert target.read_text(encoding="utf-8") == '{"source": "legacy"}'
    target.write_text('{"source": "current"}', encoding="utf-8")
    legacy.write_text('{"source": "changed"}', encoding="utf-8")
    assert paths.default_settings_path().read_text(encoding="utf-8") == '{"source": "current"}'
