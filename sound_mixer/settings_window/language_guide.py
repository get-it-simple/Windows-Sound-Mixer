from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from sound_mixer.i18n import t
from sound_mixer.overlay.guide import _DIALOG_STYLE
from sound_mixer.overlay.icons import load_icon


class LanguageGuideDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("language_guide_title"))
        self.setWindowIcon(load_icon("logo"))
        self.setStyleSheet(_DIALOG_STYLE)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        for key in ("language_guide_copy", "language_guide_translate", "language_guide_build"):
            label = QLabel(t(key), content)
            label.setObjectName("rowDesc")
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            content_layout.addWidget(label)
        content_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        frame = QFrame(self)
        frame.setObjectName("guideFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(scroll)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(frame)

        available = self.screen().availableGeometry()
        self.resize(min(560, round(available.width() * 0.88)), min(320, round(available.height() * 0.88)))
