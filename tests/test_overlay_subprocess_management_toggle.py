import sys

from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.window import OverlayWindow


def test_toggle_hidden_when_no_subprocess_manager(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)

    assert overlay._subprocess_management_toggle.isVisible() is False


def test_toggle_hidden_when_no_enabled_apps(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)

    assert overlay._subprocess_management_toggle.isVisible() is False


def test_toggle_visible_when_enabled_app_configured(qapp, fake_backend, settings):
    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    model = MixerModel(fake_backend, settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)

    assert overlay._subprocess_management_toggle.isVisible() is True


def test_toggle_unchecked_by_default_even_when_visible(qapp, fake_backend, settings):
    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    model = MixerModel(fake_backend, settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)

    assert overlay._subprocess_management_toggle.isChecked() is False
    assert manager.is_active() is False


def test_toggling_checkbox_activates_subprocess_manager(qapp, fake_backend, settings):
    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    model = MixerModel(fake_backend, settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)

    overlay._subprocess_management_toggle.setChecked(True)

    assert manager.is_active() is True
    assert manager._timer.isActive() is True

    overlay._subprocess_management_toggle.setChecked(False)

    assert manager.is_active() is False
    assert manager._timer.isActive() is False


def test_sync_updates_visibility_after_settings_change(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)

    assert overlay._subprocess_management_toggle.isVisible() is False

    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    overlay.sync_subprocess_management_toggle()

    assert overlay._subprocess_management_toggle.isVisible() is True


def test_toggle_tooltip_is_set(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)

    assert overlay._subprocess_management_toggle.toolTip()
