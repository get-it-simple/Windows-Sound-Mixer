import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"
VERSION_FILE = ROOT / "sound_mixer" / "__init__.py"


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


def _read_app_version() -> str:
    match = re.search(r'^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', VERSION_FILE.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Could not read application version from {VERSION_FILE}")
    return match.group(1)


def _write_version_resource(version: str) -> Path:
    version_parts = tuple(int(part) for part in version.split(".")) + (0,)
    build_dir = ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    path = build_dir / "version_info.txt"
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_parts},
    prodvers={version_parts},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Get it Simple'),
          StringStruct(u'FileDescription', u'Sound Mixer'),
          StringStruct(u'FileVersion', u'{version}.0'),
          StringStruct(u'InternalName', u'SoundMixer'),
          StringStruct(u'LegalCopyright', u'Copyright (c) 2026 Get it Simple'),
          StringStruct(u'OriginalFilename', u'SoundMixer.exe'),
          StringStruct(u'ProductName', u'Sound Mixer'),
          StringStruct(u'ProductVersion', u'{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)\n""",
        encoding="utf-8",
    )
    return path


def _run_pyinstaller() -> None:
    version_resource = _write_version_resource(_read_app_version())
    pyside_spec = importlib.util.find_spec("PySide6")
    if pyside_spec is None or pyside_spec.origin is None:
        raise RuntimeError("PySide6 is required to locate the Visual C++ runtime")
    vcruntime = Path(pyside_spec.origin).parent / "VCRUNTIME140.dll"
    if not vcruntime.is_file():
        raise RuntimeError(f"Visual C++ runtime not found: {vcruntime}")
    staged_vcruntime = ROOT / "build" / "vcruntime" / vcruntime.name
    staged_vcruntime.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vcruntime, staged_vcruntime)
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "SoundMixer",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
        "--icon",
        str(ROOT / "resources" / "icons" / "app.ico"),
        "--version-file",
        str(version_resource),
        "--add-data",
        f"{ROOT / 'resources'}{os.pathsep}resources",
        "--add-binary",
        f"{staged_vcruntime}{os.pathsep}.",
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
