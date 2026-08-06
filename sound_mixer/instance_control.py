import getpass
import hashlib
import os
import sys
import tempfile
from enum import Enum
from typing import Callable, Optional

from PySide6.QtCore import QLockFile, QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

APP_SERVER_PREFIX = "GetItSimple.SoundMixer"


class CommandResult(Enum):
    ACCEPTED = "accepted"
    NOT_RUNNING = "not_running"
    FAILED = "failed"


def _session_id() -> int:
    if sys.platform != "win32":
        return 0

    try:
        import ctypes

        session_id = ctypes.c_ulong()
        process_id = ctypes.windll.kernel32.GetCurrentProcessId()
        if ctypes.windll.kernel32.ProcessIdToSessionId(process_id, ctypes.byref(session_id)):
            return int(session_id.value)
    except (AttributeError, OSError):
        pass
    return 0


def server_name() -> str:
    identity = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".lower()
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{APP_SERVER_PREFIX}.{digest}.{_session_id()}"


def send_command(command: str, timeout_ms: int = 3000, name: Optional[str] = None) -> CommandResult:
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(timeout_ms):
        return CommandResult.NOT_RUNNING

    socket.write((command + "\n").encode("utf-8"))
    if socket.bytesToWrite() and not socket.waitForBytesWritten(timeout_ms):
        socket.abort()
        return CommandResult.FAILED
    if not socket.waitForReadyRead(timeout_ms):
        socket.abort()
        return CommandResult.FAILED

    response = bytes(socket.readAll()).decode("utf-8", errors="replace").strip()
    socket.disconnectFromServer()
    return CommandResult.ACCEPTED if response == "ok" else CommandResult.FAILED


class InstanceController(QObject):
    def __init__(self, on_shutdown: Callable[[], None], parent: Optional[QObject] = None, name: Optional[str] = None):
        super().__init__(parent)
        self._on_shutdown = on_shutdown
        self._name = name or server_name()
        self._server = QLocalServer(self)
        lock_name = hashlib.sha256(self._name.encode("utf-8")).hexdigest()
        self._lock = QLockFile(os.path.join(tempfile.gettempdir(), f"{lock_name}.lock"))
        self._lock.setStaleLockTime(0)
        self._clients: set[QLocalSocket] = set()
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)

    def start(self) -> bool:
        if not self._lock.tryLock(0):
            return False
        if self._server.listen(self._name):
            return True

        probe = QLocalSocket()
        probe.connectToServer(self._name)
        if probe.waitForConnected(250):
            probe.abort()
            self._lock.unlock()
            return False

        QLocalServer.removeServer(self._name)
        if self._server.listen(self._name):
            return True
        self._lock.unlock()
        return False

    def close(self) -> None:
        self._server.close()
        QLocalServer.removeServer(self._name)
        if self._lock.isLocked():
            self._lock.unlock()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            self._clients.add(socket)
            socket.readyRead.connect(lambda current=socket: self._read_command(current))
            socket.disconnected.connect(lambda current=socket: self._discard_client(current))
            if socket.bytesAvailable():
                self._read_command(socket)

    def _read_command(self, socket: QLocalSocket) -> None:
        command = bytes(socket.readAll()).decode("utf-8", errors="replace").strip()
        if command != "shutdown":
            socket.write(b"error\n")
            socket.flush()
            socket.disconnectFromServer()
            return

        try:
            self._on_shutdown()
        except Exception:
            socket.write(b"error\n")
            socket.flush()
            socket.disconnectFromServer()
            return
        socket.write(b"ok\n")
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()

    def _discard_client(self, socket: QLocalSocket) -> None:
        self._clients.discard(socket)
