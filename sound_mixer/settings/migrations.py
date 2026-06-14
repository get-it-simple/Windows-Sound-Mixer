import logging

from sound_mixer.settings.schema import CURRENT_VERSION

logger = logging.getLogger(__name__)


def _migrate_0_to_1(data: dict) -> dict:
    data = dict(data)
    if "volumes" in data and "app_volumes" not in data:
        data["app_volumes"] = data.pop("volumes")
    data.setdefault("master_muted", False)
    data.setdefault("volume_step", {"arrow": 0.05, "scroll": 0.02})
    data["version"] = 1
    return data


MIGRATIONS = {
    0: _migrate_0_to_1,
}


def migrate(data: dict) -> dict:
    version = data.get("version", 0)

    if version > CURRENT_VERSION:
        logger.warning(
            "Settings file version %s is newer than supported version %s; loading without changes",
            version,
            CURRENT_VERSION,
        )
        return data

    while version < CURRENT_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            break
        data = migration(data)
        version = data.get("version", version + 1)

    return data
