from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import MIN_OVERLAY_HEIGHT, MIN_OVERLAY_WIDTH, OverlayWindow


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
    overlay.resize(320, 400)

    handle = overlay._resize_handle_width
    handle._drag_start_pos = 100
    handle._start_size = overlay.width()

    handle.mouseMoveEvent(move_event(global_x=140))

    assert overlay.width() == 360


def test_resize_handle_clamps_to_minimum_width(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.resize(320, 400)

    handle = overlay._resize_handle_width
    handle._drag_start_pos = 100
    handle._start_size = overlay.width()

    handle.mouseMoveEvent(move_event(global_x=100 - overlay.width()))

    assert overlay.width() == MIN_OVERLAY_WIDTH


def test_height_resize_handle_drag_resizes_window(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.resize(320, 400)

    handle = overlay._resize_handle_height
    handle._drag_start_pos = 100
    handle._start_size = overlay.height()

    handle.mouseMoveEvent(move_event(global_y=160))

    assert overlay.height() == 460


def test_height_resize_handle_clamps_to_minimum_height(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.resize(320, 400)

    handle = overlay._resize_handle_height
    handle._drag_start_pos = 100
    handle._start_size = overlay.height()

    handle.mouseMoveEvent(move_event(global_y=100 - overlay.height()))

    assert overlay.height() == MIN_OVERLAY_HEIGHT


def test_resize_persists_geometry(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.resize(400, 450)
    overlay._save_geometry()

    assert settings.get_overlay_geometry()["width"] == 400
    assert settings.get_overlay_geometry()["height"] == 450


def test_overlay_restores_persisted_width(qapp, fake_backend, settings):
    settings.set_overlay_geometry(50, 60, 500, 350)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.width() == 500
    assert overlay.height() == 350


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
