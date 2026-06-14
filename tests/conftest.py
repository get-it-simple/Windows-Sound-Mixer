import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession  # noqa: E402
from sound_mixer.settings.store import SettingsStore  # noqa: E402

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


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
            FakeAudioSession(pid=100, process_name="chrome.exe", display_name="Google Chrome", volume=1.0),
            FakeAudioSession(pid=200, process_name="spotify.exe", display_name="Spotify", volume=1.0),
        ],
        master_volume=0.5,
    )


@pytest.fixture
def settings(tmp_path) -> SettingsStore:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    return store
