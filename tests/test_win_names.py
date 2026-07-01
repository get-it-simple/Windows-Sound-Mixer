import sys

import pytest

from sound_mixer.audio.win_names import get_exe_friendly_name, get_process_window_title


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


def test_window_title_returns_empty_for_zero_pid():
    assert get_process_window_title(0) == ""


def test_window_title_returns_empty_for_nonexistent_pid():
    assert get_process_window_title(0x7FFFFFFF) == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_window_title_returns_string():
    result = get_process_window_title(1)

    assert isinstance(result, str)
