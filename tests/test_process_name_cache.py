from unittest.mock import patch

from sound_mixer.audio.pycaw_backend import _ProcessNameCache

_EXE_PATH = "C:\\Games\\game.exe"
_KEY = "game.exe"
_PID = 1234

_PATCH_EXE = "sound_mixer.audio.pycaw_backend.get_exe_friendly_name"
_PATCH_WIN = "sound_mixer.audio.pycaw_backend.get_process_window_title"


def test_get_returns_empty_for_unknown_key():
    cache = _ProcessNameCache()

    assert cache.get(_KEY) == ""


def test_exe_info_used_when_available():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="My Game"), patch(_PATCH_WIN, return_value=""):
        cache.resolve(_KEY, _EXE_PATH, _PID)

    assert cache.get(_KEY) == "My Game"


def test_window_title_used_as_fallback_when_exe_info_empty():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_WIN, return_value="My Game"):
        cache.resolve(_KEY, _EXE_PATH, _PID)

    assert cache.get(_KEY) == "My Game"


def test_exe_info_checked_exactly_once_regardless_of_result():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="") as mock_exe, patch(_PATCH_WIN, return_value=""):
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)

    mock_exe.assert_called_once_with(_EXE_PATH)


def test_window_title_retried_each_call_until_name_appears():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_WIN, side_effect=["", "", "My Game"]) as mock_win:
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)

    assert mock_win.call_count == 3
    assert cache.get(_KEY) == "My Game"


def test_no_calls_after_name_found_via_exe_info():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="My Game") as mock_exe, patch(_PATCH_WIN) as mock_win:
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)

    mock_exe.assert_called_once()
    mock_win.assert_not_called()


def test_no_calls_after_name_found_via_window_title():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="") as mock_exe, patch(_PATCH_WIN, return_value="My Game") as mock_win:
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)
        cache.resolve(_KEY, _EXE_PATH, _PID)

    mock_exe.assert_called_once()
    mock_win.assert_called_once()


def test_window_title_not_called_when_exe_info_succeeds():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="Instant Name"), patch(_PATCH_WIN) as mock_win:
        cache.resolve(_KEY, _EXE_PATH, _PID)

    mock_win.assert_not_called()


def test_different_keys_resolved_independently():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_WIN, side_effect=["App A", "App B"]):
        cache.resolve("a.exe", "C:\\a.exe", 1)
        cache.resolve("b.exe", "C:\\b.exe", 2)

    assert cache.get("a.exe") == "App A"
    assert cache.get("b.exe") == "App B"
