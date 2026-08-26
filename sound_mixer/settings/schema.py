CURRENT_VERSION = 7

MIN_UI_SCALE = 0.5
MAX_UI_SCALE = 3.0

LAYOUT_HORIZONTAL = "horizontal"
LAYOUT_VERTICAL = "vertical"
LAYOUT_MODES = (LAYOUT_HORIZONTAL, LAYOUT_VERTICAL)

DEFAULT_HOTKEYS = [
    {"action": "toggle_overlay", "combo": "ctrl+alt+num5", "enabled": True},
    {"action": "volume_up", "combo": "", "enabled": False},
    {"action": "volume_down", "combo": "", "enabled": False},
    {"action": "focus_next", "combo": "", "enabled": False},
    {"action": "focus_prev", "combo": "", "enabled": False},
    {"action": "mute_toggle", "combo": "", "enabled": False},
]

DEFAULT_SETTINGS = {
    "version": CURRENT_VERSION,
    "master_volume": 0.8,
    "master_muted": False,
    "app_volumes": {},
    "hotkeys": DEFAULT_HOTKEYS,
    "autostart_enabled": False,
    "overlay": {
        "layout_mode": LAYOUT_HORIZONTAL,
        "visible_on_start": False,
        LAYOUT_HORIZONTAL: {"x": 100, "y": 100, "width": 320, "height": 400},
        LAYOUT_VERTICAL: {"x": 100, "y": 100, "width": 420, "height": 340},
    },
    "tooltip_delay_ms": 500,
    "volume_step": {
        "arrow": 0.05,
        "scroll": 0.02,
    },
    "ui_scale": 1.0,
    "default_app_volume": 1.0,
    "transparency_enabled": True,
    "ignored_apps": [],
    "language": "system",
    "subprocess_management": {
        "interval_seconds": 5,
        "apps": [],
    },
}
