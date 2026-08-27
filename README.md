# Windows Sound Mixer

A per-application volume mixer for Windows. Adjust the volume of any running
program with an audio session (or the system master volume) from a small
always-on-top overlay, the system tray, or global hotkeys.

![Sound Mixer overlay demo](assets/image.jpg)
![Sound Mixer overlay demo](assets/image-2.jpg)
![Sound Mixer overlay demo](assets/image-3.jpg)

<details>
<summary>Run, Build, Test details</summary>

## Running from source

```
pip install -r requirements.txt
python -m sound_mixer
```

## Building a standalone executable

```
python build.py
```

`build.py` checks that all packages in `requirements.txt` are installed at
the required versions. If anything is missing or outdated, it lists the
packages and asks whether to install them with `pip` before continuing. It
then runs PyInstaller and produces `dist/SoundMixer.exe`.

## Building the NSIS installers

NSIS 3.12 is required. Build the application first, then compile both x64
installer scopes with warnings treated as errors:

```powershell
python build.py
./scripts/build-installers.ps1 -Version 0.9.3 -MakeNsis "C:\Program Files (x86)\NSIS\makensis.exe"
```

The user installer writes to `%LOCALAPPDATA%\Programs\SoundMixer` without UAC.
The machine installer writes to `%ProgramFiles%\SoundMixer` through an
unelevated bootstrap and a controlled elevated file/registry phase. Both
support normal interactive installation, `/S`, `/SILENTWITHPROGRESS`, and the
standard NSIS `/D=<absolute-path>` override.

The WinGet manifest uses the machine installer, whose bootstrap requests
elevation only for the protected file and registry phase. The user installer
remains available as a release asset for direct installation without UAC.

To prepare the five release assets, checksums, and the four WinGet 1.12
manifests locally:

```powershell
./scripts/prepare-release.ps1 -Version 0.9.3
winget validate --manifest dist/winget
```

GitHub Actions tests branch and pull-request builds, but publishes a GitHub
Release only for a pre-existing `X.Y.Z` tag that exactly matches
`sound_mixer.__version__`. Optional Authenticode signing requires all three
repository secrets: `WINDOWS_SIGNING_CERTIFICATE_BASE64`,
`WINDOWS_SIGNING_CERTIFICATE_PASSWORD`, and `WINDOWS_TIMESTAMP_URL`. With none
configured, the same release is produced unsigned and verified by SHA-256.

## Running the tests

```
python -m pytest
```

Tests run in parallel via `pytest-xdist` (configured in `pytest.ini`). Tests
that need real Windows APIs (audio devices, the registry) are skipped on
non-Windows platforms.

</details>

<details>
<summary>Features</summary>

- Independent volume and mute controls for the system and every active audio
  application, with app icons and readable display names.
- Persistent per-application levels, mute states, hotkeys, overlay layout, and
  other preferences in a human-editable JSON file.
- Compact always-on-top overlay with optional Windows 11 acrylic transparency,
  accent-colored focus, and automatic recovery from off-screen positions.
- Horizontal and vertical layouts with independent saved size and position.
- Mouse, scroll wheel, and layout-aware arrow-key controls.
- Configurable global hotkeys, including overlay and mini-widget toggles,
  volume adjustment, focus navigation, and mute.
- Optional transparent mini widget for quick volume and mute control.
- Whitelist and ignored-app filters shared by the overlay and mini widget.
- System tray controls, optional launch at Windows login, and a setting to show
  the overlay immediately on startup.
- Adjustable interface scale, volume steps, tooltip delay, and transparency.
- Optional background scanning for audio child processes created by selected
  launchers, sandboxes, and other host applications.

</details>

<details>
<summary>Extra details</summary>

## Settings file (`settings.json`)

For source and portable runs, `settings.json` is created next to the source
tree or executable. An installed copy stores it in
`%LOCALAPPDATA%\GetItSimple\SoundMixer\settings.json`, regardless of installer
scope. A legacy file beside an installed executable is migrated atomically
only when the target file does not already exist. The file is plain JSON and
is safe to edit by hand while the app is not running. If the format changes
in a future version, it is migrated automatically on load.

| Field                  | Type            | Description                                                                                                                                                     |
| ---------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version`              | integer         | Settings schema version, used for migrations.                                                                                                                   |
| `master_volume`        | float (0.0-1.0) | System master volume level.                                                                                                                                     |
| `master_muted`         | bool            | System master mute state.                                                                                                                                       |
| `app_volumes`          | object          | Per-application volume/mute, keyed by the lowercase executable path with forward slashes (e.g. `"d:/games/mygame/game.exe"`), so two apps that share a file name keep separate settings. Each value is `{ "volume": float, "muted": bool }`. A bare executable name (e.g. `"chrome.exe"`) is still read as a legacy key and applies to any app with that file name. |
| `hotkeys`              | array           | Global hotkey bindings. Each entry is `{ "action": string, "combo": string, "enabled": bool }`.                                                                 |
| `autostart_enabled`    | bool            | Whether the app starts automatically on Windows login.                                                                                                          |
| `overlay`              | object          | Overlay window state: `"layout_mode"` (`"horizontal"` or `"vertical"`), `"visible_on_start"` (bool), and one `{ "x", "y", "width", "height" }` (pixels) block per layout mode under `"horizontal"` and `"vertical"`, so each mode keeps its own position and size. |
| `tooltip_delay_ms`     | integer         | Delay, in milliseconds, before action button tooltips appear.                                                                                                   |
| `volume_step`          | object          | `{ "arrow": float, "scroll": float }` - volume change per arrow-key press and per scroll wheel notch.                                                           |
| `ui_scale`             | float (0.5-3.0) | Overlay interface scale factor (fonts, icons, sliders). 1.0 is 100%.                                                                                            |
| `default_app_volume`   | float (0.0-1.0) | Initial volume applied to apps the first time they appear, if not already in `app_volumes`.                                                                     |
| `transparency_enabled` | bool            | Whether the overlay background uses the translucent acrylic effect. If disabled, the overlay has a solid background.                                            |
| `ignored_apps`         | array of string | Lowercase executable paths (e.g. `"d:/games/mygame/game.exe"`) hidden from the main entry list. Legacy bare executable names (e.g. `"discord.exe"`) still hide every app with that file name. Ignored entries can be revealed via the expand button. |
| `language`             | string          | UI language code (`"en"`, `"uk"`) or `"system"` to follow the Windows locale. Defaults to `"system"`. Changes take effect immediately when saved from Settings. |
| `subprocess_management` | object          | `{ "interval_seconds": int, "apps": [{ "path": string, "enabled": bool }] }` - shared polling interval and the list of host executables (e.g. sandbox/launcher apps) whose child processes need active background scanning because they don't trigger the normal session-created event. The scan itself is also gated by a session-only on/off switch in the overlay (not persisted - always starts off). |
| `whitelist`             | object          | `{ "enabled": bool, "apps": [{ "path": string, "enabled": bool }] }` - optional display filter for both the main overlay and mini widget. Full normalized paths distinguish same-named apps; bare session names fall back to matching an enabled path's file name. |
| `mini_widget`           | object          | `{ "enabled": bool, "x": int, "y": int, "scale": float }` - persisted visibility, screen position, and independent 0.5-3.0 interface scale of the mini volume widget. |

### Hotkey actions

| Action               | Default combo   | Effect                                                 |
| -------------------- | --------------- | ------------------------------------------------------ |
| `toggle_overlay`     | `ctrl+alt+num5` | Show/hide the overlay.                                 |
| `toggle_mini_widget` | (none)          | Show/hide the mini volume widget and persist the state.|
| `volume_up`          | (none)          | Increase the focused entry's volume by the arrow step. |
| `volume_down`        | (none)          | Decrease the focused entry's volume by the arrow step. |
| `focus_next`         | (none)          | Move focus to the next entry.                          |
| `focus_prev`         | (none)          | Move focus to the previous entry.                      |
| `mute_toggle`        | (none)          | Toggle mute on the focused entry.                      |

Hotkey combos are stored as `+`-separated key names, e.g. `ctrl+alt+num5`,
`ctrl+shift+f9`, `win+s`. In Settings they are shown key
names such as `Ctrl (Left)`, `Alt (Left)`, and `NumPad 5` as selectors inside
the same shortcut input. Modifier keys: `ctrl`, `alt`, `shift`, `win`. Numpad
digit keys are written as `num0`-`num9`.

## Known limitations

- True exclusive-fullscreen games (not borderless or "fullscreen windowed")
  can render above the overlay; use borderless/windowed fullscreen mode for
  the overlay to remain visible.
- The acrylic blur effect requires Windows 11 22H2 or later; on older Windows
  versions the overlay falls back to a plain semi-transparent background.
- On startup, the overlay briefly flashes near its last position and then
  hides again. This is required for the acrylic blur to render correctly once
  the overlay is later shown via a hotkey or the tray. With "Start opened"
  enabled the same flash still happens, and the overlay is reopened right
  after it.
- Global hotkeys are subject to Windows UIPI: an elevated foreground
  application will not receive hotkeys from a non-elevated Sound Mixer, and
  vice versa.
- Newly started applications may take a second or two to appear in the
  overlay, as sessions are picked up on a periodic refresh.
- An application with multiple audio sessions is shown as a single entry;
  volume and mute changes apply to all of its sessions.
- "System Sounds" has no dedicated entry; use the master volume entry to
  control it.
- The overlay position is stored in raw pixel coordinates. If a monitor is
  disconnected or resolution changes, the overlay may appear off-screen and
  need to be dragged back manually.
- If `SoundMixer.exe` is moved after enabling autostart, the registry entry
still points at the old path; re-enable autostart from Settings to update
it.
  </details>

## Supported languages

| Language               | Code | Added by |
| ---------------------- | ---- | -------- |
| English                | `en` | author   |
| Українська (Ukrainian) | `uk` | author   |

<details>
<summary>How to add a new translation</summary>

1. **Create the language file.** Copy `sound_mixer/i18n/en.py` to a new file named after the
   [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) code of the language
   (e.g. `sound_mixer/i18n/de.py` for German). Translate every string value; do not change
   the keys.

2. **Register the language in the i18n module.** Open `sound_mixer/i18n/__init__.py` and make
   two additions:
    - Add the code to `AVAILABLE_LANGUAGES`:
        ```python
        AVAILABLE_LANGUAGES: list[str] = ["en", "uk", "de"]
        ```
    - Add a branch in `_load_language_strings()` to import the new module:
        ```python
        def _load_language_strings(language: str) -> dict[str, str]:
            if language == "uk":
                from sound_mixer.i18n.uk import STRINGS
                return STRINGS
            if language == "de":
                from sound_mixer.i18n.de import STRINGS
                return STRINGS
            return {}
        ```

3. **Add tests.** In `tests/test_i18n.py`, add a test that calls `i18n.setup("de")` and
   asserts at least one translated string is returned correctly.

4. **Update this table** in `README.md` with the new language and your name.

5. **Bump the version** in `sound_mixer/__init__.py` (required for every source change).

</details>

<details>
<summary>Third-party packages</summary>

| Package                                                | License                           | Notes           |
| ------------------------------------------------------ | --------------------------------- | --------------- |
| [pycaw](https://github.com/AndreMiras/pycaw)           | MIT                               |                 |
| [comtypes](https://github.com/enthought/comtypes)      | MIT                               |                 |
| [PySide6](https://pypi.org/project/PySide6/)           | LGPL-3.0                          |                 |
| [psutil](https://github.com/giampaolo/psutil)          | BSD-3-Clause                      |                 |
| [PyInstaller](https://pyinstaller.org/)                | GPL-2.0 with Bootloader Exception | build tool only |
| [pytest](https://pytest.org/)                          | MIT                               | test only       |
| [pytest-xdist](https://pypi.org/project/pytest-xdist/) | MIT                               | test only       |

</details>
