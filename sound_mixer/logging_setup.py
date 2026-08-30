import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_NAME = "sound-mixer.log"
MAX_LOG_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 2


def configure_logging() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None

    log_path = Path(local_app_data) / "GetItSimple" / "SoundMixer" / "logs" / LOG_NAME
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        root_logger = logging.getLogger()
        if not any(
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename) == log_path
            for handler in root_logger.handlers
        ):
            handler = RotatingFileHandler(
                log_path,
                maxBytes=MAX_LOG_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            root_logger.addHandler(handler)
            root_logger.setLevel(logging.INFO)
    except OSError:
        return None
    return log_path
