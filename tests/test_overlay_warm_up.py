from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import OverlayWindow

from tests.conftest import windows_only


def make_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    model = MixerModel(fake_backend, settings)
    return OverlayWindow(model, settings)


@windows_only
def test_warm_up_shows_overlay_on_construction(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.isVisible()
    assert overlay._warming_up is True


@windows_only
def test_warm_up_hides_overlay_when_not_starting_opened(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay._finish_warm_up()

    assert not overlay.isVisible()
    assert overlay._warming_up is False


@windows_only
def test_start_opened_still_runs_the_warm_up_cycle(qapp, fake_backend, settings):
    settings.set_visible_on_start(True)
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.show_on_start()

    assert overlay._show_after_warm_up is True
    assert overlay.isVisible()


@windows_only
def test_start_opened_reopens_overlay_after_the_warm_up(qapp, fake_backend, settings):
    settings.set_visible_on_start(True)
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.show_on_start()

    overlay._finish_warm_up()

    assert not overlay.isVisible()
    assert overlay._show_after_warm_up is False

    qapp.processEvents()
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    deadline = QDeadlineTimer(1000)
    while not overlay.isVisible() and not deadline.hasExpired():
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)

    assert overlay.isVisible()


def test_show_on_start_shows_immediately_without_warm_up(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay._warming_up = False
    overlay.hide()

    overlay.show_on_start()

    assert overlay.isVisible()
    assert overlay._show_after_warm_up is False
