import sys

import pytest
from PySide6.QtCore import QFile, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

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


def drag_move(qapp, handle, position, buttons=Qt.MouseButton.LeftButton):
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(handle.mapFromGlobal(position)),
        QPointF(position),
        Qt.MouseButton.NoButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(handle, event)
    qapp.processEvents()


def test_drag_handle_moves_rows_and_preserves_enabled_state(qapp, tmp_path):
    apps = []
    for name in ("First", "Second", "Third"):
        path = tmp_path / f"{name}.exe"
        path.write_bytes(b"MZ")
        apps.append({"path": str(path), "enabled": name != "Second"})
    editor = AppListEditor(apps, reorderable=True)
    editor.show()
    qapp.processEvents()
    rows = editor.rows
    first, second, third = rows
    handle = second._drag_handle
    QTest.mousePress(handle, Qt.MouseButton.LeftButton)
    assert handle.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    drag_move(qapp, handle, first.mapToGlobal(first.rect().center()))

    assert editor.rows is rows
    assert editor.apps() == [apps[1], apps[0], apps[2]]
    assert editor.rows_layout.itemAt(0).widget() is second
    drag_move(qapp, handle, third.mapToGlobal(third.rect().center()))
    assert editor.apps() == [apps[0], apps[2], apps[1]]
    assert editor.rows_layout.itemAt(2).widget() is second
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton)
    assert handle.cursor().shape() == Qt.CursorShape.OpenHandCursor
    drag_move(qapp, handle, first.mapToGlobal(first.rect().center()))
    assert editor.apps() == [apps[0], apps[2], apps[1]]
    editor.close()


def test_drag_stays_in_its_section_and_requires_left_mouse_button(qapp):
    editor = AppListEditor([], reorderable=True)
    first = editor.add_row("First.exe", True)
    second = editor.add_row("Second.exe", True)
    editor.show()
    qapp.processEvents()
    handle = second._drag_handle
    QTest.mousePress(handle, Qt.MouseButton.RightButton)
    drag_move(qapp, handle, first.mapToGlobal(first.rect().center()), Qt.MouseButton.RightButton)
    QTest.mouseRelease(handle, Qt.MouseButton.RightButton)
    assert editor.rows == [first, second]

    QTest.mousePress(handle, Qt.MouseButton.LeftButton)
    drag_move(qapp, handle, editor.drop_zone.mapToGlobal(editor.drop_zone.rect().center()))
    assert editor.rows == [first, second]
    drag_move(qapp, handle, first.mapToGlobal(QPoint(-20, first.rect().center().y())))
    assert editor.rows == [first, second]
    drag_move(qapp, handle, first.mapToGlobal(first.rect().center()))
    assert editor.rows == [second, first]
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton)
    editor.close()


def test_non_reorderable_editor_hides_drag_handle(qapp):
    editor = AppListEditor([])
    row = editor.add_row("App.exe", True)
    assert row._drag_handle.isHidden()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts")
def test_dropped_shortcut_resolves_target_and_deduplicates(qapp, tmp_path):
    target = tmp_path / "Target.exe"
    target.write_bytes(b"MZ")
    shortcut = tmp_path / "Application shortcut.lnk"
    assert QFile(str(target)).link(str(shortcut))
    editor = AppListEditor([])

    editor.drop_zone.app_dropped.emit(str(shortcut))
    editor.drop_zone.app_dropped.emit(str(target))

    assert editor.apps() == [{"path": str(target.resolve()), "enabled": True}]
    assert editor.rows[0]._name_label.text() == "Target.exe"
    assert editor._error_label.isHidden()


def test_invalid_drop_shows_error_and_valid_drop_clears_it(qapp, tmp_path):
    editor = AppListEditor([])
    editor.add_path(str(tmp_path / "missing.lnk"))
    assert not editor._error_label.isHidden()
    assert editor.apps() == []
    target = tmp_path / "Target.exe"
    target.write_bytes(b"MZ")
    editor.add_path(str(target))
    assert editor._error_label.isHidden()
