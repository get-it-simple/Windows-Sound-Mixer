import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from sound_mixer.audio.win_names import get_exe_friendly_name
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
