from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import MAX_VISIBLE_ENTRIES, MIN_OVERLAY_WIDTH, OverlayWindow


def make_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    model = MixerModel(fake_backend, settings)
    return OverlayWindow(model, settings)


def move_event(global_x: float = 0, global_y: float = 0) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(0, 0),
        QPointF(global_x, global_y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def press_event(global_pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(0, 0),
        global_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def release_event(global_pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(0, 0),
        global_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_resize_handle_drag_resizes_window(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.resize(320, overlay.height())

    handle = overlay._resize_handle_width
    handle._drag_start_pos = 100
    handle._start_width = overlay.width()

    handle.mouseMoveEvent(move_event(global_x=140))

    assert overlay.width() == 360


def test_resize_handle_clamps_to_minimum_width(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.resize(320, overlay.height())

    handle = overlay._resize_handle_width
    handle._drag_start_pos = 100
    handle._start_width = overlay.width()

    handle.mouseMoveEvent(move_event(global_x=100 - overlay.width()))

    assert overlay.width() == MIN_OVERLAY_WIDTH


def test_resize_persists_geometry(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.resize(400, overlay.height())
    overlay._save_geometry()

    assert settings.get_overlay_geometry()["width"] == 400


def test_overlay_restores_persisted_width(qapp, fake_backend, settings):
    settings.set_overlay_geometry(50, 60, 500, 350)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.width() == 500


def test_dragging_title_bar_pauses_and_resumes_refresh(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    assert overlay._refresh_timer.isActive()

    title_bar = overlay._title_bar
    title_bar.mousePressEvent(press_event(QPointF(10, 10)))
    assert not overlay._refresh_timer.isActive()

    title_bar.mouseReleaseEvent(release_event(QPointF(10, 10)))
    assert overlay._refresh_timer.isActive()


def test_dragging_resize_handle_pauses_and_resumes_refresh(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    assert overlay._refresh_timer.isActive()

    handle = overlay._resize_handle_width
    handle.mousePressEvent(press_event(QPointF(10, 10)))
    assert not overlay._refresh_timer.isActive()

    handle.mouseReleaseEvent(release_event(QPointF(10, 10)))
    assert overlay._refresh_timer.isActive()


def test_overlay_has_no_vertical_resize_handle(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    assert not hasattr(overlay, "_resize_handle_height")
    assert overlay.minimumHeight() == overlay.maximumHeight()


def test_window_height_grows_with_entry_count(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    initial_height = overlay.height()
    initial_count = len(overlay._entry_widgets)

    fake_backend.add_session(FakeAudioSession(pid=300, process_name="discord.exe", display_name="Discord", volume=1.0))
    overlay._model.refresh()
    overlay.refresh_view()

    assert len(overlay._entry_widgets) == initial_count + 1
    assert overlay.height() > initial_height


def test_window_height_caps_after_max_visible_entries(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    for i in range(MAX_VISIBLE_ENTRIES + 4):
        fake_backend.add_session(
            FakeAudioSession(pid=1000 + i, process_name=f"app{i}.exe", display_name=f"App {i}", volume=1.0)
        )
    overlay._model.refresh()
    overlay.refresh_view()

    height_at_cap = overlay.height()

    fake_backend.add_session(FakeAudioSession(pid=2000, process_name="extra.exe", display_name="Extra", volume=1.0))
    overlay._model.refresh()
    overlay.refresh_view()

    assert overlay.height() == height_at_cap
