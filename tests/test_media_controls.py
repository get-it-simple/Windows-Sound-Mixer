import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QToolButton

from sound_mixer.media.model import MediaItem, PausedSessions
from sound_mixer.media.provider import WindowsMediaProvider
from sound_mixer.overlay.media_card import MediaCard
from test_playing_media import Manager, Session, wait_for


class ControllableSession(Session):
    def __init__(self, source="player.exe", **kwargs):
        super().__init__(source, **kwargs)
        self.controls = SimpleNamespace(is_previous_enabled=True, is_next_enabled=True,
                                        is_play_enabled=True, is_pause_enabled=True,
                                        is_play_pause_toggle_enabled=False)
        self.calls = []
        self.command_gate = None
        self.result = True

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self.status, controls=self.controls)

    async def _command(self, action):
        self.calls.append(action)
        if action in {"play", "pause", "toggle"}:
            self.status = 5 if action == "pause" or (action == "toggle" and self.status == 4) else 4
            self.emit()
        else:
            self.title = f"Track after {action}"
            self.emit(metadata=True)
        if self.command_gate is not None:
            await self.command_gate.wait()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    async def try_play_async(self):
        return await self._command("play")

    async def try_pause_async(self):
        return await self._command("pause")

    async def try_toggle_play_pause_async(self):
        return await self._command("toggle")

    async def try_skip_previous_async(self):
        return await self._command("previous")

    async def try_skip_next_async(self):
        return await self._command("next")


@asynccontextmanager
async def running(sessions, memory=None, generation=1):
    manager = Manager(sessions)
    snapshots = []

    async def factory():
        return manager

    provider = WindowsMediaProvider(snapshots.append, factory, paused_sessions=memory, generation=generation)
    task = asyncio.create_task(provider.run())
    try:
        await wait_for(lambda: snapshots)
        yield provider, snapshots, manager
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_own_pause_before_acknowledgement_is_retained_and_reopens():
    async def scenario():
        session = ControllableSession()
        memory = PausedSessions()
        async with running([session], memory) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            key = snapshots[-1][0].session_id
            session.command_gate = asyncio.Event()
            provider.request_action(key, "pause")
            await wait_for(lambda: session.status == 5 and snapshots[-1][0].playback_state == "paused")
            assert snapshots[-1][0].pending_action == "pause"
            assert not memory.contains(session)
            provider.request_action(key, "pause")
            assert session.calls == ["pause"]
            session.command_gate.set()
            await wait_for(lambda: memory.contains(session) and not snapshots[-1][0].pending_action)
        assert not session.media and not session.playback
        async with running([session], memory, generation=2) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            item = snapshots[-1][0]
            assert item.playback_state == "paused" and item.generation == 2
            provider.request_action(item.session_id, "play")
            await wait_for(lambda: snapshots[-1] and snapshots[-1][0].playback_state == "playing")
            assert not memory.contains(session)
            session.status = 5
            session.emit()
            await wait_for(lambda: snapshots[-1] == ())
    asyncio.run(scenario())


@pytest.mark.parametrize("result", [False, OSError("Rejected")])
def test_failed_pause_does_not_retain_external_paused_state(result):
    async def scenario():
        session = ControllableSession()
        session.result = result
        memory = PausedSessions()
        async with running([session], memory) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            provider.request_action(snapshots[-1][0].session_id, "pause")
            await wait_for(lambda: session.calls and snapshots[-1] == ())
            assert not memory.contains(session)
    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["previous", "next", "pause"])
def test_commands_target_only_the_selected_session(action):
    async def scenario():
        first, second = ControllableSession("same.exe"), ControllableSession("same.exe")
        async with running([first, second]) as (provider, snapshots, manager):
            await wait_for(lambda: len(snapshots[-1]) == 2)
            provider.request_action(snapshots[-1][1].session_id, action)
            await wait_for(lambda: second.calls)
            assert second.calls == [action] and first.calls == []
            if action in {"previous", "next"}:
                await wait_for(lambda: any(item.title == f"Track after {action}" for item in snapshots[-1]))
    asyncio.run(scenario())


def test_command_revalidates_capabilities_and_supports_toggle_only_players():
    async def scenario():
        session = ControllableSession()
        session.controls.is_play_enabled = session.controls.is_pause_enabled = False
        session.controls.is_play_pause_toggle_enabled = True
        async with running([session]) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            key = snapshots[-1][0].session_id
            session.controls.is_next_enabled = False
            provider.request_action(key, "next")
            await asyncio.sleep(0.07)
            assert not session.calls
            provider.request_action(key, "pause")
            await wait_for(lambda: snapshots[-1][0].playback_state == "paused" and not snapshots[-1][0].pending_action)
            provider.request_action(key, "play")
            await wait_for(lambda: snapshots[-1][0].playback_state == "playing")
            assert session.calls == ["toggle", "toggle"]
    asyncio.run(scenario())


def test_retention_is_scoped_to_native_session_and_cleared_on_stop_or_disable():
    async def scenario():
        session = ControllableSession()
        memory = PausedSessions()
        memory.remember(session, memory.epoch)
        replacement = ControllableSession(status=5)
        async with running([replacement], memory) as (provider, snapshots, manager):
            await asyncio.sleep(0.1)
            assert snapshots[-1] == () and not memory.contains(session)
        session.status = 5
        memory.remember(session, memory.epoch)
        async with running([session], memory) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            session.status = 3
            session.emit()
            await wait_for(lambda: snapshots[-1] == ())
            assert not memory.contains(session)
        session.status = 4
        async with running([session], memory) as (provider, snapshots, manager):
            await wait_for(lambda: snapshots[-1])
            session.command_gate = asyncio.Event()
            provider.request_action(snapshots[-1][0].session_id, "pause")
            await wait_for(lambda: session.calls)
            memory.clear()
            session.command_gate.set()
            await wait_for(lambda: snapshots[-1] == ())
            assert not memory.contains(session)
    asyncio.run(scenario())


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0, 3.0])
def test_title_grows_when_space_is_available_and_controls_fit(qapp, scale):
    item = MediaItem("target", "source", "A short title", can_previous=True, can_next=True, can_pause=True, generation=7)
    card = MediaCard(item, scale)
    card.resize(round(500 * scale), card.sizeHint().height())
    card.show()
    qapp.processEvents()
    assert card.title.font().pixelSize() == round(18 * scale)
    assert len(card.title.lines()) == 1
    column = card.title.parentWidget()
    assert column.height() == card.cover.height()
    for button in card.buttons.values():
        assert button.isEnabled() and not button.icon().isNull()
        assert button.y() >= card.title.geometry().bottom()
        assert button.geometry().bottom() < column.height()
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus
    spy = QSignalSpy(card.action_requested)
    card.buttons["next"].click()
    assert spy.count() == 1 and spy.at(0) == ["target", 7, "next"]
    card.close()


def test_paused_card_shows_play_and_pending_commands_disable_buttons(qapp):
    item = MediaItem("1", "source", "Paused", playback_state="paused", can_play=True, can_next=True)
    card = MediaCard(item)
    assert "play" in card.buttons and "pause" not in card.buttons
    spy = QSignalSpy(card.action_requested)
    card.buttons["play"].click()
    assert spy.at(0) == ["1", 0, "play"]
    busy = MediaCard(replace(item, pending_action="play"))
    assert all(not button.isEnabled() for button in busy.buttons.values())
    assert not card.buttons["previous"].isEnabled()


def test_title_is_vertically_centered_in_its_available_area(qapp):
    card = MediaCard(MediaItem("1", "source", "Center"))
    card.resize(400, card.sizeHint().height())
    card.show()
    qapp.processEvents()
    image = card.title.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    background = image.pixelColor(image.width() - 1, image.height() - 1)
    rows = [y for y in range(image.height()) if any(image.pixelColor(x, y) != background for x in range(image.width()))]
    assert rows
    assert abs((rows[0] + rows[-1]) / 2 - image.height() / 2) < card.title.fontMetrics().height() / 2
    card.close()


def test_retained_pause_reuses_native_manager_between_openings(monkeypatch):
    async def scenario():
        memory = PausedSessions()

        class ManagerFactory:
            @staticmethod
            async def request_async():
                return Manager([ControllableSession(status=5)])

        monkeypatch.setitem(sys.modules, "winrt.windows.media.control", SimpleNamespace(GlobalSystemMediaTransportControlsSessionManager=ManagerFactory))
        manager = Manager([ControllableSession(status=5)])
        session = manager.sessions[0]
        memory.cache_manager(manager, memory.epoch)
        memory.remember(session, memory.epoch)
        for generation in (1, 2):
            snapshots = []
            provider = WindowsMediaProvider(snapshots.append, paused_sessions=memory, generation=generation)
            task = asyncio.create_task(provider._run())
            try:
                await wait_for(lambda: snapshots and snapshots[-1])
                assert snapshots[-1][0].playback_state == "paused"
                assert snapshots[-1][0].generation == generation
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            assert not manager.callbacks and not session.media and not session.playback
        memory.clear()
        assert memory.get_manager() is None and not memory.contains(session)
    asyncio.run(scenario())
