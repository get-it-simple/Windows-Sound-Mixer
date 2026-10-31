import asyncio
import logging
import sys
import threading

from PySide6.QtCore import QObject, Signal

from sound_mixer.media.identity import application_identities
from sound_mixer.media.model import MediaItem, MediaOwner, PausedSessions, attach_owners
from sound_mixer.media.provider import WindowsMediaProvider

logger = logging.getLogger(__name__)


class _MediaWorker(threading.Thread):
    def __init__(self, generation, deliver, owners, provider_factory, paused_sessions):
        super().__init__(name="Playing media", daemon=True)
        self.generation = generation
        self.deliver = deliver
        self.owners = owners
        self.provider_factory = provider_factory
        self.stopping = threading.Event()
        self.loop = None
        self.task = None
        self.items: tuple[MediaItem, ...] = ()
        self.identities = None
        self.paused_sessions = paused_sessions
        self.provider = None

    def run(self):
        try:
            asyncio.run(self._run())
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("Playing media service unavailable", exc_info=True)
            if not self.stopping.is_set():
                self.deliver(self.generation, ())

    async def _run(self):
        self.loop = asyncio.get_running_loop()
        self.task = asyncio.current_task()
        if not self.stopping.is_set():
            self.provider = self.provider_factory(self.publish, paused_sessions=self.paused_sessions, generation=self.generation)
            await self.provider.run()

    def request_action(self, session_id, action):
        if self.loop is not None and self.provider is not None and not self.stopping.is_set():
            try:
                self.loop.call_soon_threadsafe(self.provider.request_action, session_id, action)
            except RuntimeError:
                pass

    def publish(self, items):
        if self.stopping.is_set():
            return
        if {item.source for item in items} != {item.source for item in self.items}:
            self.identities = None
        self.items = items
        if self.identities is None:
            self.identities = application_identities(self.owners)
        self.deliver(self.generation, attach_owners(items, self.owners, self.identities))

    def set_owners(self, owners):
        self.owners = owners
        def update():
            self.identities = None
            self.publish(self.items)
        if self.loop is not None and not self.stopping.is_set():
            try:
                self.loop.call_soon_threadsafe(update)
            except RuntimeError:
                pass

    def stop(self):
        self.stopping.set()
        if self.loop is not None and self.task is not None:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass


class MediaController(QObject):
    changed = Signal(object)
    _delivered = Signal(int, object)

    def __init__(self, parent=None, provider_factory=WindowsMediaProvider):
        super().__init__(parent)
        self._provider_factory = provider_factory
        self._enabled = False
        self._visible = False
        self._generation = 0
        self._worker = None
        self._retired = []
        self._owners = ()
        self._paused = PausedSessions()
        self.items = ()
        self._delivered.connect(self._accept)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self._paused.clear()
        self._sync()

    def set_visible(self, visible):
        self._visible = bool(visible)
        self._sync()

    def set_entries(self, entries):
        owners = tuple(MediaOwner(entry.key, entry.pids, entry.icon_path) for entry in entries if not getattr(entry, "is_master", False))
        if owners != self._owners:
            self._owners = owners
            if self._worker is not None:
                self._worker.set_owners(owners)

    def _sync(self):
        active = self._enabled and self._visible and sys.platform == "win32"
        if active and self._worker is None:
            self._retired = [worker for worker in self._retired if worker.is_alive()]
            self._generation += 1
            self._worker = _MediaWorker(self._generation, self._delivered.emit, self._owners, self._provider_factory, self._paused)
            self._worker.start()
        elif not active and self._worker is not None:
            self.stop()

    def _accept(self, generation, items):
        if generation == self._generation and self._worker is not None and items != self.items:
            self.items = items
            self.changed.emit(items)

    def request_action(self, session_id, generation, action):
        if self._worker is not None and generation == self._generation:
            self._worker.request_action(session_id, action)

    def stop(self):
        self._generation += 1
        if self._worker is not None:
            self._worker.stop()
            self._retired.append(self._worker)
            self._worker = None
        if self.items:
            self.items = ()
            self.changed.emit(())

    def shutdown(self):
        self._paused.clear()
        self.stop()
        for worker in self._retired:
            worker.join(timeout=1)
