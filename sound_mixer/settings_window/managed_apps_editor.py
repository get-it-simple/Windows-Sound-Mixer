import os
from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sound_mixer.audio.win_names import get_exe_friendly_name
from sound_mixer.executable_path import InvalidExecutablePathError, resolve_application_path
from sound_mixer.i18n import t
from sound_mixer.overlay.icons import DelayedTooltipButton, bordered_input_style, load_icon, toggle_switch_style


def resolve_app_display_name(path: str) -> str:
    return get_exe_friendly_name(path) or os.path.basename(path)


class AppDropZone(QFrame):
    app_dropped = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("appDropZone")
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(bordered_input_style("appDropZone"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self._label = QLabel(t("drop_app_here"), self)
        self._label.setStyleSheet("color: #b7b7bd; padding-left: 2px;")
        layout.addWidget(self._label)

    def retranslate(self) -> None:
        self._label.setText(t("drop_app_here"))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.app_dropped.emit(path)
        event.acceptProposedAction()


class AppDragHandle(DelayedTooltipButton):
    dragged = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._dragging = False
        self.setIcon(load_icon("drag"))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            "QToolButton { background: #626071; border: none; border-radius: 4px; padding: 4px; }"
            "QToolButton:hover, QToolButton:pressed { background: #716f82; }"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setDown(True)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.dragged.emit(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setDown(False)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ManagedAppRow(QFrame):
    remove_requested = Signal()

    def __init__(self, path: str, enabled: bool = True, parent: Optional[QWidget] = None, *, reorderable: bool = False) -> None:
        super().__init__(parent)
        self.path = path

        self._enabled_checkbox = QCheckBox(self)
        self._enabled_checkbox.setObjectName("managedAppToggle")
        self._enabled_checkbox.setStyleSheet(toggle_switch_style("managedAppToggle"))
        self._enabled_checkbox.setChecked(enabled)

        self._name_label = QLabel(resolve_app_display_name(path), self)
        self._name_label.setToolTip(path)

        self._remove_button = DelayedTooltipButton(self)
        self._remove_button.setIcon(load_icon("trash"))
        self._remove_button.setToolTip(t("remove_managed_app_tooltip"))
        self._remove_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._remove_button.clicked.connect(self.remove_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._enabled_checkbox)
        layout.addWidget(self._name_label, 1)
        self._drag_handle = AppDragHandle(self)
        self._drag_handle.setVisible(reorderable)
        layout.addWidget(self._drag_handle)
        layout.addWidget(self._remove_button)
        self.retranslate()

    def is_enabled(self) -> bool:
        return self._enabled_checkbox.isChecked()

    def retranslate(self) -> None:
        self._drag_handle.setToolTip(t("drag_app_tooltip"))
        self._drag_handle.setAccessibleName(t("drag_app_tooltip"))
        self._remove_button.setToolTip(t("remove_managed_app_tooltip"))


class AppListEditor(QWidget):
    def __init__(self, apps: list[dict], parent: Optional[QWidget] = None, *, reorderable: bool = False) -> None:
        super().__init__(parent)
        self.rows: list[ManagedAppRow] = []
        self._reorderable = reorderable

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.drop_zone = AppDropZone(self)
        self.drop_zone.app_dropped.connect(self.add_path)
        layout.addWidget(self.drop_zone)
        self._error_label = QLabel(t("invalid_application_drop"), self)
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #e05555;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        rows_container = QWidget(self)
        self.rows_layout = QVBoxLayout(rows_container)
        self.rows_layout.setContentsMargins(0, 8, 0, 0)
        self.rows_layout.setSpacing(6)
        layout.addWidget(rows_container)

        for app in apps:
            self.add_path(app["path"], app.get("enabled", True))

    def add_path(self, path: str, enabled: bool = True) -> None:
        try:
            path = resolve_application_path(path)
        except InvalidExecutablePathError:
            self._error_label.show()
            return
        self._error_label.hide()
        if any(row.path.lower() == path.lower() for row in self.rows):
            return
        self.add_row(path, enabled)

    def add_row(self, path: str, enabled: bool) -> ManagedAppRow:
        row = ManagedAppRow(path, enabled, self, reorderable=self._reorderable)
        row._drag_handle.dragged.connect(lambda position, r=row: self._drag_row(r, position))
        row.remove_requested.connect(lambda r=row: self.remove_row(r))
        self.rows_layout.addWidget(row)
        self.rows.append(row)
        return row

    def remove_row(self, row: ManagedAppRow) -> None:
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()

    def move_row(self, row: ManagedAppRow, delta: int) -> None:
        index = self.rows.index(row)
        target = index + delta
        if not 0 <= target < len(self.rows):
            return
        self.rows.insert(target, self.rows.pop(index))
        self.rows_layout.removeWidget(row)
        self.rows_layout.insertWidget(target, row)

    def _drag_row(self, row: ManagedAppRow, global_position: QPoint) -> None:
        container = self.rows_layout.parentWidget()
        position = container.mapFromGlobal(global_position)
        if not container.rect().contains(position):
            return
        target = min(
            range(len(self.rows)),
            key=lambda index: abs(self.rows[index].geometry().center().y() - position.y()),
        )
        index = self.rows.index(row)
        if target != index:
            self.move_row(row, target - index)
            self.rows_layout.activate()

    def apps(self) -> list[dict]:
        return [{"path": row.path, "enabled": row.is_enabled()} for row in self.rows]

    def retranslate(self) -> None:
        self.drop_zone.retranslate()
        self._error_label.setText(t("invalid_application_drop"))
        for row in self.rows:
            row.retranslate()
