import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sound_mixer.audio.win_names import get_exe_friendly_name
from sound_mixer.executable_path import InvalidExecutablePathError, resolve_local_executable
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


class ManagedAppRow(QFrame):
    remove_requested = Signal()

    def __init__(self, path: str, enabled: bool = True, parent: Optional[QWidget] = None) -> None:
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
        layout.addWidget(self._remove_button)

    def is_enabled(self) -> bool:
        return self._enabled_checkbox.isChecked()

    def retranslate(self) -> None:
        self._remove_button.setToolTip(t("remove_managed_app_tooltip"))


class AppListEditor(QWidget):
    def __init__(self, apps: list[dict], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.rows: list[ManagedAppRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.drop_zone = AppDropZone(self)
        self.drop_zone.app_dropped.connect(self.add_path)
        layout.addWidget(self.drop_zone)

        rows_container = QWidget(self)
        self.rows_layout = QVBoxLayout(rows_container)
        self.rows_layout.setContentsMargins(0, 8, 0, 0)
        self.rows_layout.setSpacing(6)
        layout.addWidget(rows_container)

        for app in apps:
            self.add_path(app["path"], app.get("enabled", True))

    def add_path(self, path: str, enabled: bool = True) -> None:
        try:
            path = resolve_local_executable(path)
        except InvalidExecutablePathError:
            return
        if any(row.path.lower() == path.lower() for row in self.rows):
            return
        self.add_row(path, enabled)

    def add_row(self, path: str, enabled: bool) -> ManagedAppRow:
        row = ManagedAppRow(path, enabled, self)
        row.remove_requested.connect(lambda r=row: self.remove_row(r))
        self.rows_layout.addWidget(row)
        self.rows.append(row)
        return row

    def remove_row(self, row: ManagedAppRow) -> None:
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()

    def apps(self) -> list[dict]:
        return [{"path": row.path, "enabled": row.is_enabled()} for row in self.rows]

    def retranslate(self) -> None:
        self.drop_zone.retranslate()
        for row in self.rows:
            row.retranslate()
