from pathlib import Path
import logging

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

    assert paths.default_settings_path(["SoundMixer.exe", "--portable"]) == install_dir / "settings.json"


def test_frozen_build_defaults_to_local_app_data_without_portable(monkeypatch, tmp_path):
    install_dir = tmp_path / "standalone"
    local_app_data = tmp_path / "data"
    configure_frozen(monkeypatch, install_dir, local_app_data)

    assert paths.default_settings_path(["SoundMixer.exe"]) == (
        local_app_data / "GetItSimple" / "SoundMixer" / "settings.json"
    )


def test_portable_falls_back_when_executable_directory_is_not_writable(monkeypatch, tmp_path):
    install_dir = tmp_path / "portable"
    local_app_data = tmp_path / "data"
    configure_frozen(monkeypatch, install_dir, local_app_data)
    monkeypatch.setattr(paths, "_is_directory_writable", lambda _: False)

    assert paths.default_settings_path(["SoundMixer.exe", "--portable"]) == (
        local_app_data / "GetItSimple" / "SoundMixer" / "settings.json"
    )


def test_write_probe_returns_after_first_permission_error(monkeypatch, tmp_path):
    attempts = 0

    def deny_open(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise PermissionError("denied")

    monkeypatch.setattr(paths.os, "open", deny_open)

    assert paths._is_directory_writable(tmp_path) is False
    assert attempts == 1


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


def test_failed_legacy_migration_is_logged(monkeypatch, tmp_path, caplog):
    source = tmp_path / "legacy" / "settings.json"
    target = tmp_path / "data" / "settings.json"
    source.parent.mkdir()
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths.shutil, "copy2", lambda *_: (_ for _ in ()).throw(PermissionError("denied")))

    with caplog.at_level(logging.WARNING):
        paths._migrate_legacy_settings(source, target)

    assert not target.exists()
    assert any(str(source) in record.getMessage() and str(target) in record.getMessage() for record in caplog.records)
