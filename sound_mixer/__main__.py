import sys

from PySide6.QtCore import QCoreApplication

from sound_mixer import __version__
from sound_mixer.instance_control import CommandResult, send_command


def main() -> int:
    if "--version" in sys.argv:
        print(__version__)
        return 0

    if "--shutdown-for-update" in sys.argv:
        qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)
        result = send_command("shutdown", timeout_ms=5000)
        qt_app.processEvents()
        return 0 if result in {CommandResult.ACCEPTED, CommandResult.NOT_RUNNING} else 2

    from sound_mixer.logging_setup import configure_logging

    configure_logging()

    from sound_mixer.app import SoundMixerApp

    app = SoundMixerApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
