from PySide6.QtCore import (
    Property, QEasingCurve, QPauseAnimation,
    QPropertyAnimation, QSequentialAnimationGroup, QSize, Qt,
)
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from sound_mixer.i18n import t
from sound_mixer.overlay.icons import load_icon


def _get_sections() -> list[tuple[str, list[tuple[str, str]]]]:
    return [
        (
            t("guide_section_mouse"),
            [
                (t("guide_scroll"), t("guide_scroll_desc")),
                (t("guide_drag"), t("guide_drag_desc")),
                (t("guide_mute_click"), t("guide_mute_click_desc")),
            ],
        ),
        (
            t("guide_section_keyboard"),
            [
                (t("guide_arrows_ud"), t("guide_arrows_ud_desc")),
                (t("guide_arrows_lr"), t("guide_arrows_lr_desc")),
            ],
        ),
        (
            t("guide_section_hotkeys"),
            [
                (t("guide_hotkey_toggle"), t("guide_hotkey_toggle_desc")),
                (t("guide_hotkey_vol"), t("guide_hotkey_vol_desc")),
                (t("guide_hotkey_focus"), t("guide_hotkey_focus_desc")),
                (t("guide_hotkey_mute"), t("guide_hotkey_mute_desc")),
                ("", t("guide_hotkey_note")),
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


class _MarqueeLabel(QWidget):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rowDesc")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._text = text
        self._x = 0

        self._fwd = QPropertyAnimation(self, b"xOffset")
        self._fwd.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._bwd = QPropertyAnimation(self, b"xOffset")
        self._bwd.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pause1 = QPauseAnimation(700)
        self._pause2 = QPauseAnimation(700)

        self._group = QSequentialAnimationGroup(self)
        self._group.setLoopCount(-1)
        self._group.addAnimation(self._fwd)
        self._group.addAnimation(self._pause1)
        self._group.addAnimation(self._bwd)
        self._group.addAnimation(self._pause2)

    @Property(int)
    def xOffset(self) -> int:
        return self._x

    @xOffset.setter
    def xOffset(self, value: int) -> None:
        self._x = value
        self.update()

    def text(self) -> str:
        return self._text

    def start_marquee(self) -> None:
        container_w = self.width()
        if container_w <= 0:
            return
        text_w = self.fontMetrics().horizontalAdvance(self._text)
        if text_w <= container_w:
            return
        travel = text_w - container_w
        duration = max(1000, travel * 12)

        self._fwd.setDuration(duration)
        self._fwd.setStartValue(0)
        self._fwd.setEndValue(-travel)

        self._bwd.setDuration(duration)
        self._bwd.setStartValue(-travel)
        self._bwd.setEndValue(0)

        self._x = 0
        self._group.start()

    def stop_marquee(self) -> None:
        self._group.stop()
        self._x = 0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text_w = self.fontMetrics().horizontalAdvance(self._text) + 2
        painter.drawText(self._x, 0, text_w, self.height(),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self._text)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(160, fm.height() + 6)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height() + 6)


class _GuideRow(QWidget):
    def __init__(self, key_label: QLabel, marquee: _MarqueeLabel, parent=None) -> None:
        super().__init__(parent)
        self._marquee = marquee
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(key_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(marquee, 1, Qt.AlignmentFlag.AlignVCenter)

    def enterEvent(self, event) -> None:
        self._marquee.start_marquee()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._marquee.stop_marquee()
        super().leaveEvent(event)


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
        self.setWindowTitle(t("controls_guide_title"))
        self.setWindowIcon(load_icon("logo"))
        self.setMinimumWidth(640)
        self.setStyleSheet(_DIALOG_STYLE)
        self._key_labels: list[QLabel] = []
        self._build_ui()
        self._equalize_key_widths()
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

    def _equalize_key_widths(self) -> None:
        if not self._key_labels:
            return
        max_w = max(lbl.sizeHint().width() for lbl in self._key_labels)
        for lbl in self._key_labels:
            lbl.setFixedWidth(max_w)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(20)

        for title, rows in _get_sections():
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
            key_label = QLabel(key, section)
            key_label.setObjectName("rowKey")
            key_label.setWordWrap(False)
            if not key:
                key_label.setProperty("note", "true")
            self._key_labels.append(key_label)

            marquee = _MarqueeLabel(desc, section)
            layout.addWidget(_GuideRow(key_label, marquee, section))

        return section
