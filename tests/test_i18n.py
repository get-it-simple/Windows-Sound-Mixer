import ast
import json
import shutil
from pathlib import Path

import pytest

import sound_mixer.i18n as i18n


@pytest.fixture(autouse=True)
def reset_i18n():
    i18n.setup("en")
    yield
    i18n.setup("en")


def test_english_catalog_and_unknown_keys():
    assert i18n.get_current_language() == "en"
    assert i18n.t("sound_mixer_title") == "Sound Mixer"
    assert i18n.t("exit_menu") == "Exit"
    assert i18n.t("nonexistent_key_xyz") == "nonexistent_key_xyz"
    catalog = json.loads((i18n._TRANSLATIONS_DIR / "en" / "strings.json").read_text(encoding="utf-8"))
    assert catalog
    assert all(isinstance(value, str) and value for value in catalog.values())
    for source in i18n._TRANSLATIONS_DIR.parent.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t":
                if node.args and isinstance(node.args[0], ast.Constant):
                    assert node.args[0].value in catalog, f"Missing English string in {source}: {node.args[0].value}"


def test_unknown_language_falls_back_to_english():
    i18n.setup("nonexistent-language")
    assert i18n.get_current_language() == "en"
    assert i18n.t("exit_menu") == "Exit"


def test_english_language_names():
    assert "en" in i18n.AVAILABLE_LANGUAGES
    assert i18n._language_native_name("en") == "English"
    assert i18n._language_english_name("en") == "English"
    assert i18n.language_display_name("en") == "English"


def test_new_catalog_is_discovered_loaded_and_falls_back(tmp_path, monkeypatch):
    shutil.copytree(i18n._TRANSLATIONS_DIR / "en", tmp_path / "en")
    catalog_dir = tmp_path / "en-GB"
    catalog_dir.mkdir()
    (catalog_dir / "strings.json").write_text(json.dumps({"exit_menu": "Leave"}), encoding="utf-8")
    (tmp_path / "empty-directory").mkdir()
    (tmp_path / "ignored.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(i18n, "_TRANSLATIONS_DIR", tmp_path)
    monkeypatch.setattr(i18n, "AVAILABLE_LANGUAGES", i18n._discover_languages())

    assert i18n.AVAILABLE_LANGUAGES == ["en", "en-GB"]
    i18n.setup("en-GB")
    assert i18n.get_current_language() == "en-GB"
    assert i18n.t("exit_menu") == "Leave"
    assert i18n.t("close_tooltip") == "Close"
    assert i18n.t("nonexistent_key_xyz") == "nonexistent_key_xyz"
    i18n.setup("en")
    assert i18n.t("exit_menu") == "Exit"


def test_system_locale_prefers_exact_then_parent_language(monkeypatch):
    monkeypatch.setattr(i18n, "AVAILABLE_LANGUAGES", ["en", "en-GB"])
    assert i18n._match_language("en_GB.UTF-8") == "en-GB"
    assert i18n._match_language("EN-gb") == "en-GB"
    assert i18n._match_language("en-US") == "en"
    assert i18n._match_language("zz-ZZ") is None
    i18n.setup("system")
    assert i18n.get_current_language() in i18n.AVAILABLE_LANGUAGES


def test_build_collects_catalogs_without_registering_languages():
    from PyInstaller.utils.hooks import collect_data_files

    catalogs = {
        str(Path(source).resolve())
        for source, destination in collect_data_files("sound_mixer.i18n")
        if Path(source).name == "strings.json"
    }
    assert str((i18n._TRANSLATIONS_DIR / "en" / "strings.json").resolve()) in catalogs
    assert catalogs == {str(path.resolve()) for path in i18n._TRANSLATIONS_DIR.glob("*/strings.json")}
