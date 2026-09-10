import sys

from sound_mixer.settings_window.managed_apps_editor import (
    AppDropZone,
    AppListEditor,
    ManagedAppRow,
    resolve_app_display_name,
)


def test_resolve_app_display_name_falls_back_to_basename():
    assert resolve_app_display_name("C:/Games/totally_unknown_binary.exe") == "totally_unknown_binary.exe"


def test_resolve_app_display_name_uses_friendly_name_when_available():
    name = resolve_app_display_name(sys.executable)

    assert name


def test_managed_app_row_defaults_enabled(qapp):
    row = ManagedAppRow("C:/Games/sandbox.exe")

    assert row.path == "C:/Games/sandbox.exe"
    assert row.is_enabled() is True
    assert row._name_label.toolTip() == "C:/Games/sandbox.exe"


def test_managed_app_row_respects_enabled_flag(qapp):
    row = ManagedAppRow("C:/Games/sandbox.exe", enabled=False)

    assert row.is_enabled() is False


def test_managed_app_row_remove_signal(qapp):
    row = ManagedAppRow("C:/Games/sandbox.exe")
    emitted = []
    row.remove_requested.connect(lambda: emitted.append(1))

    row._remove_button.click()

    assert emitted == [1]


def test_app_drop_zone_object_name_and_style(qapp):
    zone = AppDropZone()

    assert zone.objectName() == "appDropZone"
    assert "QFrame#appDropZone" in zone.styleSheet()
    assert zone.acceptDrops() is True


def test_app_drop_zone_drop_event_emits_path(qapp):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtCore import QPointF
    from PySide6.QtCore import Qt

    zone = AppDropZone()
    emitted = []
    zone.app_dropped.connect(emitted.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(sys.executable)])
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    zone.dropEvent(event)

    assert emitted == [sys.executable.replace("\\", "/")]


def test_app_list_editor_adds_dedupes_removes_and_exports_rows(qapp, tmp_path):
    aurora = tmp_path / "Aurora.exe"
    lumen = tmp_path / "Lumen.exe"
    aurora.write_bytes(b"MZ")
    lumen.write_bytes(b"MZ")
    editor = AppListEditor([{"path": str(aurora), "enabled": False}])

    editor.add_path(str(aurora).replace("\\", "/"))
    editor.add_path(str(lumen))
    editor.remove_row(editor.rows[0])

    assert editor.apps() == [{"path": str(lumen.resolve()), "enabled": True}]


def test_app_list_editor_rejects_invalid_path_without_reading_metadata(qapp, monkeypatch):
    def fail_if_called(_):
        raise AssertionError("metadata lookup must not run")

    monkeypatch.setattr(
        "sound_mixer.settings_window.managed_apps_editor.get_exe_friendly_name",
        fail_if_called,
    )
    editor = AppListEditor([])

    editor.add_path(r"\\server\share\Remote.exe")

    assert editor.rows == []


def test_reorder_buttons_move_rows_and_preserve_enabled_state(qapp, tmp_path):
    apps = []
    for name in ("First", "Second", "Third"):
        path = tmp_path / f"{name}.exe"
        path.write_bytes(b"MZ")
        apps.append({"path": str(path), "enabled": name != "Second"})
    editor = AppListEditor(apps, reorderable=True)
    rows = editor.rows
    second = rows[1]

    second._move_up_button.click()

    assert editor.rows is rows
    assert editor.apps() == [apps[1], apps[0], apps[2]]
    assert editor.rows_layout.itemAt(0).widget() is second
    assert not second._move_up_button.isEnabled()
    second._move_down_button.click()
    second._move_down_button.click()
    assert editor.apps() == [apps[0], apps[2], apps[1]]
    assert not second._move_down_button.isEnabled()
    editor.remove_row(second)
    assert not editor.rows[-1]._move_down_button.isEnabled()
