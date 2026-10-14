from PySide6.QtCore import Property, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QMenu, QSizePolicy

from sound_mixer.i18n import t
from sound_mixer.overlay.icons import DelayedTooltipButton, load_icon
from sound_mixer.overlay.marquee import MarqueeLabel


class DeviceButton(DelayedTooltipButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._compact = True
        self._scale = 1.0
        self._devices = []
        self._current_id = ""
        self._pending_id = None
        self._progress = 0.0
        self._busy_animation = QPropertyAnimation(self, b"busyProgress", self)
        self._busy_animation.setStartValue(0.0)
        self._busy_animation.setEndValue(1.0)
        self._busy_animation.setDuration(1000)
        self._busy_animation.setLoopCount(-1)
        self._label = MarqueeLabel(parent=self)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        palette = self._label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, "#f2f2f5")
        self._label.setPalette(palette)
        self._label.hide()
        self.menu = QMenu(self)
        self.menu.setToolTipsVisible(True)
        self.clicked.connect(self._show_menu)
        self.set_devices([], "")

    def set_devices(self, devices, current_id: str) -> None:
        self._devices = list(devices)
        self._current_id = current_id
        if self._pending_id is not None and (
            current_id == self._pending_id or self._pending_id not in {device.id for device in self._devices}
        ):
            self.finish_selection()
        self.retranslate()

    @Property(float)
    def busyProgress(self) -> float:
        return self._progress

    @busyProgress.setter
    def busyProgress(self, value: float) -> None:
        self._progress = value
        self.update()

    def begin_selection(self, device_id: str) -> bool:
        if self._pending_id is not None or device_id == self._current_id:
            return False
        if device_id not in {device.id for device in self._devices}:
            return False
        self._pending_id = device_id
        self.menu.hide()
        self.menu.setEnabled(False)
        self.setEnabled(False)
        self._label.hide()
        if self.isVisible():
            self._busy_animation.start()
        self.retranslate()
        return True

    def finish_selection(self) -> None:
        self._pending_id = None
        self._busy_animation.stop()
        self.menu.setEnabled(True)
        self.setEnabled(True)
        self._label.setVisible(not self._compact)
        self.retranslate()

    def retranslate(self) -> None:
        current = next((device.name for device in self._devices if device.id == self._current_id), "")
        self._label.setText(current or t("output_device_select"))
        self.setAccessibleName(t("output_device_select"))
        self.setToolTip(f"{t('output_device_select')}\n{current}" if current else t("output_device_select"))
        if self._pending_id is not None:
            target = next((device.name for device in self._devices if device.id == self._pending_id), "")
            self.setAccessibleName(t("output_device_switching"))
            self.setToolTip(f"{t('output_device_switching')}\n{target}")
        actions = {action.data(): action for action in self.menu.actions()}
        device_ids = {device.id for device in self._devices} or {None}
        for device_id, action in list(actions.items()):
            if device_id not in device_ids:
                self.menu.removeAction(action)
                action.deleteLater()
                del actions[device_id]
        if not self._devices:
            empty = actions.get(None) or self.menu.addAction("")
            empty.setText(t("output_device_empty"))
            empty.setEnabled(False)
        for device in self._devices:
            action = actions.get(device.id) or self.menu.addAction("")
            action.setText(device.name.replace("&", "&&"))
            action.setData(device.id)
            action.setToolTip(device.name)
            action.setCheckable(True)
            action.setChecked(device.id == self._current_id)
        self._update_size()

    def apply_scale(self, scale: float) -> None:
        self._scale = scale
        self.setIconSize(QSize(round(16 * scale), round(16 * scale)))
        self._label.setFont(self.font())
        self._update_size()

    def expanded_width(self) -> int:
        text = self._label.text()
        preview = text if len(text) <= 16 else text[:15] + "…"
        return max(round(40 * self._scale), self._label.fontMetrics().horizontalAdvance(preview) + round(26 * self._scale))

    def set_compact(self, compact: bool) -> None:
        if self._compact != compact:
            self._compact = compact
            self._label.setVisible(not compact and self._pending_id is None)
            self._update_size()

    def _update_size(self) -> None:
        self.setMinimumWidth(round(40 * self._scale))
        self.setMaximumWidth(self.sizeHint().width())
        self._position_label()
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        width = round(40 * self._scale) if self._compact else self.expanded_width()
        return QSize(width, max(round(28 * self._scale), self.fontMetrics().height() + round(12 * self._scale)))

    def minimumSizeHint(self) -> QSize:
        return QSize(round(40 * self._scale), self.sizeHint().height())

    def _position_label(self) -> None:
        padding = round(6 * self._scale)
        self._label.setGeometry(padding, 0, max(0, self.width() - round(26 * self._scale)), self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_label()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        if self._pending_id is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            padding = round(6 * self._scale)
            height = max(3, round(3 * self._scale))
            track = QRectF(padding, (self.height() - height) / 2, self.width() - 2 * padding, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 45))
            painter.drawRoundedRect(track, height / 2, height / 2)
            painter.setClipRect(track)
            segment = max(6 * self._scale, track.width() / 3)
            x = track.left() - segment + self._progress * (track.width() + segment)
            painter.setBrush(QColor("#f2f2f5"))
            painter.drawRoundedRect(QRectF(x, track.top(), segment, height), height / 2, height / 2)
            return
        icon = self.iconSize().width()
        if self._compact:
            load_icon("device").paint(painter, round(6 * self._scale), (self.height() - icon) // 2, icon, icon)
        arrow = round(8 * self._scale)
        load_icon("dropdown_arrow").paint(
            painter, self.width() - round(6 * self._scale) - arrow, (self.height() - arrow) // 2, arrow, arrow
        )

    def enterEvent(self, event) -> None:
        self._label.start_marquee()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._label.stop_marquee()
        super().leaveEvent(event)

    def _show_menu(self) -> None:
        if self._pending_id is None:
            self.menu.popup(self.mapToGlobal(self.rect().bottomLeft()))

    def hideEvent(self, event) -> None:
        self._busy_animation.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._pending_id is not None:
            self._busy_animation.start()
