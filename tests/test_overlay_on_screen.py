from PySide6.QtGui import QGuiApplication

from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import MIN_VISIBLE_PX, OverlayWindow


def make_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    model = MixerModel(fake_backend, settings)
    return OverlayWindow(model, settings)


def available_geometry():
    return QGuiApplication.primaryScreen().availableGeometry()


def test_offscreen_geometry_is_recentered(qapp, fake_backend, settings):
    available = available_geometry()
    settings.set_overlay_geometry(available.right() + 4000, available.bottom() + 4000, 320, 400)

    overlay = make_overlay(qapp, fake_backend, settings)

    overlap = available.intersected(overlay.frameGeometry())
    assert overlap.width() >= min(MIN_VISIBLE_PX, overlay.width())
    assert overlap.height() >= min(MIN_VISIBLE_PX, overlay.height())


def test_negative_offscreen_geometry_is_recentered(qapp, fake_backend, settings):
    settings.set_overlay_geometry(-5000, -5000, 320, 400)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert available_geometry().intersects(overlay.frameGeometry())


def test_barely_visible_sliver_is_recentered(qapp, fake_backend, settings):
    available = available_geometry()
    settings.set_overlay_geometry(available.right() - 4, available.top() + 10, 320, 400)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.x() < available.right() - 4


def test_on_screen_geometry_is_left_alone(qapp, fake_backend, settings):
    available = available_geometry()
    settings.set_overlay_geometry(available.left() + 40, available.top() + 50, 320, 400)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.x() == available.left() + 40
    assert overlay.y() == available.top() + 50


def test_oversized_width_is_clamped_to_available_area(qapp, fake_backend, settings):
    available = available_geometry()
    settings.set_overlay_geometry(available.left(), available.top(), available.width() + 500, 400)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.width() <= available.width()


def test_oversized_height_is_clamped_in_vertical_mode(qapp, fake_backend, settings):
    available = available_geometry()
    settings.set_layout_mode("vertical")
    settings.set_overlay_geometry(available.left(), available.top(), 320, available.height() + 500)

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.height() <= available.height()


def test_showing_after_screen_change_recenters(qapp, fake_backend, settings):
    available = available_geometry()
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.hide()

    overlay.move(available.right() + 3000, available.bottom() + 3000)
    overlay.show()

    assert available.intersects(overlay.frameGeometry())
    overlay.close()
