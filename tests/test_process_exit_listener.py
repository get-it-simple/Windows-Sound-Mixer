import ctypes
from ctypes import wintypes
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QDeadlineTimer
from PySide6.QtTest import QTest

from sound_mixer.audio.process_exit_listener import ProcessExitListener
from tests.conftest import windows_only

pytestmark = windows_only


def wait_until(predicate):
    deadline = QDeadlineTimer(3000)
    while not predicate() and not deadline.hasExpired():
        QTest.qWait(10)
    assert predicate()


def test_windows_process_exit_notifies_once_without_polling(qapp, child_process):
    listener = ProcessExitListener()
    notifications = []
    listener.process_exited.connect(lambda: notifications.append(True))
    try:
        listener.sync({child_process.pid})
        QTest.qWait(30)
        assert notifications == []

        child_process.stdin.close()
        child_process.wait(timeout=10)
        wait_until(lambda: notifications == [True])

        listener.sync({child_process.pid})
        QTest.qWait(30)
        assert notifications == [True]
    finally:
        listener.stop()


@pytest.mark.parametrize("remove", [True, False])
def test_removing_or_stopping_watch_closes_handle_and_silences_exit(qapp, child_process, remove):
    listener = ProcessExitListener()
    notifications = []
    listener.process_exited.connect(lambda: notifications.append(True))
    listener.sync({child_process.pid})
    handle = listener._watches[child_process.pid][0]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetHandleInformation.restype = wintypes.BOOL
    flags = wintypes.DWORD()
    assert kernel32.GetHandleInformation(handle, ctypes.byref(flags))

    if remove:
        listener.sync(set())
    else:
        listener.stop()

    assert not kernel32.GetHandleInformation(handle, ctypes.byref(flags))
    child_process.stdin.close()
    child_process.wait(timeout=10)
    QTest.qWait(30)
    assert notifications == []
    listener.stop()


def test_process_that_exited_before_registration_still_notifies(qapp, child_process):
    child_process.stdin.close()
    child_process.wait(timeout=10)
    listener = ProcessExitListener()
    notifications = []
    listener.process_exited.connect(lambda: notifications.append(True))
    try:
        listener.sync({child_process.pid})
        wait_until(lambda: notifications == [True])
    finally:
        listener.stop()


def test_access_denied_does_not_poll_or_emit_exit(qapp, monkeypatch):
    listener = ProcessExitListener()
    kernel32 = Mock()
    kernel32.OpenProcess.return_value = None
    listener._kernel32 = kernel32
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5)
    notifications = []
    listener.process_exited.connect(lambda: notifications.append(True))
    try:
        listener.sync({42})
        listener.sync({42})
        QTest.qWait(30)
        assert kernel32.OpenProcess.call_count == 1
        assert notifications == []
    finally:
        listener.stop()
