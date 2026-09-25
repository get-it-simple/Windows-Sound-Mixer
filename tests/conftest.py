import gc
import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QEvent

from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession  # noqa: E402
from sound_mixer.settings.store import SettingsStore  # noqa: E402

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


@pytest.fixture(autouse=True)
def collect_gui_objects(request):
    yield
    if "qapp" in request.fixturenames:
        app = QApplication.instance()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def process_factory():
    processes = []

    def create():
        process = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.stdin.read()"],
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(process)
        return process

    yield create
    for process in processes:
        process.stdin.close()
        process.wait(timeout=10)


@pytest.fixture
def child_process(process_factory):
    return process_factory()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def fake_backend() -> FakeAudioBackend:
    return FakeAudioBackend(
        sessions=[
            FakeAudioSession(pid=100, process_name="aurora.exe", display_name="Aurora Browser", volume=1.0),
            FakeAudioSession(pid=200, process_name="lumen.exe", display_name="Lumen", volume=1.0),
        ],
        master_volume=0.5,
    )


@pytest.fixture
def settings(tmp_path) -> SettingsStore:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    return store
