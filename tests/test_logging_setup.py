import logging
from logging.handlers import RotatingFileHandler

from sound_mixer.logging_setup import LOG_BACKUP_COUNT, MAX_LOG_BYTES, configure_logging


def test_configure_logging_uses_rotating_local_app_data_log(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)

    try:
        path = configure_logging()
        handler = next(
            item
            for item in root_logger.handlers
            if isinstance(item, RotatingFileHandler) and item.baseFilename == str(path)
        )

        assert path == tmp_path / "GetItSimple" / "SoundMixer" / "logs" / "sound-mixer.log"
        assert handler.maxBytes == MAX_LOG_BYTES
        assert handler.backupCount == LOG_BACKUP_COUNT
    finally:
        for handler in root_logger.handlers:
            if handler not in original_handlers:
                handler.close()
        root_logger.handlers[:] = original_handlers
