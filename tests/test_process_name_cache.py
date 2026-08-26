from unittest.mock import patch

import pytest

from sound_mixer.audio.pycaw_backend import (
    TITLE_RETRY_INITIAL_S,
    TITLE_RETRY_MAX_S,
    _ProcessNameCache,
)

_EXE_PATH = "D:\\Games\\Voidrunner\\voidrunner.exe"
_KEY = "d:/games/voidrunner/voidrunner.exe"
_TITLE = "Voidrunner: Echoes"
_PID = 1234
_PIDS = [_PID]

_PATCH_EXE = "sound_mixer.audio.pycaw_backend.get_exe_friendly_name"
_PATCH_TITLES = "sound_mixer.audio.pycaw_backend.get_window_titles_by_pid"
_PATCH_SIBLINGS = "sound_mixer.audio.pycaw_backend._pids_with_exe_path"
_PATCH_SAME_PATH = "sound_mixer.audio.pycaw_backend._runs_from_exe_path"
_PATCH_RELATIVES = "sound_mixer.audio.pycaw_backend._pids_in_same_folder"


@pytest.fixture(autouse=True)
def running_from_group_executable():
    with patch(_PATCH_SAME_PATH, return_value=True) as same_path:
        yield same_path


@pytest.fixture(autouse=True)
def no_relatives_in_same_folder():
    with patch(_PATCH_RELATIVES, return_value=[]) as relatives:
        yield relatives


def make_cache_with_clock():
    clock = [0.0]
    return _ProcessNameCache(now=lambda: clock[0]), clock


def resolve_passes(cache, clock, key, exe_path, pids, passes=2):
    for _ in range(passes):
        cache.resolve(key, exe_path, pids)
        clock[0] += TITLE_RETRY_MAX_S


def test_get_returns_empty_for_unknown_key():
    cache = _ProcessNameCache()

    assert cache.get(_KEY) == ""


def test_description_is_used_until_a_window_title_appears():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="Aurora Browser"), patch(_PATCH_TITLES, return_value={}):
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert cache.get(_KEY) == "Aurora Browser"


def test_window_title_used_when_description_is_missing():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={_PID: _TITLE}):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS)

    assert cache.get(_KEY) == _TITLE


def test_exe_info_checked_exactly_once_regardless_of_result():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="") as mock_exe, patch(_PATCH_TITLES, return_value={}):
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    mock_exe.assert_called_once_with(_EXE_PATH)


def test_window_title_retried_until_name_appears():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, side_effect=[{}, {}, {_PID: _TITLE}, {_PID: _TITLE}]
    ) as mock_titles:
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS, passes=5)

    assert mock_titles.call_count == 4
    assert cache.get(_KEY) == _TITLE


def test_title_lookup_not_retried_within_backoff_window():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={}) as mock_titles:
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert mock_titles.call_count == 1


def test_title_lookup_retries_after_backoff_elapses():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={}) as mock_titles:
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        clock[0] += TITLE_RETRY_INITIAL_S
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert mock_titles.call_count == 2


def test_backoff_doubles_and_caps():
    cache, clock = make_cache_with_clock()

    expected_intervals = [
        TITLE_RETRY_INITIAL_S,
        TITLE_RETRY_INITIAL_S * 2,
        TITLE_RETRY_INITIAL_S * 4,
        TITLE_RETRY_INITIAL_S * 8,
        TITLE_RETRY_MAX_S,
        TITLE_RETRY_MAX_S,
    ]

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={}) as mock_titles:
        cache.resolve(_KEY, _EXE_PATH, _PIDS)
        for interval in expected_intervals:
            clock[0] += interval - 0.001
            cache.resolve(_KEY, _EXE_PATH, _PIDS)
            clock[0] += 0.001
            cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert mock_titles.call_count == 1 + len(expected_intervals)


def test_late_window_title_eventually_resolved():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, side_effect=[{}, {}, {_PID: "Late Title"}, {_PID: "Late Title"}]
    ):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS, passes=10)

    assert cache.get(_KEY) == "Late Title"


def test_no_lookups_after_the_name_is_confirmed():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value="") as mock_exe, patch(
        _PATCH_TITLES, return_value={_PID: _TITLE}
    ) as mock_titles:
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS, passes=6)

    mock_exe.assert_called_once()
    assert mock_titles.call_count == 2
    assert cache.get(_KEY) == _TITLE


def test_short_description_is_replaced_by_the_window_title_that_extends_it():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/MyGame/Game.exe"
    key = "d:/games/mygame/game.exe"

    with patch(_PATCH_EXE, return_value="game"), patch(
        _PATCH_TITLES, return_value={_PID: "Game Name Deluxe"}
    ):
        cache.resolve(key, exe_path, _PIDS)

        assert cache.get(key) == "Game Name Deluxe"

        clock[0] += TITLE_RETRY_MAX_S
        cache.resolve(key, exe_path, _PIDS)

    assert cache.get(key) == "Game Name Deluxe"


def test_runtime_description_is_replaced_by_the_window_title():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value="Web Runtime Host"), patch(
        _PATCH_TITLES, return_value={_PID: _TITLE}
    ):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS)

    assert cache.get(_KEY) == _TITLE


def test_title_with_separator_is_accepted_once_it_stays_stable():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/Starfall/starfall.exe"
    key = "d:/games/starfall/starfall.exe"

    with patch(_PATCH_EXE, return_value="Web Runtime Host"), patch(
        _PATCH_TITLES, return_value={_PID: "Starfall - Director's Cut"}
    ):
        resolve_passes(cache, clock, key, exe_path, _PIDS)

    assert cache.get(key) == "Starfall - Director's Cut"


def test_changing_title_falls_back_to_the_description():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Player/player.exe"
    key = "c:/player/player.exe"
    changing = [{_PID: "Artist %d - Song %d" % (n, n)} for n in range(6)]

    with patch(_PATCH_EXE, return_value="Media Runtime"), patch(
        _PATCH_TITLES, side_effect=changing
    ) as mock_titles:
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=len(changing))

    assert mock_titles.call_count == len(changing)
    assert cache.get(key) == "Media Runtime"


def test_a_track_title_is_never_adopted_after_the_fallback():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Player/player.exe"
    key = "c:/player/player.exe"
    changing = [{_PID: "Artist %d - Song %d" % (n, n)} for n in range(12)]

    with patch(_PATCH_EXE, return_value="Media Runtime"), patch(
        _PATCH_TITLES, side_effect=changing
    ):
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=len(changing))

    assert cache.get(key) == "Media Runtime"


def test_a_paused_track_title_is_never_adopted_after_the_fallback():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Player/player.exe"
    key = "c:/player/player.exe"
    changing = [{_PID: "Artist %d - Song %d" % (n, n)} for n in range(4)]
    paused = [{_PID: "Paused Artist - Paused Song"}] * 8

    with patch(_PATCH_EXE, return_value="Media Runtime"), patch(
        _PATCH_TITLES, side_effect=changing + paused
    ):
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=len(changing) + len(paused))

    assert cache.get(key) == "Media Runtime"


def test_title_repeating_the_description_does_not_settle_the_name():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/Voidrunner/runtime.exe"
    key = "d:/games/voidrunner/runtime.exe"

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, side_effect=[{_PID: "webruntime"}, {_PID: _TITLE}, {_PID: _TITLE}]
    ) as mock_titles:
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=3)

    assert mock_titles.call_count == 3
    assert cache.get(key) == _TITLE


def test_title_repeating_the_file_name_does_not_settle_the_name():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/MyGame/Game.exe"
    key = "d:/games/mygame/game.exe"

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, side_effect=[{_PID: "Game"}, {_PID: _TITLE}, {_PID: _TITLE}]
    ):
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=3)

    assert cache.get(key) == _TITLE


def test_placeholder_title_keeps_the_description_visible_meanwhile():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, return_value={_PID: "webruntime"}
    ):
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert cache.get(_KEY) == "webruntime"


def test_title_that_settles_after_startup_churn_is_still_adopted():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/Voidrunner/runtime.exe"
    key = "d:/games/voidrunner/runtime.exe"
    churn = [
        {_PID: "Voidrunner - Downloading 5%"},
        {_PID: "Voidrunner - Downloading 40%"},
        {_PID: "Voidrunner - Downloading 80%"},
        {_PID: "Voidrunner - Verifying"},
    ]
    settled = [{_PID: _TITLE}] * 3

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, side_effect=churn + settled
    ):
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=len(churn))

        assert cache.get(key) == "webruntime"

        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=len(settled))

    assert cache.get(key) == _TITLE


def test_splash_title_is_replaced_by_the_real_title():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, side_effect=[{_PID: "Loading"}, {_PID: _TITLE}, {_PID: _TITLE}]
    ):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, _PIDS, passes=3)

    assert cache.get(_KEY) == _TITLE


def test_title_ending_with_the_description_keeps_the_description():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Aurora/aurora.exe"
    key = "c:/aurora/aurora.exe"

    with patch(_PATCH_EXE, return_value="Aurora Browser"), patch(
        _PATCH_TITLES, return_value={_PID: "Some Page - Aurora Browser"}
    ) as mock_titles:
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=4)

    assert mock_titles.call_count == 1
    assert cache.get(key) == "Aurora Browser"


def test_dynamic_title_does_not_replace_a_description_matching_the_file_name():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Lumen/Lumen.exe"
    key = "c:/lumen/lumen.exe"

    with patch(_PATCH_EXE, return_value="Lumen"), patch(
        _PATCH_TITLES, return_value={_PID: "Some Artist - Some Song"}
    ) as mock_titles:
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=5)

    assert mock_titles.call_count == 1
    assert cache.get(key) == "Lumen"


def test_rejected_title_stops_further_lookups():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Nimbus/Nimbus.exe"
    key = "c:/nimbus/nimbus.exe"

    with patch(_PATCH_EXE, return_value="Nimbus"), patch(
        _PATCH_TITLES, return_value={_PID: "#room | Some Space - Nimbus"}
    ) as mock_titles:
        resolve_passes(cache, clock, key, exe_path, _PIDS, passes=5)

    assert mock_titles.call_count == 1
    assert cache.get(key) == "Nimbus"


def test_title_matching_the_file_name_keeps_its_own_casing():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, return_value={_PID: "Voidrunner"}
    ):
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    assert cache.get(_KEY) == "Voidrunner"


def test_different_keys_resolved_independently():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, side_effect=[{1: "App One"}, {2: "App Two"}, {1: "App One"}, {2: "App Two"}]
    ):
        for _ in range(2):
            cache.resolve("c:/one/one.exe", "C:/One/one.exe", [1])
            cache.resolve("c:/two/two.exe", "C:/Two/two.exe", [2])
            clock[0] += TITLE_RETRY_MAX_S

    assert cache.get("c:/one/one.exe") == "App One"
    assert cache.get("c:/two/two.exe") == "App Two"


def test_window_title_taken_from_another_process_of_the_same_group():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={5678: _TITLE}):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, [_PID, 5678])

    assert cache.get(_KEY) == _TITLE


def test_longest_title_wins_within_the_group():
    cache, clock = make_cache_with_clock()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, return_value={_PID: "Void", 5678: _TITLE}
    ):
        resolve_passes(cache, clock, _KEY, _EXE_PATH, [_PID, 5678])

    assert cache.get(_KEY) == _TITLE


def test_window_title_taken_from_another_instance_outside_the_audio_sessions():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/MyGame/Game.exe"
    key = "d:/games/mygame/game.exe"

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, return_value={999: _TITLE}
    ), patch(_PATCH_SIBLINGS, return_value=[_PID, 999]):
        resolve_passes(cache, clock, key, exe_path, _PIDS)

    assert cache.get(key) == _TITLE


def test_process_list_not_scanned_when_own_process_has_a_window():
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, return_value={_PID: _TITLE}
    ), patch(_PATCH_SIBLINGS) as mock_siblings:
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    mock_siblings.assert_not_called()


def test_window_title_of_a_process_with_another_executable_is_ignored():
    cache, clock = make_cache_with_clock()
    exe_path = "C:/Hostbox/hostbox.exe"
    key = "c:/hostbox/hostbox.exe"

    with patch(_PATCH_EXE, return_value="Hostbox"), patch(
        _PATCH_TITLES, return_value={999: _TITLE}
    ), patch(_PATCH_SIBLINGS, return_value=[_PID]):
        resolve_passes(cache, clock, key, exe_path, _PIDS)

    assert cache.get(key) == "Hostbox"


def test_window_title_of_another_app_with_the_same_file_name_is_ignored():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/MyGame/Game.exe"
    key = "d:/games/mygame/game.exe"

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, return_value={999: "Another Game Title"}
    ), patch(_PATCH_SIBLINGS, return_value=[_PID]) as mock_siblings:
        resolve_passes(cache, clock, key, exe_path, _PIDS)

    mock_siblings.assert_called_with(exe_path)
    assert cache.get(key) == "webruntime"


def test_window_title_taken_from_a_relative_in_the_same_folder():
    cache, clock = make_cache_with_clock()
    exe_path = "D:/Games/Voidrunner/runtime.exe"
    key = "d:/games/voidrunner/runtime.exe"

    with patch(_PATCH_EXE, return_value="webruntime"), patch(
        _PATCH_TITLES, return_value={999: _TITLE}
    ), patch(_PATCH_SIBLINGS, return_value=[_PID]), patch(
        _PATCH_RELATIVES, return_value=[999]
    ) as mock_relatives:
        resolve_passes(cache, clock, key, exe_path, _PIDS)

    mock_relatives.assert_called_with(exe_path, _PIDS, [999])
    assert cache.get(key) == _TITLE


def test_same_folder_scan_not_used_when_the_group_has_a_window(no_relatives_in_same_folder):
    cache = _ProcessNameCache()

    with patch(_PATCH_EXE, return_value=""), patch(_PATCH_TITLES, return_value={_PID: _TITLE}):
        cache.resolve(_KEY, _EXE_PATH, _PIDS)

    no_relatives_in_same_folder.assert_not_called()
