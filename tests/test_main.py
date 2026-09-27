import sys
from unittest.mock import Mock

from sound_mixer import __main__
from sound_mixer import app as app_module
from sound_mixer import logging_setup


def test_normal_startup_enables_efficiency_mode(monkeypatch):
    calls = []

    class FakeApp:
        def run(self):
            calls.append("run")
            return 7

    monkeypatch.setattr(sys, "argv", ["sound-mixer"])
    monkeypatch.setattr(logging_setup, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(__main__, "enable_efficiency_mode", lambda: calls.append("efficiency"))
    monkeypatch.setattr(app_module, "SoundMixerApp", FakeApp)

    assert __main__.main() == 7
    assert calls == ["logging", "efficiency", "run"]


def test_version_command_does_not_enable_efficiency_mode(monkeypatch, capsys):
    enable = Mock()
    monkeypatch.setattr(sys, "argv", ["sound-mixer", "--version"])
    monkeypatch.setattr(__main__, "enable_efficiency_mode", enable)

    assert __main__.main() == 0

    enable.assert_not_called()
    assert capsys.readouterr().out.strip()


def test_shutdown_command_does_not_enable_efficiency_mode(monkeypatch):
    enable = Mock()
    qt_app = Mock()
    core_application = Mock()
    core_application.instance.return_value = qt_app
    monkeypatch.setattr(sys, "argv", ["sound-mixer", "--shutdown-for-update"])
    monkeypatch.setattr(__main__, "enable_efficiency_mode", enable)
    monkeypatch.setattr(__main__, "QCoreApplication", core_application)
    monkeypatch.setattr(__main__, "send_command", lambda *args, **kwargs: __main__.CommandResult.NOT_RUNNING)

    assert __main__.main() == 0

    enable.assert_not_called()
    qt_app.processEvents.assert_called_once_with()
