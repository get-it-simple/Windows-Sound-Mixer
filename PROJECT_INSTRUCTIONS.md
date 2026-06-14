# Project Instructions

## Requirements

- Build a per-application volume mixer for Windows.
- Use Python.
- Keep the code clean, simple, and readable.
- Do not leave comments in the code.
- No restrictions on third-party dependencies; use whatever packages are appropriate for audio control, hotkeys, overlays, etc.
- Keep project responsibilities split across the appropriate files and modules.
- Write project documentation and instruction files in English.
- Allow controlling the volume of any running process that has an audio session or plays media, independent of other applications.
- Give each application its own persistent volume level.
- Persist all settings (volume levels, hotkeys, autostart, overlay options) between application restarts.
- Store application settings in a human-editable JSON file next to the application.
- If the settings file format changes, migrate existing settings files to the new format.
- Support enabling and disabling autostart on Windows login.
- Provide an always-on-top overlay for volume control that works over fullscreen and exclusive-fullscreen games/apps, without injecting into or otherwise interfering with other processes.
- Support user-configurable global hotkeys (e.g. Ctrl+Alt+Numpad5) for showing/hiding the overlay and adjusting volume.
- Support mouse-based volume control in the overlay.
- Support keyboard control in the overlay: Left/Right arrows adjust the volume of the focused application; Up/Down arrows move focus between application volume controls.
- Use icon-only action buttons with hover tooltips.
- Store the tooltip display delay in settings.
- Keep the application version in `sound_mixer/__init__.py`.
- Update the application version with every user-visible behavior change, feature addition, or compatibility fix.
- Show the application version in the UI so builds can be identified during support and testing.
- Keep a short settings file structure summary in `README.md` and update it with every settings format change.
- Package the application as a standalone executable using PyInstaller.
- Provide a build script that checks for required dependencies and prompts the user before installing missing ones.
- Cover application functionality with automated tests.
- Tests must support parallel execution, scaled to the number of available CPU threads on the system.
- Run the full test suite before accepting code changes.
- When fixing a bug, add or update a regression test that would fail before the fix and pass after it, so the same class of bug cannot silently return.
- Do not cheat with unit tests: tests must assert externally visible behavior or stable data contracts, must not only mirror implementation details, must not skip critical assertions to pass, and must not mock the code under test so heavily that the real behavior is no longer exercised.

## Implementation Notes

- Use the Windows Core Audio API (e.g. via `pycaw`) to enumerate per-process audio sessions and set per-application volume independently of the system master volume and other applications.
- The overlay window must stay on top of fullscreen and exclusive-fullscreen applications without stealing focus or input from them unless the user is actively interacting with it.
- Implement global hotkeys with a keyboard-hook library (e.g. `keyboard`); bindings must be configurable, not hardcoded.
- Toggle autostart via a Windows Registry "Run" key entry (HKCU) so no administrator privileges are required.
- Keep mouse, hotkey, and keyboard (arrow key) input on the same per-application volume model so all input methods stay in sync.
- Use `pytest` with `pytest-xdist` for parallel test execution (`-n auto`), scaled to the number of available CPU cores.
- The build script should detect missing dependencies (PyInstaller and runtime packages) and prompt the user before installing them with `pip`.
- Configuration should remain human-editable JSON.
