import subprocess
import sys
import time
import uuid

from PySide6.QtNetwork import QLocalServer

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


def test_command_reports_when_instance_is_not_running():
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    assert send_command("shutdown", 50, name) is CommandResult.NOT_RUNNING


def test_command_times_out_when_instance_does_not_acknowledge():
    name = f"SoundMixer.Test.{uuid.uuid4()}"
    server = QLocalServer()
    assert server.listen(name)
    try:
        assert send_command("shutdown", 50, name) is CommandResult.FAILED
    finally:
        server.close()
        QLocalServer.removeServer(name)
