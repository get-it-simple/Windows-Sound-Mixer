from dataclasses import dataclass

VALID_MODIFIERS = {"ctrl", "alt", "shift", "win"}

_LETTERS = {chr(c) for c in range(ord("a"), ord("z") + 1)}
_DIGITS = {str(d) for d in range(10)}
_NUMPAD_DIGITS = {f"num{d}" for d in range(10)}
_FUNCTION_KEYS = {f"f{n}" for n in range(1, 25)}
_ARROWS = {"up", "down", "left", "right"}
_OTHER_KEYS = {
    "space",
    "enter",
    "esc",
    "tab",
    "backspace",
    "delete",
    "insert",
    "home",
    "end",
    "page up",
    "page down",
    "caps lock",
    "print screen",
    "scroll lock",
    "pause",
    "num lock",
}

VALID_KEYS = VALID_MODIFIERS | _LETTERS | _DIGITS | _NUMPAD_DIGITS | _FUNCTION_KEYS | _ARROWS | _OTHER_KEYS


@dataclass
class HotkeyBinding:
    action: str
    combo: str
    enabled: bool

    @classmethod
    def from_dict(cls, data: dict) -> "HotkeyBinding":
        return cls(action=data["action"], combo=data["combo"], enabled=data["enabled"])

    def to_dict(self) -> dict:
        return {"action": self.action, "combo": self.combo, "enabled": self.enabled}


def normalize_combo(combo: str) -> str:
    if not combo:
        return ""
    parts = [part.strip().lower() for part in combo.split("+")]
    return "+".join(parts)


def parse_combo(combo: str) -> list[str]:
    normalized = normalize_combo(combo)
    if not normalized:
        return []

    tokens = normalized.split("+")
    for token in tokens:
        if token not in VALID_KEYS:
            raise ValueError(f"Unknown key: {token}")
    return tokens


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


def validate_bindings(bindings: list[dict]) -> None:
    from sound_mixer.i18n import t

    used = set()
    for binding in bindings:
        if not binding["enabled"] or not binding["combo"]:
            continue
        key = combo_to_hotkey(binding["combo"])
        if key in used:
            raise ValueError(t("hotkey_conflict").format(combo=binding["combo"]))
        used.add(key)

_MODIFIER_FLAGS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

_VK_CODES: dict[str, int] = {}
_VK_CODES.update({str(d): 0x30 + d for d in range(10)})
_VK_CODES.update({chr(ord("a") + i): 0x41 + i for i in range(26)})
_VK_CODES.update({f"num{d}": 0x60 + d for d in range(10)})
_VK_CODES.update({f"f{n}": 0x70 + (n - 1) for n in range(1, 25)})
_VK_CODES.update(
    {
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
        "space": 0x20,
        "enter": 0x0D,
        "esc": 0x1B,
        "tab": 0x09,
        "backspace": 0x08,
        "delete": 0x2E,
        "insert": 0x2D,
        "home": 0x24,
        "end": 0x23,
        "page up": 0x21,
        "page down": 0x22,
        "caps lock": 0x14,
        "print screen": 0x2C,
        "scroll lock": 0x91,
        "pause": 0x13,
        "num lock": 0x90,
    }
)


def combo_to_hotkey(combo: str) -> tuple[int, int]:
    """Convert a combo string to (modifiers, virtual_key_code) for RegisterHotKey."""
    tokens = parse_combo(combo)

    modifiers = 0
    key_token = None
    for token in tokens:
        if token in _MODIFIER_FLAGS:
            modifiers |= _MODIFIER_FLAGS[token]
        elif key_token is None:
            key_token = token
        else:
            raise ValueError(f"Combo has more than one non-modifier key: {combo}")

    if key_token is None:
        raise ValueError(f"Combo has no non-modifier key: {combo}")

    return modifiers, _VK_CODES[key_token]
