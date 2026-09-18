from PySide6.QtCore import (
    Property, QEvent, QEasingCurve, QPauseAnimation,
    QPropertyAnimation, QSequentialAnimationGroup, QSize, Qt,
)
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QSizePolicy, QWidget


class MarqueeLabel(QWidget):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._text = text
        self._x = 0
        self._hovered = False
        self._fwd = QPropertyAnimation(self, b"xOffset")
        self._fwd.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._bwd = QPropertyAnimation(self, b"xOffset")
        self._bwd.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._group = QSequentialAnimationGroup(self)
        self._group.setLoopCount(-1)
        self._group.addAnimation(self._fwd)
        self._group.addAnimation(QPauseAnimation(700))
        self._group.addAnimation(self._bwd)
        self._group.addAnimation(QPauseAnimation(700))

    @Property(int)
    def xOffset(self) -> int:
        return self._x

    @xOffset.setter
    def xOffset(self, value: int) -> None:
        self._x = value
        self.update()

    def text(self) -> str:
        return self._text

    def alignment(self) -> Qt.AlignmentFlag:
        return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

    def setText(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self._update_marquee()

    def start_marquee(self) -> None:
        if not self._hovered:
            self._hovered = True
            self._update_marquee()

    def stop_marquee(self) -> None:
        self._hovered = False
        self._update_marquee()

    def _update_marquee(self) -> None:
        self._group.stop()
        self.xOffset = 0
        if not self._hovered or not self.isVisible() or self.width() <= 0:
            return
        travel = self.fontMetrics().horizontalAdvance(self._text) - self.width()
        if travel <= 0:
            return
        duration = max(1000, travel * 12)
        self._fwd.setDuration(duration)
        self._fwd.setStartValue(0)
        self._fwd.setEndValue(-travel)
        self._bwd.setDuration(duration)
        self._bwd.setStartValue(-travel)
        self._bwd.setEndValue(0)
        self._group.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_marquee()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.updateGeometry()
            self._update_marquee()

    def hideEvent(self, event) -> None:
        self.stop_marquee()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text_w = self.fontMetrics().horizontalAdvance(self._text) + 2
        painter.drawText(self._x, 0, text_w, self.height(),
                         self.alignment(),
                         self._text)

    def sizeHint(self) -> QSize:
        return QSize(160, self.fontMetrics().height() + 6)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height() + 6)
