import logging
import os
import shutil
import sys
import uuid
from pathlib import Path

INSTALL_MARKER = ".sound-mixer-installed"
INSTALLED_DATA_PARTS = ("GetItSimple", "SoundMixer")
logger = logging.getLogger(__name__)


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


def default_settings_path(argv: list[str] | None = None) -> Path:
    base_dir = _base_dir()
    if not getattr(sys, "frozen", False):
        return base_dir / "settings.json"

    argv = sys.argv if argv is None else argv
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return base_dir / "settings.json"

    target = Path(local_app_data).joinpath(*INSTALLED_DATA_PARTS, "settings.json")
    if "--portable" in argv and _is_directory_writable(base_dir):
        return base_dir / "settings.json"

    _migrate_legacy_settings(base_dir / "settings.json", target)
    return target


def _is_directory_writable(directory: Path) -> bool:
    temporary_path = directory / f".sound-mixer-write-{uuid.uuid4().hex}"
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(temporary_path, flags)
        os.close(descriptor)
        descriptor = None
        temporary_path.unlink()
        return True
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except OSError:
            pass
        return False


def _migrate_legacy_settings(source: Path, target: Path) -> None:
    if target.exists() or not source.is_file():
        return

    temporary = target.with_suffix(target.suffix + ".migrating")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    except OSError:
        logger.warning(
            "Failed to migrate settings from %s to %s; using the destination path",
            source,
            target,
            exc_info=True,
        )
        try:
            temporary.unlink()
        except OSError:
            pass
