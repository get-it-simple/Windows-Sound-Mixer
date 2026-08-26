import contextlib
import ctypes
import os
import sys

import pytest

from sound_mixer.audio.win_names import (
    first_version_string,
    get_exe_friendly_name,
    get_window_titles_by_pid,
    is_named_app_window,
)

NUL = "\x00"

_WS_POPUP = 0x80000000
_WS_VISIBLE = 0x10000000
_WS_EX_TOOLWINDOW = 0x00000080
_OFFSCREEN = -32000


@contextlib.contextmanager
def owned_window(title: str, ex_style: int = 0):
    user32 = ctypes.WinDLL("user32")
    user32.CreateWindowExW.restype = ctypes.c_void_p
    user32.CreateWindowExW.argtypes = [
        ctypes.c_uint,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    user32.DestroyWindow.argtypes = [ctypes.c_void_p]

    def create(style, owner, name):
        return user32.CreateWindowExW(
            ex_style if owner else 0,
            "STATIC",
            name,
            style,
            _OFFSCREEN,
            _OFFSCREEN,
            1,
            1,
            owner,
            None,
            None,
            None,
        )

    holder = create(_WS_POPUP, None, "holder")
    if not holder:
        pytest.skip("cannot create a window in this session")
    window = create(_WS_POPUP | _WS_VISIBLE, holder, title)
    if not window:
        user32.DestroyWindow(holder)
        pytest.skip("cannot create a window in this session")
    try:
        yield window
    finally:
        user32.DestroyWindow(window)
        user32.DestroyWindow(holder)


def test_returns_empty_string_for_empty_path():
    assert get_exe_friendly_name("") == ""


def test_returns_empty_string_for_nonexistent_path():
    assert get_exe_friendly_name("C:\\nonexistent\\no_such_file.exe") == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_returns_nonempty_string_for_python_exe():
    name = get_exe_friendly_name(sys.executable)

    assert isinstance(name, str)
    assert len(name) > 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_return_value_is_stripped_of_whitespace():
    name = get_exe_friendly_name(sys.executable)

    assert name == name.strip()


def test_window_titles_returns_a_mapping():
    titles = get_window_titles_by_pid()

    assert isinstance(titles, dict)
    assert all(isinstance(pid, int) for pid in titles)
    assert all(isinstance(title, str) for title in titles.values())


def test_window_titles_contains_no_empty_entries():
    titles = get_window_titles_by_pid()

    assert all(pid > 0 for pid in titles)
    assert all(title.strip() == title and title for title in titles.values())


def test_version_string_stops_at_the_first_terminator():
    raw = "Starfall Demo%s0%sFileVersion%s0.54.0" % (NUL, NUL, NUL)

    assert first_version_string(raw) == "Starfall Demo"


def test_version_string_without_terminator_is_stripped():
    assert first_version_string("  My Game  ") == "My Game"


def test_version_string_that_starts_with_a_terminator_is_empty():
    assert first_version_string("%sjunk" % NUL) == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_exe_name_has_no_embedded_terminators():
    name = get_exe_friendly_name(sys.executable)

    assert NUL not in name


def test_a_visible_titled_top_level_window_is_used():
    assert is_named_app_window(visible=True, top_level=True, length=9)
    assert is_named_app_window(visible=1, top_level=True, length=1)


def test_hidden_child_and_untitled_windows_are_skipped():
    assert not is_named_app_window(visible=False, top_level=True, length=9)
    assert not is_named_app_window(visible=True, top_level=False, length=9)
    assert not is_named_app_window(visible=True, top_level=True, length=0)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_window_owned_by_a_hidden_window_is_still_reported():
    title = "Owned Window Regression Probe"

    with owned_window(title):
        titles = get_window_titles_by_pid()

    assert titles.get(os.getpid()) == title


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_a_tool_window_owned_by_a_hidden_window_is_still_reported():
    title = "Tool Window Regression Probe"

    with owned_window(title, ex_style=_WS_EX_TOOLWINDOW):
        titles = get_window_titles_by_pid()

    assert titles.get(os.getpid()) == title
