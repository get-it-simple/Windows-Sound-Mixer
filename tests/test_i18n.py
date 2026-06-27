import pytest

import sound_mixer.i18n as i18n
from sound_mixer.i18n import AVAILABLE_LANGUAGES, FALLBACK_LANGUAGE, language_display_name, t


@pytest.fixture(autouse=True)
def reset_i18n():
    yield
    i18n.setup(FALLBACK_LANGUAGE)


def test_default_language_is_english():
    assert i18n.get_current_language() == "en"


def test_t_returns_english_string_by_default():
    assert t("sound_mixer_title") == "Sound Mixer"
    assert t("close_tooltip") == "Close"


def test_t_returns_key_for_unknown_string():
    assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_setup_english_returns_english_strings():
    i18n.setup("en")

    assert t("sound_mixer_title") == "Sound Mixer"
    assert t("exit_menu") == "Exit"
    assert i18n.get_current_language() == "en"


def test_setup_ukrainian_returns_ukrainian_strings():
    i18n.setup("uk")

    assert t("sound_mixer_title") == "Sound Mixer"
    assert t("exit_menu") == "Вийти"
    assert t("tab_general") == "Загальні"
    assert i18n.get_current_language() == "uk"


def test_setup_unknown_language_falls_back_to_english():
    i18n.setup("zz")

    assert i18n.get_current_language() == "en"
    assert t("exit_menu") == "Exit"


def test_setup_system_does_not_crash():
    i18n.setup("system")

    assert i18n.get_current_language() in AVAILABLE_LANGUAGES


def test_ukrainian_falls_back_to_english_for_missing_keys():
    i18n.setup("uk")

    assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_available_languages_contains_en_and_uk():
    assert "en" in AVAILABLE_LANGUAGES
    assert "uk" in AVAILABLE_LANGUAGES


def test_language_display_name_different_languages():
    i18n.setup("en")

    name = language_display_name("uk")
    assert "Українська" in name
    assert "Ukrainian" in name


def test_language_display_name_same_as_current_shows_native_only():
    i18n.setup("en")

    name = language_display_name("en")
    assert name == "English"


def test_language_display_name_explicit_current():
    name = language_display_name("en", current_lang="uk")
    assert name == "English (Англійська)"


def test_language_display_name_uk_from_en():
    name = language_display_name("uk", current_lang="en")
    assert name == "Українська (Ukrainian)"


def test_detect_system_language_returns_valid_code():
    lang = i18n.detect_system_language()

    assert lang in AVAILABLE_LANGUAGES
