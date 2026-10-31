from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QTextLayout, QTextOption
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sound_mixer.i18n import t
from sound_mixer.overlay.icons import DelayedTooltipButton, load_app_icon, load_icon


class MediaTitle(QWidget):
    def __init__(self, text, parent=None, scale=1.0):
        super().__init__(parent)
        self.text = text
        self._scale = scale
        self._lines = []
        self._layout_key = None
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(120, self.height())

    def _measure(self, font):
        text = " ".join(self.text.split())
        layout = QTextLayout(text, font)
        metrics = QFontMetrics(font)
        encoded = text.encode("utf-16-le")
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        lines = []
        height = 0
        while len(lines) < 4:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(1, self.width()))
            if height + metrics.lineSpacing() > self.height():
                break
            lines.append((line.textStart(), line.textLength()))
            height += metrics.lineSpacing()
        layout.endLayout()
        result = []
        for index, (start, length) in enumerate(lines):
            remaining = encoded[start * 2:].decode("utf-16-le")
            if index == len(lines) - 1 and (start + length) * 2 < len(encoded):
                result.append(metrics.elidedText(remaining, Qt.TextElideMode.ElideRight, self.width()))
            else:
                result.append(encoded[start * 2:(start + length) * 2].decode("utf-16-le").rstrip())
        complete = not text or bool(lines and (lines[-1][0] + lines[-1][1]) * 2 >= len(encoded))
        return result, complete

    def _reflow(self):
        key = (self.text, self.width(), self.height(), self._scale)
        if key == self._layout_key:
            return
        self._layout_key = key
        font = self.font()
        minimum = max(1, round(13 * self._scale))
        for pixels in range(max(minimum, round(18 * self._scale)), minimum - 1, -1):
            font.setPixelSize(pixels)
            lines, complete = self._measure(font)
            if complete or pixels == minimum:
                self.setFont(font)
                self._lines = lines
                break
        self.update()

    def lines(self):
        self._reflow()
        return self._lines

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        metrics = self.fontMetrics()
        offset = max(0, (self.height() - len(self._lines) * metrics.lineSpacing()) // 2)
        for index, text in enumerate(self._lines):
            painter.drawText(0, offset + metrics.ascent() + index * metrics.lineSpacing(), text)


class MediaCard(QFrame):
    action_requested = Signal(str, int, str)

    def __init__(self, item, scale=1.0, source_name="", icon_path="", show_owner=False, parent=None, show_source=False, tooltip_delay_ms=500):
        super().__init__(parent)
        self.item = item
        self.setObjectName("mediaCard")
        self.setToolTip(source_name or item.source)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(round(8 * scale), round(4 * scale), round(8 * scale), round(4 * scale))
        layout.setSpacing(round(8 * scale))
        self.owner_icon = QLabel(self)
        self.owner_icon.setFixedSize(round(24 * scale), round(24 * scale))
        self.owner_icon.setPixmap((load_app_icon(icon_path) if icon_path else load_icon("volume")).pixmap(self.owner_icon.size()))
        self.owner_icon.setToolTip(source_name or item.source)
        self.owner_icon.setVisible(show_owner)
        layout.addWidget(self.owner_icon)
        self.cover = QLabel(self)
        self.cover.setFixedSize(round(64 * scale), round(64 * scale))
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap.fromImage(item.image) if not item.image.isNull() else load_icon("volume").pixmap(self.cover.size())
        self.cover.setPixmap(pixmap.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.cover)
        title = item.title or t("media_untitled")
        if show_source:
            title = f"{source_name or item.source}: {title}"
        text_column = QWidget(self)
        text_column.setFixedHeight(round(64 * scale))
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(round(4 * scale))
        self.title = MediaTitle(title, text_column, scale)
        self.title.setFixedHeight(round(64 * scale) - round(24 * scale) - round(4 * scale))
        text_layout.addWidget(self.title)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(round(4 * scale))
        self.buttons = {}
        play_action = "play" if item.playback_state == "paused" else "pause"
        for action in ("previous", play_action, "next"):
            button = DelayedTooltipButton(text_column, tooltip_delay_ms=tooltip_delay_ms)
            button.setObjectName(f"media_{action}")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedSize(round(24 * scale), round(24 * scale))
            button.setIconSize(QSize(round(16 * scale), round(16 * scale)))
            button.setIcon(load_icon(action))
            button.setToolTip(t(f"media_{action}"))
            button.setEnabled(not item.pending_action and getattr(item, f"can_{action}"))
            button.clicked.connect(lambda checked=False, a=action: self.action_requested.emit(item.session_id, item.generation, a))
            controls.addWidget(button)
            self.buttons[action] = button
        controls.addStretch(1)
        text_layout.addLayout(controls)
        text_column.setMinimumWidth(round(80 * scale))
        layout.addWidget(text_column, 1)


class MediaConnections(QWidget):
    def __init__(self, parent: QWidget, viewport: QWidget):
        super().__init__(parent)
        self._links = []
        self._color = QColor()
        self._background = parent
        self._viewport = viewport
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        parent.installEventFilter(self)

    def set_links(self, links, color):
        for owner, card in self._links:
            owner.removeEventFilter(self)
            card.removeEventFilter(self)
        self._links = links
        self._color = color
        for owner, card in links:
            owner.installEventFilter(self)
            card.installEventFilter(self)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.update()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.LayoutRequest):
            if watched is self.parentWidget():
                self.setGeometry(self._background.rect())
            self.update()
        return False

    def paintEvent(self, event):
        if not self._links:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._color, 1))
        footer_viewport = self._links[0][1].parentWidget().parentWidget()
        junction_y = self.mapFromGlobal(footer_viewport.mapToGlobal(QPoint())).y() - 2
        for owner, card in self._links:
            if not owner.isVisible() or not card.isVisible():
                continue
            visible = QRect(owner.mapTo(self._viewport, QPoint()), owner.size()).intersected(self._viewport.rect())
            if visible.isEmpty():
                continue
            visible_card = QRect(card.mapTo(footer_viewport, QPoint()), card.size()).intersected(footer_viewport.rect())
            if visible_card.isEmpty():
                continue
            start = self.mapFromGlobal(self._viewport.mapToGlobal(QPoint(visible.center().x(), visible.bottom())))
            end = self.mapFromGlobal(footer_viewport.mapToGlobal(visible_card.topLeft()))
            path = QPainterPath(QPointF(start))
            path.lineTo(start.x(), junction_y)
            path.lineTo(end.x() - 4, junction_y)
            path.lineTo(end.x() - 4, end.y() + 2)
            path.lineTo(end.x() + round(8 * card.height() / 72), end.y() + 2)
            painter.drawPath(path)
