import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent, QWheelEvent

from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.icons import load_icon
from sound_mixer.overlay.mini_widget import (
    BASE_APP_ICON_PX,
    BASE_ENTRY_RADIUS_PX,
    BASE_FONT_PX,
    BASE_SPACING_PX,
    MUTED_ICON_SCALE,
    MUTED_OPACITY,
    MiniWidget,
)
from sound_mixer.overlay.window import OverlayWindow


def wheel_event(direction: int) -> QWheelEvent:
    return QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, 120 * direction),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def mouse_event(event_type, global_x: float, global_y: float, button, buttons) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        QPointF(0, 0),
        QPointF(global_x, global_y),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def mini(qapp, fake_backend, settings):
    widget = MiniWidget(MixerModel(fake_backend, settings), settings)
    widget.set_enabled(True)
    qapp.processEvents()
    yield widget
    widget.stop()
    widget.close()


def test_mini_widget_is_transparent_and_excludes_master(mini):
    assert mini.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert "background: transparent" in mini.styleSheet()
    assert "rgba(0, 0, 0, 51)" not in mini._content.styleSheet()
    assert "rgba(0, 0, 0, 51)" not in mini._pin_row.styleSheet()
    assert list(mini._entries) == ["aurora.exe", "lumen.exe"]

    for entry in mini._entries.values():
        assert "background: rgba(0, 0, 0, 51)" in entry.styleSheet()
        assert f"border-radius: {BASE_ENTRY_RADIUS_PX}px" in entry.styleSheet()
    assert mini._grid.horizontalSpacing() == BASE_SPACING_PX


def test_mini_entry_centers_percentage_and_icon(mini):
    entry = mini._entries["aurora.exe"]

    assert entry._volume_label.text() == "100%"
    assert entry._volume_label.alignment() == Qt.AlignmentFlag.AlignCenter
    assert entry._icon_label.alignment() == Qt.AlignmentFlag.AlignCenter
    assert entry._muted_icon_label.alignment() == Qt.AlignmentFlag.AlignCenter


def test_mini_widget_keeps_all_entries_and_wraps_to_rows(qapp, fake_backend, settings):
    for index in range(80):
        fake_backend.add_session(
            FakeAudioSession(
                pid=1000 + index,
                process_name=f"extra{index}.exe",
                display_name=f"Extra {index}",
            )
        )
    widget = MiniWidget(MixerModel(fake_backend, settings), settings)
    widget.set_enabled(True)
    qapp.processEvents()

    rows = [widget._grid.getItemPosition(index)[0] for index in range(widget._grid.count())]

    assert len(widget._entries) == 82
    assert max(rows) > 0
    widget.stop()
    widget.close()


def test_wheel_adjusts_matching_volume_and_focus(mini):
    entry = mini._entries["lumen.exe"]
    changed = []
    mini.model_changed.connect(lambda: changed.append(True))

    entry.wheelEvent(wheel_event(-1))

    assert mini._model.focused_entry.key == "lumen.exe"
    assert mini._model.focused_entry.volume == pytest.approx(0.98)
    assert entry._volume_label.text() == "98%"
    assert changed == [True]


def test_click_toggles_mute_and_dims_icon_without_changing_percentage(mini):
    entry = mini._entries["aurora.exe"]

    entry.mousePressEvent(
        mouse_event(
            QMouseEvent.Type.MouseButtonPress,
            0,
            0,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )

    assert mini._model.focused_entry.key == "aurora.exe"
    assert mini._model.focused_entry.muted is True
    assert entry._volume_label.text() == "100%"
    assert entry._icon_effect.opacity() == pytest.approx(MUTED_OPACITY)
    assert entry._muted_icon_label.isVisible()
    muted_icon_px = round(BASE_APP_ICON_PX * MUTED_ICON_SCALE)
    assert entry._muted_icon_label.pixmap().cacheKey() == load_icon("muted").pixmap(
        muted_icon_px, muted_icon_px
    ).cacheKey()
    assert entry._muted_icon_label.pixmap().size() == QSize(muted_icon_px, muted_icon_px)

    entry.mousePressEvent(
        mouse_event(
            QMouseEvent.Type.MouseButtonPress,
            0,
            0,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )

    assert mini._model.focused_entry.muted is False
    assert entry._volume_label.text() == "100%"
    assert entry._icon_effect.opacity() == pytest.approx(1.0)
    assert entry._muted_icon_label.isHidden()


def test_hover_shows_pin_and_drag_moves_and_saves_widget(mini, settings):
    mini.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(mini.x(), mini.y())))
    assert not mini._pin_button.isHidden()
    start = mini.pos()
    press_global = start + QPoint(4, 4)

    mini._pin_button.mousePressEvent(
        mouse_event(
            QMouseEvent.Type.MouseButtonPress,
            press_global.x(),
            press_global.y(),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )
    mini._pin_button.mouseMoveEvent(
        mouse_event(
            QMouseEvent.Type.MouseMove,
            press_global.x() + 20,
            press_global.y() + 15,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )
    mini._pin_button.mouseReleaseEvent(
        mouse_event(
            QMouseEvent.Type.MouseButtonRelease,
            press_global.x() + 20,
            press_global.y() + 15,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    mini._save_position()

    assert mini.pos() == start + QPoint(20, 15)
    assert settings.get_mini_widget_position() == {"x": mini.x(), "y": mini.y()}


def test_pin_hide_is_delayed_and_reenter_cancels_it(mini):
    enter = QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(mini.x(), mini.y()))
    mini.enterEvent(enter)

    mini.leaveEvent(QEvent(QEvent.Type.Leave))

    assert not mini._pin_button.isHidden()
    assert mini._pin_hide_timer.isActive()

    mini.enterEvent(enter)

    assert not mini._pin_button.isHidden()
    assert not mini._pin_hide_timer.isActive()


def test_pin_hide_timer_does_not_hide_during_drag(mini):
    mini._pin_button.show()
    mini._pin_button._drag_offset = QPoint(1, 1)

    mini._hide_pin_if_idle()

    assert not mini._pin_button.isHidden()
    mini._pin_button._drag_offset = None


def test_mini_widget_applies_its_own_scale(mini, settings):
    settings.set_ui_scale(2.0)
    settings.set_mini_widget_scale(1.5)

    mini.apply_scale()

    entry = mini._entries["aurora.exe"]
    assert entry._icon_label.width() == round(BASE_APP_ICON_PX * 1.5)
    assert entry._volume_label.font().pixelSize() == round(BASE_FONT_PX * 1.5)


def test_pin_moves_below_content_in_upper_half_and_above_in_lower_half(qapp, mini):
    available = qapp.primaryScreen().availableGeometry()

    mini.move(available.left() + 10, available.top() - mini.height())
    mini._ensure_on_screen()
    assert mini.y() == available.top()
    assert mini._outer_layout.indexOf(mini._pin_row) > mini._outer_layout.indexOf(mini._content)
    entry_layout = mini._entries["aurora.exe"].layout()
    assert entry_layout.itemAt(0).widget() is mini._entries["aurora.exe"]._icon_container
    assert entry_layout.itemAt(1).widget() is mini._entries["aurora.exe"]._volume_label

    mini.move(available.left() + 10, available.bottom() - mini.height())
    mini._update_pin_position()
    assert mini._outer_layout.indexOf(mini._pin_row) < mini._outer_layout.indexOf(mini._content)
    assert entry_layout.itemAt(0).widget() is mini._entries["aurora.exe"]._volume_label
    assert entry_layout.itemAt(1).widget() is mini._entries["aurora.exe"]._icon_container


def test_mini_widget_recovers_from_offscreen_position(qapp, mini):
    available = qapp.primaryScreen().availableGeometry()
    mini.move(available.right() + 1000, available.bottom() + 1000)

    mini._ensure_on_screen()

    assert available.contains(mini.frameGeometry().topLeft())


def test_enabled_empty_widget_hides_and_reappears_when_session_arrives(qapp, settings):
    backend = FakeAudioBackend()
    widget = MiniWidget(MixerModel(backend, settings), settings)

    widget.set_enabled(True)
    qapp.processEvents()
    assert widget.is_enabled() is True
    assert not widget.isVisible()
    assert widget._refresh_timer.isActive()

    backend.add_session(FakeAudioSession(pid=1, process_name="aurora.exe", display_name="Aurora"))
    widget._refresh()
    qapp.processEvents()

    assert widget.isVisible()
    widget.set_enabled(False)
    assert settings.get_mini_widget_enabled() is False
    assert not widget.isVisible()
    widget.stop()
    widget.close()


def test_main_overlay_and_mini_widget_synchronize_interactions(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    overlay.model_changed.connect(mini.refresh_view)
    mini.model_changed.connect(overlay.refresh_view)
    mini.set_enabled(True)

    overlay._on_volume_changed(overlay._entry_widgets[1], 0.44)
    assert mini._entries["aurora.exe"]._volume_label.text() == "44%"

    mini._on_scrolled("aurora.exe", -1)
    assert overlay._entry_widgets[1]._volume_spinbox.value() == 42

    overlay._on_mute_toggled(overlay._entry_widgets[1])
    assert mini._entries["aurora.exe"]._muted_icon_label.isVisible()

    mini.stop()
    mini.close()
    overlay.close()
