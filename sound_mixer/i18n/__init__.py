import ctypes
import sys

from sound_mixer.i18n.en import STRINGS as _EN_STRINGS

FALLBACK_LANGUAGE = "en"

AVAILABLE_LANGUAGES: list[str] = ["en", "uk"]

LANGUAGE_NAMES: dict[str, dict[str, str]] = {
    "en": {"en": "English", "uk": "Англійська"},
    "uk": {"en": "Ukrainian", "uk": "Українська"},
}

_strings: dict[str, str] = dict(_EN_STRINGS)
_current_language: str = FALLBACK_LANGUAGE


def detect_system_language() -> str:
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(85)
            ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
            lang_code = buf.value.split("-")[0].lower()
            if lang_code in AVAILABLE_LANGUAGES:
                return lang_code
        except Exception:
            pass
    try:
        import locale

        lang = locale.getdefaultlocale()[0]
        if lang:
            lang_code = lang.split("_")[0].lower()
            if lang_code in AVAILABLE_LANGUAGES:
                return lang_code
    except Exception:
        pass
    return FALLBACK_LANGUAGE


def setup(language: str) -> None:
    global _strings, _current_language
    resolved = language
    if resolved == "system":
        resolved = detect_system_language()
    if resolved not in AVAILABLE_LANGUAGES:
        resolved = FALLBACK_LANGUAGE
    _current_language = resolved
    if resolved == FALLBACK_LANGUAGE:
        _strings = dict(_EN_STRINGS)
    else:
        lang_strings = _load_language_strings(resolved)
        _strings = {**_EN_STRINGS, **lang_strings}


def get_current_language() -> str:
    return _current_language


def language_display_name(lang_code: str, current_lang: str | None = None) -> str:
    if current_lang is None:
        current_lang = _current_language
    names = LANGUAGE_NAMES.get(lang_code, {})
    native = names.get(lang_code, lang_code)
    in_current = names.get(current_lang, native)
    if native == in_current:
        return native
    return f"{native} ({in_current})"


def t(key: str) -> str:
    return _strings.get(key, key)


def _load_language_strings(language: str) -> dict[str, str]:
    if language == "uk":
        from sound_mixer.i18n.uk import STRINGS

        return STRINGS
    return {}
