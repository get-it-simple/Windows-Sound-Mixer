import ctypes
from dataclasses import replace
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest
from PySide6.QtCore import QEventLoop, QRect

from sound_mixer.media import identity
from sound_mixer.media.controller import _MediaWorker
from sound_mixer.media.model import MediaItem, MediaOwner, PausedSessions, attach_owners
from sound_mixer.overlay.window import OverlayWindow
from test_playing_media import make_overlay


@pytest.fixture
def window_api(monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows media identities")
    from comtypes import GUID

    class Variant(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3), ("data", ctypes.c_void_p * 2)]

    apis = []

    def create(windows):
        buffers = {}
        stores = {}
        released = []
        cleared = []

        @ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(Variant))
        def get_value(store, key, value):
            value.contents.vt = 31
            value.contents.data[0] = ctypes.addressof(buffers[store])
            return 0

        @ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
        def release(store):
            released.append(store)
            return 0

        table = (ctypes.c_void_p * 8)()
        table[2] = ctypes.cast(release, ctypes.c_void_p).value
        table[5] = ctypes.cast(get_value, ctypes.c_void_p).value
        for hwnd, pid, app_id in windows:
            store = ctypes.pointer(ctypes.cast(table, ctypes.POINTER(ctypes.c_void_p)))
            address = ctypes.cast(store, ctypes.c_void_p).value
            buffers[address] = ctypes.create_unicode_buffer(app_id)
            stores[hwnd] = store

        def window_pid(hwnd, output):
            pid = next(pid for handle, pid, app_id in windows if handle == hwnd)
            ctypes.cast(output, ctypes.POINTER(ctypes.wintypes.DWORD))[0] = pid
            return 1

        def get_store(hwnd, iid, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(stores[hwnd], ctypes.c_void_p)
            return 0

        def enumerate_windows(callback, param):
            for hwnd, pid, app_id in windows:
                assert callback(hwnd, param)
            return True

        kernel = SimpleNamespace(OpenProcess=Mock(return_value=0), CloseHandle=Mock(), GetApplicationUserModelId=Mock())
        user = SimpleNamespace(GetWindowThreadProcessId=Mock(side_effect=window_pid), EnumWindows=Mock(side_effect=enumerate_windows))
        shell = SimpleNamespace(SHGetPropertyStoreForWindow=Mock(side_effect=get_store))
        ole = SimpleNamespace(PropVariantClear=Mock(side_effect=lambda value: cleared.append(value)))
        libraries = {"kernel32": kernel, "user32": user, "shell32": shell, "ole32": ole}
        monkeypatch.setattr(identity.ctypes, "WinDLL", lambda name, **kwargs: libraries[name])
        api = SimpleNamespace(shell=shell, released=released, cleared=cleared, callbacks=(get_value, release),
                              buffers=buffers, stores=stores, table=table, guid=GUID)
        apis.append(api)
        return api

    return create


@pytest.mark.parametrize("profile", ["Chrome.UserData.Default", "Chrome.UserData.Profile2"])
def test_profile_window_matches_audio_process_by_full_executable(window_api, monkeypatch, profile):
    api = window_api([(1000, 100, profile), (1001, 100, "Chrome.UserData.Profile3")])
    lookup = Mock(return_value=SimpleNamespace(exe=lambda: "C:\\Browser\\CHROME.EXE"))
    monkeypatch.setattr(psutil, "Process", lookup)
    owner = MediaOwner("c:/browser/chrome.exe", (200,))
    identities = identity.application_identities((owner,))
    assert identities[owner.key] == {profile.casefold(), "chrome.userdata.profile3"}
    items = attach_owners((MediaItem("one", profile), MediaItem("two", "Chrome.UserData.Profile3")), (owner,), identities)
    assert [item.owner_key for item in items] == [owner.key, owner.key]
    lookup.assert_called_once_with(100)
    assert len(api.released) == len(api.cleared) == 2


@pytest.mark.parametrize("failure", [psutil.NoSuchProcess(100), psutil.AccessDenied(100)])
def test_inaccessible_window_process_is_skipped_and_cached(window_api, monkeypatch, failure):
    api = window_api([(1000, 100, "inaccessible"), (1001, 100, "inaccessible")])
    lookup = Mock(side_effect=failure)
    monkeypatch.setattr(psutil, "Process", lookup)
    owner = MediaOwner("c:/browser/chrome.exe", (200,))
    assert identity.application_identities((owner,)) == {owner.key: set()}
    lookup.assert_called_once_with(100)
    api.shell.SHGetPropertyStoreForWindow.assert_not_called()


def test_same_executable_names_do_not_cross_installations(window_api, monkeypatch):
    api = window_api([(1000, 100, "first.profile"), (1001, 101, "second.profile"), (1002, 102, "unrelated.profile")])
    paths = {100: "c:/first/chrome.exe", 101: "d:/second/chrome.exe", 102: "e:/unrelated/chrome.exe"}
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(exe=lambda: paths[pid]))
    owners = (MediaOwner(paths[100], (200,)), MediaOwner(paths[101], (201,)))
    identities = identity.application_identities(owners)
    assert identities == {owners[0].key: {"first.profile"}, owners[1].key: {"second.profile"}}
    assert len(api.released) == len(api.cleared) == 2


def test_ambiguous_window_identity_stays_unmatched(window_api, monkeypatch):
    window_api([(1000, 100, "same.profile"), (1001, 101, "same.profile")])
    paths = {100: "c:/first/chrome.exe", 101: "d:/second/chrome.exe"}
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(exe=lambda: paths[pid]))
    owners = (MediaOwner(paths[100], (200,)), MediaOwner(paths[101], (201,)))
    identities = identity.application_identities(owners)
    assert all(values == {"same.profile"} for values in identities.values())
    assert attach_owners((MediaItem("one", "same.profile"),), owners, identities)[0].owner_key is None


def test_window_lookup_does_not_guess_from_bare_executable_name(window_api, monkeypatch):
    api = window_api([(1000, 100, "Chrome.UserData.Profile2")])
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(exe=lambda: "c:/browser/chrome.exe"))
    owner = MediaOwner("chrome.exe", (200,))
    assert identity.application_identities((owner,)) == {owner.key: set()}
    api.shell.SHGetPropertyStoreForWindow.assert_not_called()


def test_known_audio_pid_keeps_window_identity_without_process_lookup(window_api, monkeypatch):
    api = window_api([(1000, 200, "known.application")])
    lookup = Mock(side_effect=psutil.AccessDenied(200))
    monkeypatch.setattr(psutil, "Process", lookup)
    owner = MediaOwner("legacy.exe", (200,))
    assert identity.application_identities((owner,)) == {owner.key: {"known.application"}}
    lookup.assert_not_called()
    assert len(api.released) == len(api.cleared) == 1


def test_worker_retries_unmatched_source_on_next_snapshot(monkeypatch):
    owner = MediaOwner("c:/browser/chrome.exe", (200,))
    available = False
    queries = []

    def identities(owners):
        queries.append(owners)
        return {owner.key: {"chrome.userdata.profile2"} if available else set()}

    monkeypatch.setattr("sound_mixer.media.controller.application_identities", identities)
    delivered = []
    worker = _MediaWorker(1, lambda generation, items: delivered.append(items), (owner,), None, PausedSessions())
    item = MediaItem("one", "Chrome.UserData.Profile2", "Track")
    worker.publish((item,))
    assert delivered[-1][0].owner_key is None
    available = True
    worker.publish((replace(item, title="New track"),))
    assert delivered[-1][0].owner_key == owner.key
    assert len(queries) == 2
    worker.publish((replace(item, title="Another track"),))
    assert delivered[-1][0].owner_key == owner.key
    assert len(queries) == 2


@pytest.mark.parametrize("mode", ["horizontal", "vertical"])
def test_matched_profiles_use_browser_cards_without_source_prefix(qapp, fake_backend, settings, monkeypatch, mode):
    settings.set_layout_mode(mode)
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(0, 0, 1600, 1600))
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        owner = MediaOwner(overlay._model.entries[1].key, (100,))
        sources = ("Chrome.UserData.Profile2", "Chrome.UserData.Profile3")
        items = tuple(MediaItem(str(i), source, f"Track {i}", can_pause=True, generation=1) for i, source in enumerate(sources))
        items = attach_owners(items, (owner,), {owner.key: {source.casefold() for source in sources}})
        overlay.set_media_items(items)
        for _ in range(6):
            qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        cards = overlay._footer_cards if mode == "vertical" else overlay._entry_widgets[1]._media_cards
        assert [card.title.text for card in cards] == ["Track 0", "Track 1"]
        assert [card.item.session_id for card in cards] == ["0", "1"]
        assert len(overlay._media_connections._links) == (2 if mode == "vertical" else 0)
    finally:
        overlay.close()
