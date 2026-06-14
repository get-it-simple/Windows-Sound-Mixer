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


def to_keyboard_combo(combo: str) -> str:
    tokens = parse_combo(combo)

    keyboard_tokens = []
    for token in tokens:
        if token in _NUMPAD_DIGITS:
            keyboard_tokens.append(f"num {token[3:]}")
        elif token == "win":
            keyboard_tokens.append("windows")
        else:
            keyboard_tokens.append(token)
    return "+".join(keyboard_tokens)
