import os


def normalize_app_key(value: str) -> str:
    return value.replace("\\", "/").lower()


def legacy_app_key(key: str) -> str:
    return os.path.basename(normalize_app_key(key))
