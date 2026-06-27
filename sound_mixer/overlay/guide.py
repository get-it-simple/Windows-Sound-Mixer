from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sound_mixer.overlay.icons import load_icon

_SECTIONS = [
    (
        "Mouse",
        [
            ("Hover overlay + scroll wheel", "Adjust the focused application's volume"),
            ("Drag the slider", "Set volume to an exact level"),
            ("Click the mute button", "Toggle mute on / off for that application"),
        ],
    ),
    (
        "Keyboard (overlay focused)",
        [
            ("Up / Down arrows", "Move focus between applications"),
            ("Left / Right arrows", "Decrease / increase the focused application's volume"),
        ],
    ),
    (
        "Global hotkeys",
        [
            ("Show / Hide overlay", "Toggle overlay visibility from any application"),
            ("Volume up / down", "Adjust the focused application's volume without opening the overlay"),
            ("Focus next / previous", "Move focus while the overlay is hidden"),
            ("Mute toggle", "Toggle mute for the focused application"),
            ("", "Configure bindings in Settings → Hotkeys"),
        ],
    ),
]

_DIALOG_STYLE = """
QDialog {
    background: #1e1e1e;
    color: #f2f2f5;
}
#guideFrame {
    background: #252526;
    border-radius: 10px;
    padding: 0px;
}
#sectionHeader {
    color: #c8c8d4;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
#rowKey {
    color: #bbbbc8;
    font-size: 12px;
    background: rgba(255, 255, 255, 14);
    border-radius: 5px;
    padding: 2px 8px;
    min-width: 180px;
    max-width: 220px;
}
#rowKey[note="true"] {
    color: #8888a0;
    background: transparent;
    font-style: italic;
    padding: 2px 0px;
}
#rowDesc {
    color: #f2f2f5;
    font-size: 12px;
}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 55);
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 80);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


class _FullSizeScrollArea(QScrollArea):
    def sizeHint(self) -> QSize:
        widget = self.widget()
        if widget is None:
            return super().sizeHint()
        hint = widget.sizeHint()
        sb_width = self.verticalScrollBar().sizeHint().width()
        return QSize(hint.width() + sb_width, hint.height())


class GuideDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Controls Guide")
        self.setWindowIcon(load_icon("logo"))
        self.setMinimumWidth(480)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.adjustSize()
        max_height = round(available.height() * 0.88)
        if self.height() > max_height:
            self.resize(self.width(), max_height)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(20)

        for title, rows in _SECTIONS:
            content_layout.addWidget(self._build_section(title, rows, content))

        content_layout.addStretch(1)

        scroll = _FullSizeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        frame = QFrame()
        frame.setObjectName("guideFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(scroll)

        outer.addWidget(frame)

    def _build_section(self, title: str, rows: list[tuple[str, str]], parent: QWidget) -> QWidget:
        section = QWidget(parent)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel(title.upper(), section)
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        for key, desc in rows:
            row = QWidget(section)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            key_label = QLabel(key, row)
            key_label.setObjectName("rowKey")
            key_label.setWordWrap(False)
            if not key:
                key_label.setProperty("note", "true")

            desc_label = QLabel(desc, row)
            desc_label.setObjectName("rowDesc")
            desc_label.setWordWrap(True)

            row_layout.addWidget(key_label, 0, Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(desc_label, 1, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(row)

        return section
