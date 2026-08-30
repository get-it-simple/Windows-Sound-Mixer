import ctypes
import sys
from pathlib import Path


DRIVE_REMOTE = 4


class InvalidExecutablePathError(ValueError):
    pass


def resolve_local_executable(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise InvalidExecutablePathError("Executable path is empty")

    windows_path = path.replace("/", "\\").casefold()
    if windows_path.startswith("\\\\") or windows_path.startswith("\\??\\") or windows_path.startswith("\\device\\"):
        raise InvalidExecutablePathError("Network and device paths are not allowed")

    candidate = Path(path)
    if not candidate.is_absolute():
        raise InvalidExecutablePathError("Executable path must be absolute")

    if sys.platform == "win32":
        root = candidate.anchor
        if not root or ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOTE:
            raise InvalidExecutablePathError("Executable must be stored on a local drive")

    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise InvalidExecutablePathError("Executable path does not exist") from exc

    if not resolved.is_file() or resolved.suffix.casefold() != ".exe":
        raise InvalidExecutablePathError("Path must reference an existing .exe file")

    if sys.platform == "win32":
        root = resolved.anchor
        if not root or ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOTE:
            raise InvalidExecutablePathError("Executable must be stored on a local drive")

    return str(resolved)
