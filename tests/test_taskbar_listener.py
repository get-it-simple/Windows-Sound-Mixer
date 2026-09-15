from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QEvent
from PySide6.QtTest import QTest

from sound_mixer.overlay import taskbar_listener
from sound_mixer.overlay.taskbar_listener import TaskbarListener


@pytest.fixture
def listener(qapp):
    listener = TaskbarListener()
    api = Mock()
    api.SetWinEventHook.side_effect = range(0x100000001, 0x100000010)
    listener._user32 = api
    listener.start()
    yield listener, api
    listener.stop()


def test_hooks_use_exact_events_and_skip_own_process(listener):
    listener, api = listener
    calls = api.SetWinEventHook.call_args_list
    assert [call.args[:2] for call in calls] == [
        (0x0003, 0x0003), (0x8002, 0x8002), (0x8004, 0x8004), (0x800B, 0x800B),
    ]
    assert all(call.args[2] is None and call.args[4:] == (0, 0, 0x0002) for call in calls)
    listener.start()
    assert api.SetWinEventHook.call_count == 4
    listener.stop()
    assert [call.args for call in api.UnhookWinEvent.call_args_list] == [
        (0x100000001,), (0x100000002,), (0x100000003,), (0x100000004,),
    ]
    listener.stop()
    assert api.UnhookWinEvent.call_count == 4


@pytest.mark.parametrize("event", [0x8002, 0x8004, 0x800B])
@pytest.mark.parametrize("class_name", ["Shell_TrayWnd", "Shell_SecondaryTrayWnd", "OtherWindow"])
def test_only_taskbar_window_events_notify(qapp, listener, event, class_name):
    listener, api = listener
    notifications = []
    listener.changed.connect(lambda: notifications.append(True))

    def get_class(hwnd, buffer, size):
        assert hwnd == 0x100000005
        buffer.value = class_name
        return len(class_name)

    api.GetClassNameW.side_effect = get_class
    listener._on_event(1, event, 0x100000005, 0, 0, 1, 0)
    qapp.sendPostedEvents()
    assert notifications == ([True] if class_name != "OtherWindow" else [])


def test_foreground_burst_notifies_once_and_never_polls(qapp, listener):
    listener, api = listener
    notifications = []
    listener.changed.connect(lambda: notifications.append(True))
    for hwnd in (42, 43, 44):
        listener._on_event(1, 0x0003, hwnd, 0, 0, 1, 0)
    assert notifications == []
    qapp.sendPostedEvents()
    assert notifications == [True]
    QTest.qWait(600)
    assert notifications == [True]
    api.GetClassNameW.assert_not_called()
    listener._on_event(1, 0x0003, 45, 0, 0, 1, 0)
    qapp.sendPostedEvents()
    assert notifications == [True, True]


@pytest.mark.parametrize("hwnd, object_id, child_id", [(0, 0, 0), (42, -4, 0), (42, 0, 1)])
def test_invalid_or_child_events_do_no_work(qapp, listener, hwnd, object_id, child_id):
    listener, api = listener
    notifications = []
    listener.changed.connect(lambda: notifications.append(True))
    listener._on_event(1, 0x800B, hwnd, object_id, child_id, 1, 0)
    qapp.sendPostedEvents()
    api.GetClassNameW.assert_not_called()
    assert notifications == []


def test_stop_cancels_pending_notification_and_releases_hooks(qapp, listener):
    listener, api = listener
    notifications = []
    listener.changed.connect(lambda: notifications.append(True))
    listener._on_event(1, 0x0003, 42, 0, 0, 1, 0)
    listener.stop()
    qapp.sendPostedEvents()
    listener._on_event(1, 0x0003, 42, 0, 0, 1, 0)
    qapp.sendPostedEvents()
    assert notifications == []
    assert api.UnhookWinEvent.call_count == 4
    listener.start()
    listener._on_event(5, 0x0003, 42, 0, 0, 1, 0)
    qapp.sendPostedEvents()
    assert notifications == [True]


def test_hook_failure_releases_partial_registration_without_retrying(qapp, listener, caplog):
    listener, api = listener
    listener.stop()
    api.reset_mock()
    api.SetWinEventHook.side_effect = [123, None]
    listener.start()
    api.UnhookWinEvent.assert_called_once_with(123)
    assert "Cannot watch taskbar events" in caplog.text
    QTest.qWait(600)
    assert api.SetWinEventHook.call_count == 2


def test_parent_destruction_releases_native_hooks(qapp):
    parent = QObject()
    listener = TaskbarListener(parent)
    api = Mock()
    api.SetWinEventHook.side_effect = range(1, 5)
    listener._user32 = api
    listener.start()
    parent.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert api.UnhookWinEvent.call_count == 4


def test_listener_is_noop_off_windows(qapp, monkeypatch):
    monkeypatch.setattr(taskbar_listener, "sys", SimpleNamespace(platform="linux"))
    listener = TaskbarListener()
    listener.start()
    listener.stop()
