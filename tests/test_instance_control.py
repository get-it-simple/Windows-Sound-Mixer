import subprocess
import sys
import time
import uuid

import pytest

from PySide6.QtNetwork import QLocalServer, QLocalSocket

from sound_mixer import instance_control
from sound_mixer.instance_control import CommandResult, InstanceController, send_command


def wait_for_process(qapp, process, timeout=5.0):
    deadline = time.monotonic() + timeout
    while process.poll() is None and time.monotonic() < deadline:
        qapp.processEvents()
    return process.wait(timeout=0.5)


def test_shutdown_command_is_acknowledged_after_dispatch(qapp, tmp_path):
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    marker = tmp_path / "flushed"
    shutdowns = []

    def dispatch_shutdown():
        marker.write_text("flushed", encoding="utf-8")
        shutdowns.append(True)

    controller = InstanceController(dispatch_shutdown, name=name)
    assert controller.start() is True
    try:
        code = (
            "import sys; "
            "from sound_mixer.instance_control import CommandResult, send_command; "
            "result=send_command('shutdown', 2000, sys.argv[1]); "
            "sys.exit(0 if result is CommandResult.ACCEPTED "
            "and __import__('pathlib').Path(sys.argv[2]).is_file() else 1)"
        )
        process = subprocess.Popen([sys.executable, "-c", code, name, str(marker)])
        assert wait_for_process(qapp, process) == 0
        qapp.processEvents()
        assert shutdowns == [True]
    finally:
        controller.close()


def test_second_controller_cannot_claim_active_server(qapp):
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    first = InstanceController(lambda: None, name=name)
    second = InstanceController(lambda: None, name=name)
    assert first.start() is True
    try:
        assert second.start() is False
    finally:
        second.close()
        first.close()


@pytest.mark.parametrize(
    ("command", "expected", "shutdown_count"),
    [("shutdown", CommandResult.ACCEPTED, 1), ("unknown", CommandResult.FAILED, 0)],
)
def test_command_handles_response_buffered_before_read_wait(qapp, monkeypatch, command, expected, shutdown_count):
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    shutdowns = []
    controller = InstanceController(lambda: shutdowns.append(True), name=name)
    assert controller.start() is True

    class BufferedResponseSocket(QLocalSocket):
        def write(self, data):
            written = super().write(data)
            self.flush()
            deadline = time.monotonic() + 5
            while self.state() != QLocalSocket.LocalSocketState.UnconnectedState and time.monotonic() < deadline:
                qapp.processEvents()
            assert self.state() == QLocalSocket.LocalSocketState.UnconnectedState
            assert self.canReadLine()
            return written

    monkeypatch.setattr(instance_control, "QLocalSocket", BufferedResponseSocket)
    try:
        assert send_command(command, 1000, name) is expected
        assert shutdowns == [True] * shutdown_count
    finally:
        controller.close()


def test_command_reports_when_instance_is_not_running():
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    assert send_command("shutdown", 50, name) is CommandResult.NOT_RUNNING


def test_command_retries_while_instance_is_starting(qapp, tmp_path):
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    started = tmp_path / "command-started"
    shutdowns = []
    code = (
        "import pathlib, sys; "
        "from sound_mixer.instance_control import CommandResult, send_command; "
        "pathlib.Path(sys.argv[2]).write_text('started'); "
        "result=send_command('shutdown', 2000, sys.argv[1]); "
        "sys.exit(0 if result is CommandResult.ACCEPTED else 1)"
    )
    process = subprocess.Popen([sys.executable, "-c", code, name, str(started)])
    deadline = time.monotonic() + 2
    while not started.is_file() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert started.is_file()
    time.sleep(0.1)

    controller = InstanceController(lambda: shutdowns.append(True), name=name)
    assert controller.start() is True
    try:
        assert wait_for_process(qapp, process) == 0
        qapp.processEvents()
        assert shutdowns == [True]
    finally:
        controller.close()


def test_command_times_out_when_instance_does_not_acknowledge():
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    server = QLocalServer()
    assert server.listen(name)
    try:
        assert send_command("shutdown", 50, name) is CommandResult.FAILED
    finally:
        server.close()
        QLocalServer.removeServer(name)


def test_update_shutdown_waits_for_slow_application_start(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("USERDOMAIN", f"SoundMixer.Test.{uuid.uuid4()}")
    started = tmp_path / "shutdown-started"
    code = (
        "import pathlib, sys; "
        "from sound_mixer.__main__ import main; "
        "pathlib.Path(sys.argv[1]).write_text('started'); "
        "sys.argv = ['sound_mixer', '--shutdown-for-update']; "
        "sys.exit(main())"
    )
    process = subprocess.Popen([sys.executable, "-c", code, str(started)])
    shutdowns = []
    controller = InstanceController(lambda: shutdowns.append(True))
    try:
        deadline = time.monotonic() + 10
        while not started.is_file() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started.is_file()
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=6)

        assert controller.start() is True
        assert wait_for_process(qapp, process) == 0
        assert shutdowns == [True]
    finally:
        controller.close()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
