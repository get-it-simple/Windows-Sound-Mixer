import os
import shutil
import sys
from pathlib import Path

INSTALL_MARKER = ".sound-mixer-installed"
INSTALLED_DATA_PARTS = ("GetItSimple", "SoundMixer")


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", _base_dir()))
    else:
        base = _base_dir()
    return base.joinpath(*parts)


def default_settings_path() -> Path:
    base_dir = _base_dir()
    if not getattr(sys, "frozen", False) or not (base_dir / INSTALL_MARKER).is_file():
        return base_dir / "settings.json"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return base_dir / "settings.json"

    target = Path(local_app_data).joinpath(*INSTALLED_DATA_PARTS, "settings.json")
    _migrate_legacy_settings(base_dir / "settings.json", target)
    return target


def _migrate_legacy_settings(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".migrating")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
