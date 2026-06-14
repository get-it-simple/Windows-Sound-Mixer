import sys
from pathlib import Path


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
    return _base_dir() / "settings.json"
