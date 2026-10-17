import ctypes
import logging
from types import SimpleNamespace
from unittest.mock import Mock

from sound_mixer import power_efficiency


def make_kernel32(*, priority_result=True, eco_qos_result=True, last_error=0):
    return SimpleNamespace(
        GetCurrentProcess=Mock(return_value=1234),
        SetPriorityClass=Mock(return_value=priority_result),
        SetProcessInformation=Mock(return_value=eco_qos_result),
        GetLastError=Mock(return_value=last_error),
    )


def test_enable_efficiency_mode_sets_low_priority_and_eco_qos(monkeypatch):
    kernel32 = make_kernel32()
    monkeypatch.setattr(power_efficiency.sys, "platform", "win32")
    monkeypatch.setattr(power_efficiency.ctypes, "windll", SimpleNamespace(kernel32=kernel32))

    assert power_efficiency.enable_efficiency_mode()

    kernel32.SetPriorityClass.assert_called_once_with(1234, power_efficiency.IDLE_PRIORITY_CLASS)
    args = kernel32.SetProcessInformation.call_args.args
    assert args[0] == 1234
    assert args[1] == power_efficiency.PROCESS_POWER_THROTTLING
    state = ctypes.cast(args[2], ctypes.POINTER(power_efficiency.ProcessPowerThrottlingState)).contents
    assert state.Version == power_efficiency.PROCESS_POWER_THROTTLING_CURRENT_VERSION
    assert state.ControlMask == power_efficiency.PROCESS_POWER_THROTTLING_EXECUTION_SPEED
    assert state.StateMask == power_efficiency.PROCESS_POWER_THROTTLING_EXECUTION_SPEED
    assert args[3] == ctypes.sizeof(power_efficiency.ProcessPowerThrottlingState)


def test_enable_efficiency_mode_reports_each_failed_setting(monkeypatch, caplog):
    kernel32 = make_kernel32(priority_result=False, eco_qos_result=False, last_error=5)
    monkeypatch.setattr(power_efficiency.sys, "platform", "win32")
    monkeypatch.setattr(power_efficiency.ctypes, "windll", SimpleNamespace(kernel32=kernel32))

    with caplog.at_level(logging.WARNING):
        assert not power_efficiency.enable_efficiency_mode()

    assert "Unable to enable low process priority; Windows error 5" in caplog.text
    assert "Unable to enable EcoQoS; Windows error 5" in caplog.text
    assert kernel32.GetLastError.call_count == 2


def test_enable_efficiency_mode_continues_to_eco_qos_after_priority_api_error(monkeypatch, caplog):
    kernel32 = make_kernel32()
    del kernel32.SetPriorityClass
    monkeypatch.setattr(power_efficiency.sys, "platform", "win32")
    monkeypatch.setattr(power_efficiency.ctypes, "windll", SimpleNamespace(kernel32=kernel32))

    with caplog.at_level(logging.WARNING):
        assert not power_efficiency.enable_efficiency_mode()

    assert "Unable to enable low process priority" in caplog.text
    kernel32.SetProcessInformation.assert_called_once()


def test_enable_efficiency_mode_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(power_efficiency.sys, "platform", "linux")
    windll = Mock()
    monkeypatch.setattr(power_efficiency.ctypes, "windll", windll)

    assert not power_efficiency.enable_efficiency_mode()

    windll.assert_not_called()
