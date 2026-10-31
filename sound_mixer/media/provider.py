import asyncio
from dataclasses import dataclass, replace
from hashlib import sha256
import logging

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from sound_mixer.media.model import MediaItem, PausedSessions

logger = logging.getLogger(__name__)
MAX_ARTWORK_BYTES = 8 * 1024 * 1024


def decode_artwork(data: bytes) -> QImage:
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 16_777_216:
        return QImage()
    reader.setScaledSize(size.scaled(QSize(192, 192), Qt.AspectRatioMode.KeepAspectRatio))
    return reader.read()


async def read_artwork(thumbnail):
    if thumbnail is None:
        return "", QImage()
    from winrt.windows.storage.streams import DataReader

    stream = await thumbnail.open_read_async()
    try:
        if stream.size > MAX_ARTWORK_BYTES:
            return "", QImage()
        reader = DataReader(stream)
        try:
            loaded = await reader.load_async(stream.size)
            data = bytearray(loaded)
            reader.read_bytes(data)
            return sha256(data).hexdigest(), decode_artwork(bytes(data))
        finally:
            reader.detach_stream()
            reader.close()
    finally:
        stream.close()


@dataclass
class _Session:
    native: object
    tokens: tuple
    item: MediaItem | None = None
    task: asyncio.Task | None = None
    dirty: bool = True
    metadata_dirty: bool = True
    command_task: asyncio.Task | None = None
    pending_action: str = ""
    awaiting_pause: bool = False


class WindowsMediaProvider:
    def __init__(self, publish, manager_factory=None, *, paused_sessions=None, generation=0):
        self._publish = publish
        self._manager_factory = manager_factory
        self._sessions: dict[str, _Session] = {}
        self._next_id = 0
        self._handle = None
        self._closed = False
        self._paused = paused_sessions if paused_sessions is not None else PausedSessions()
        self._pause_epoch = self._paused.epoch
        self._generation = generation

    async def run(self):
        if self._manager_factory is not None:
            await self._run()
            return
        from winrt.runtime import ApartmentType, init_apartment, uninit_apartment
        init_apartment(ApartmentType.MULTI_THREADED)
        try:
            await self._run()
        finally:
            uninit_apartment()

    async def _run(self):
        if self._manager_factory is None:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            manager = self._paused.get_manager()
            if manager is None:
                manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
                self._paused.cache_manager(manager, self._pause_epoch)
        else:
            manager = await self._manager_factory()
        self._loop = asyncio.get_running_loop()
        token = manager.add_sessions_changed(lambda sender, args: self._schedule(self._sync_sessions, manager))
        try:
            self._sync_sessions(manager)
            await asyncio.Future()
        finally:
            self._closed = True
            manager.remove_sessions_changed(token)
            if self._handle is not None:
                self._handle.cancel()
            tasks = [task for state in self._sessions.values() for task in (state.task, state.command_task) if task is not None]
            for state in self._sessions.values():
                self._unsubscribe(state)
            self._sessions.clear()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _schedule(self, callback, *args):
        if not self._closed:
            try:
                self._loop.call_soon_threadsafe(callback, *args)
            except RuntimeError:
                pass

    def _sync_sessions(self, manager):
        if self._closed:
            return
        try:
            sessions = list(manager.get_sessions())
        except Exception:
            logger.warning("Could not enumerate media sessions", exc_info=True)
            return
        self._paused.retain(sessions)
        for key, state in list(self._sessions.items()):
            if not any(state.native == native for native in sessions):
                self._unsubscribe(state)
                del self._sessions[key]
        for native in sessions:
            if any(state.native == native for state in self._sessions.values()):
                continue
            self._next_id += 1
            key = str(self._next_id)
            tokens = []
            try:
                tokens.append(native.add_media_properties_changed(lambda sender, args, k=key: self._schedule(self._mark_dirty, k, True)))
                tokens.append(native.add_playback_info_changed(lambda sender, args, k=key: self._schedule(self._mark_dirty, k, False)))
                self._sessions[key] = _Session(native, tuple(tokens))
            except Exception:
                if tokens:
                    native.remove_media_properties_changed(tokens[0])
                logger.warning("Could not subscribe to a media session", exc_info=True)
        self._emit()
        self._queue_flush()

    def _unsubscribe(self, state):
        if state.task is not None:
            state.task.cancel()
        if state.command_task is not None:
            state.command_task.cancel()
        for remove, token in zip((state.native.remove_media_properties_changed, state.native.remove_playback_info_changed), state.tokens):
            try:
                remove(token)
            except Exception:
                logger.debug("Media subscription already unavailable", exc_info=True)

    def _mark_dirty(self, key, metadata):
        if self._closed or key not in self._sessions:
            return
        state = self._sessions[key]
        state.dirty = True
        state.metadata_dirty |= metadata
        self._queue_flush()

    def _queue_flush(self):
        if self._handle is None and not self._closed:
            self._handle = self._loop.call_later(0.05, self._flush)

    def _flush(self):
        self._handle = None
        for key, state in self._sessions.items():
            if state.dirty and state.task is None:
                state.dirty = False
                metadata = state.metadata_dirty
                state.metadata_dirty = False
                state.task = self._loop.create_task(self._refresh(key, state, metadata))

    async def _refresh(self, key, state, metadata):
        try:
            async with asyncio.timeout(5):
                info = state.native.get_playback_info()
                status = int(info.playback_status)
                if status == 5:
                    state.awaiting_pause = False
                elif status in (0, 3) or (status == 4 and not state.awaiting_pause):
                    self._paused.forget(state.native)
                visible = status == 4 or (status == 5 and (self._paused.contains(state.native) or state.pending_action == "pause"))
                if not visible:
                    state.item = None
                elif metadata or state.item is None:
                    properties = await state.native.try_get_media_properties_async()
                    try:
                        artwork_key, image = await read_artwork(properties.thumbnail)
                    except Exception:
                        artwork_key, image = "", QImage()
                        logger.debug("Media artwork unavailable", exc_info=True)
                    if not state.dirty:
                        state.item = MediaItem(key, state.native.source_app_user_model_id, properties.title or "", artwork_key, image)
                if state.item is not None:
                    controls = getattr(info, "controls", None)
                    toggle = bool(getattr(controls, "is_play_pause_toggle_enabled", False))
                    state.item = replace(state.item, playback_state="paused" if status == 5 else "playing",
                                         can_previous=bool(getattr(controls, "is_previous_enabled", False)),
                                         can_next=bool(getattr(controls, "is_next_enabled", False)),
                                         can_play=bool(getattr(controls, "is_play_enabled", False)) or toggle,
                                         can_pause=bool(getattr(controls, "is_pause_enabled", False)) or toggle,
                                         generation=self._generation)
                if not self._closed and key in self._sessions and not state.dirty:
                    self._emit()
        except asyncio.CancelledError:
            raise
        except Exception:
            state.item = None
            if not self._closed and key in self._sessions:
                self._emit()
            logger.debug("Media session unavailable", exc_info=True)
        finally:
            state.task = None
            if state.dirty and not self._closed:
                state.metadata_dirty |= metadata
                self._queue_flush()

    def request_action(self, session_id, action):
        state = self._sessions.get(session_id)
        if self._closed or state is None or state.item is None or state.command_task is not None:
            return
        if action not in {"previous", "next", "play", "pause"} or not getattr(state.item, f"can_{action}", False):
            return
        state.pending_action = action
        state.awaiting_pause = action == "pause"
        state.command_task = self._loop.create_task(self._perform_action(session_id, state, action))
        self._emit()

    async def _perform_action(self, key, state, action):
        succeeded = False
        try:
            async with asyncio.timeout(5):
                info = state.native.get_playback_info()
                status = int(info.playback_status)
                controls = info.controls
                if action in {"play", "pause"}:
                    desired = 4 if action == "play" else 5
                    if status == desired:
                        return
                    if getattr(controls, f"is_{action}_enabled", False):
                        method = getattr(state.native, f"try_{action}_async")
                    elif controls.is_play_pause_toggle_enabled:
                        method = state.native.try_toggle_play_pause_async
                    else:
                        return
                else:
                    if not getattr(controls, f"is_{action}_enabled", False):
                        return
                    method = getattr(state.native, f"try_skip_{action}_async")
                succeeded = bool(await method())
                if succeeded and action == "pause" and not self._closed and key in self._sessions:
                    self._paused.remember(state.native, self._pause_epoch)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Media command failed", exc_info=True)
        finally:
            if action == "pause" and not succeeded:
                state.awaiting_pause = False
                self._paused.forget(state.native)
            state.pending_action = ""
            state.command_task = None
            if not self._closed and key in self._sessions:
                self._emit()
                self._mark_dirty(key, False)

    def _emit(self):
        self._publish(tuple(replace(state.item, pending_action=state.pending_action)
                            for state in self._sessions.values() if state.item is not None))
