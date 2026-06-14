import importlib.metadata
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"


def _parse_requirement(line: str) -> tuple[str, str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(>=|==)\s*([A-Za-z0-9_.\-]+)$", line)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for part in version.split("."):
        digits = re.match(r"\d+", part)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def _missing_requirements() -> list[str]:
    missing = []
    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        parsed = _parse_requirement(line)
        if parsed is None:
            continue

        name, op, version = parsed
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(f"{name}{op}{version}")
            continue

        if op == "==" and _version_tuple(installed) != _version_tuple(version):
            missing.append(f"{name}{op}{version}")
        elif op == ">=" and _version_tuple(installed) < _version_tuple(version):
            missing.append(f"{name}{op}{version}")

    return missing


def _install(specs: list[str]) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", *specs], check=True)


def _run_pyinstaller() -> None:
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "SoundMixer",
        "--onefile",
        "--windowed",
        "--icon",
        str(ROOT / "resources" / "icons" / "app.ico"),
        "--add-data",
        f"{ROOT / 'resources'}{os.pathsep}resources",
        str(ROOT / "sound_mixer" / "__main__.py"),
    ]
    subprocess.run(args, check=True, cwd=ROOT)


def main() -> int:
    missing = _missing_requirements()
    if missing:
        print("The following dependencies are missing or outdated:")
        for spec in missing:
            print(f"  {spec}")

        answer = input("Install them now with pip? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborting build.")
            return 1

        _install(missing)

    _run_pyinstaller()

    exe_path = ROOT / "dist" / "SoundMixer.exe"
    print(f"Build complete: {exe_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
