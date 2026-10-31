import asyncio
from types import SimpleNamespace
import time
import sys

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from sound_mixer.media.model import MediaItem, MediaOwner, match_owner
from sound_mixer.media.controller import MediaController
from sound_mixer.media.provider import WindowsMediaProvider, decode_artwork
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.media_card import MediaCard
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings.migrations import migrate
from sound_mixer.settings.schema import CURRENT_VERSION
from sound_mixer.settings.store import SettingsStore
from sound_mixer.settings_window.window import SettingsWindow


class Session:
    def __init__(self, source="player.exe", title="Track", status=4):
        self.source_app_user_model_id = source
        self.title = title
        self.status = status
        self.media = {}
        self.playback = {}
        self.reads = 0
        self.gate = None

    def add_media_properties_changed(self, callback):
        self.media[1] = callback
        return 1

    def add_playback_info_changed(self, callback):
        self.playback[2] = callback
        return 2

    def remove_media_properties_changed(self, token):
        del self.media[token]

    def remove_playback_info_changed(self, token):
        del self.playback[token]

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self.status)

    async def try_get_media_properties_async(self):
        self.reads += 1
        title = self.title
        if self.gate is not None:
            await self.gate.wait()
        return SimpleNamespace(title=title, thumbnail=None)

    def emit(self, metadata=False):
        for callback in list((self.media if metadata else self.playback).values()):
            callback(self, None)


class Manager:
    def __init__(self, sessions):
        self.sessions = sessions
        self.callbacks = {}

    def add_sessions_changed(self, callback):
        self.callbacks[1] = callback
        return 1

    def remove_sessions_changed(self, token):
        del self.callbacks[token]

    def get_sessions(self):
        return self.sessions

    def emit(self):
        for callback in list(self.callbacks.values()):
            callback(self, None)


async def wait_for(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.01)


def test_provider_initial_snapshot_events_no_polling_and_cleanup():
    async def scenario():
        first, second = Session(), Session("other.exe", "Other")
        manager = Manager([first, second])
        snapshots = []

        async def factory():
            return manager

        task = asyncio.create_task(WindowsMediaProvider(snapshots.append, factory).run())
        try:
            await wait_for(lambda: snapshots and len(snapshots[-1]) == 2)
            assert {item.title for item in snapshots[-1]} == {"Track", "Other"}
            await asyncio.sleep(0.15)
            assert first.reads == second.reads == 1
            first.status = 5
            first.emit()
            await wait_for(lambda: len(snapshots[-1]) == 1)
            first.title = "New track"
            first.status = 4
            first.emit()
            await wait_for(lambda: any(item.title == "New track" for item in snapshots[-1]))
            first.title = "Renamed"
            for _ in range(10):
                first.emit(metadata=True)
            await wait_for(lambda: any(item.title == "Renamed" for item in snapshots[-1]))
            assert first.reads == 3
            manager.sessions.remove(second)
            manager.emit()
            await wait_for(lambda: len(snapshots[-1]) == 1)
            assert not second.media and not second.playback
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert not manager.callbacks and not first.media and not first.playback
    asyncio.run(scenario())


def test_provider_discards_metadata_changed_during_read():
    async def scenario():
        session = Session()
        session.gate = asyncio.Event()
        snapshots = []

        async def factory():
            return Manager([session])

        task = asyncio.create_task(WindowsMediaProvider(snapshots.append, factory).run())
        try:
            await wait_for(lambda: session.reads == 1)
            session.title = "Latest"
            session.emit(metadata=True)
            await asyncio.sleep(0.02)
            session.gate.set()
            await wait_for(lambda: snapshots and any(item.title == "Latest" for item in snapshots[-1]))
            assert not any(item.title == "Track" for items in snapshots for item in items)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize("source,expected", [("generic.identity", "c:/one/player.exe"),
    ("C:/ONE/PLAYER.EXE", "c:/one/player.exe"), ("player.exe", None), ("other.exe", "c:/other.exe"), ("unknown", None)])
def test_owner_matching_is_generic_and_unambiguous(source, expected):
    owners = (MediaOwner("c:/one/player.exe", (1,)), MediaOwner("d:/two/player.exe", (2,)), MediaOwner("c:/other.exe", (3,)))
    identities = {owners[0].key: {"generic.identity"}}
    assert match_owner(source, owners, identities) == expected


def test_duplicate_system_id_is_not_attached_arbitrarily():
    owners = (MediaOwner("c:/a.exe", (1,)), MediaOwner("d:/a.exe", (2,)))
    assert match_owner("same.id", owners, {owner.key: {"same.id"} for owner in owners}) is None


def test_media_settings_migration_persistence_and_dialog_cancel(settings, qapp):
    original = {"version": 14, "app_volumes": {"app.exe": {"volume": 0.3}}}
    result = migrate(original)
    assert result["version"] == CURRENT_VERSION
    assert result["playing_media_enabled"] is False
    assert result["app_volumes"] == original["app_volumes"]
    assert "playing_media_enabled" not in original
    dialog = SettingsWindow(settings)
    dialog._playing_media_checkbox.setChecked(True)
    dialog.reject()
    assert not settings.get_playing_media_enabled()
    dialog = SettingsWindow(settings)
    dialog._playing_media_checkbox.setChecked(True)
    dialog.accept()
    restored = SettingsStore(settings.path)
    restored.load()
    assert restored.get_playing_media_enabled()


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0, 3.0])
def test_media_card_wraps_long_plain_text_with_ellipsis(qapp, scale):
    title = "<b>Plain title</b> " + "verylongword" * 100
    card = MediaCard(MediaItem("1", "source", title), scale)
    card.resize(round(220 * scale), card.sizeHint().height())
    card.show()
    qapp.processEvents()
    lines = card.title.lines()
    assert 1 < len(lines) <= 4
    assert lines[-1].endswith("…")
    assert card.title.toolTip() == title
    assert card.title.height() < card.cover.height()
    assert card.buttons["pause"].geometry().bottom() <= card.cover.height()
    assert card.owner_icon.isHidden()
    assert not card.cover.pixmap().isNull()
    card.close()


def test_artwork_decode_scales_and_rejects_invalid_data(qapp):
    image = QImage(600, 400, QImage.Format.Format_RGB32)
    image.fill(0x2288AA)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    decoded = decode_artwork(bytes(buffer.data()))
    assert decoded.width() == 192 and decoded.height() == 128
    assert decode_artwork(b"invalid").isNull()


def make_overlay(qapp, fake_backend, settings, monkeypatch):
    monkeypatch.setattr(OverlayWindow, "_warm_up_acrylic", lambda self: None)
    overlay = OverlayWindow(MixerModel(fake_backend, settings), settings)
    overlay.show()
    qapp.processEvents()
    return overlay


def test_media_moves_between_layouts_and_preserves_controls(qapp, fake_backend, settings, monkeypatch):
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        owner = overlay._model.entries[1]
        item = MediaItem("1", "source", "Title", owner_key=owner.key)
        original_height = overlay.height()
        overlay.set_media_items((item,))
        qapp.processEvents()
        widget = overlay._entry_widgets[1]
        assert len(widget._media_cards) == 1
        assert overlay.height() > original_height
        assert widget._media_cards[0].geometry().top() >= widget._media_controls.geometry().bottom()
        overlay.set_layout_mode("vertical")
        qapp.processEvents()
        assert not widget._media_cards
        assert len(overlay._footer_cards) == 1
        assert not overlay._footer_cards[0].owner_icon.isVisible()
        assert overlay._media_footer.geometry().top() >= overlay._main_content.geometry().bottom()
        overlay.set_layout_mode("horizontal")
        qapp.processEvents()
        assert len(widget._media_cards) == 1 and not overlay._footer_cards
        overlay.set_media_items(())
        qapp.processEvents()
        assert overlay.height() == original_height
        widget._slider.setValue(37)
        assert overlay._model.entries[1].volume == pytest.approx(0.37)
        assert not widget._slider.isHidden()
    finally:
        overlay.close()


def test_vertical_multiple_apps_show_owner_icons_and_unmatched_media(qapp, fake_backend, settings, monkeypatch):
    settings.set_layout_mode("vertical")
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        entries = overlay._model.entries[1:]
        items = tuple(MediaItem(str(index), entry.key, "Song", owner_key=entry.key) for index, entry in enumerate(entries))
        overlay.set_media_items(items + (MediaItem("unmatched", "unknown.source", "Unmatched"),))
        qapp.processEvents()
        assert len(overlay._footer_cards) == 3
        assert all(card.owner_icon.isVisible() for card in overlay._footer_cards)
        assert "unknown.source" in overlay._footer_cards[-1].title.text
        assert len(overlay._media_connections._links) == 2
        connections = overlay._media_connections.grab().toImage()
        colored = sum(1 for y in range(overlay._main_content.height(), connections.height())
                      for x in range(connections.width())
                      if (color := connections.pixelColor(x, y)).blue() > 100 and color.blue() > color.red() * 1.2)
        assert colored > 10
        assert overlay._footer_cards[1].y() > overlay._footer_cards[0].y()
        assert not overlay.grab().isNull()
    finally:
        overlay.close()


def test_hidden_owner_media_follows_expansion(qapp, fake_backend, settings, monkeypatch):
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        entry = overlay._model.entries[1]
        settings.add_ignored_app(entry.key)
        overlay._model.refresh()
        overlay.refresh_view()
        overlay.set_media_items((MediaItem("1", "source", "Hidden", owner_key=entry.key),))
        assert not overlay._footer_cards
        assert not any(widget._media_cards for widget in overlay._entry_widgets + overlay._ignored_widgets)
        overlay._on_expand_ignored()
        assert len(overlay._ignored_widgets[0]._media_cards) == 1
    finally:
        overlay.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows media controller")
def test_controller_visibility_enablement_reopen_and_stale_results(qapp, monkeypatch):
    monkeypatch.setattr("sound_mixer.media.controller.application_identities", lambda owners: {})
    providers = []

    class Provider:
        def __init__(self, publish, **kwargs):
            self.publish = publish
            self.closed = False
            self.actions = []
            providers.append(self)

        def request_action(self, session_id, action):
            self.actions.append((session_id, action))

        async def run(self):
            try:
                self.publish((MediaItem("1", "source", "Initial"),))
                await asyncio.Future()
            finally:
                self.closed = True

    def until(predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
        assert predicate()

    controller = MediaController(provider_factory=Provider)
    try:
        controller.set_visible(True)
        assert not providers
        controller.set_enabled(True)
        until(lambda: controller.items)
        assert controller.items[0].title == "Initial"
        old_generation = controller._generation
        controller.set_visible(True)
        controller.set_enabled(True)
        assert len(providers) == 1
        controller.set_visible(False)
        assert not controller.items
        until(lambda: providers[0].closed)
        controller._delivered.emit(old_generation, (MediaItem("old", "source", "Stale"),))
        qapp.processEvents()
        assert not controller.items
        controller.set_visible(True)
        until(lambda: len(providers) == 2 and controller.items)
        controller.request_action("1", old_generation, "pause")
        controller.request_action("1", controller._generation, "next")
        until(lambda: providers[1].actions)
        assert providers[1].actions == [("1", "next")]
        controller.set_enabled(False)
        until(lambda: providers[1].closed)
        assert not controller.items
    finally:
        controller.shutdown()


def test_provider_failure_does_not_remove_healthy_session():
    async def scenario():
        healthy, failing = Session("healthy.exe", "Healthy"), Session()

        async def fail():
            raise OSError("Session closed")

        failing.try_get_media_properties_async = fail
        snapshots = []

        async def factory():
            return Manager([healthy, failing])

        task = asyncio.create_task(WindowsMediaProvider(snapshots.append, factory).run())
        try:
            await wait_for(lambda: snapshots and any(item.title == "Healthy" for item in snapshots[-1]))
            assert len(snapshots[-1]) == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())
