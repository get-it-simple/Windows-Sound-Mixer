import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest

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
    SNAP_DISTANCE_PX,
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


def test_mini_widget_does_not_refresh_audio_sessions(qapp, settings):
    class TrackingAudioBackend(FakeAudioBackend):
        def __init__(self):
            super().__init__()
            self.refresh_count = 0

        def refresh(self):
            self.refresh_count += 1

    backend = TrackingAudioBackend()
    model = MixerModel(backend, settings)
    widget = MiniWidget(model, settings)

    initial_refresh_count = backend.refresh_count
    widget.set_enabled(True)
    qapp.processEvents()

    assert backend.refresh_count == initial_refresh_count
    assert widget.is_enabled() is True
    assert not widget.isVisible()

    backend.add_session(FakeAudioSession(pid=1, process_name="aurora.exe", display_name="Aurora"))
    model.refresh()
    widget.refresh_view()
    qapp.processEvents()

    assert backend.refresh_count == initial_refresh_count + 1
    assert widget.isVisible()
    widget.stop()
    widget.close()


def test_enabled_empty_widget_hides_and_reappears_after_model_update(qapp, settings):
    backend = FakeAudioBackend()
    model = MixerModel(backend, settings)
    widget = MiniWidget(model, settings)

    widget.set_enabled(True)
    qapp.processEvents()
    assert widget.is_enabled() is True
    assert not widget.isVisible()

    backend.add_session(FakeAudioSession(pid=1, process_name="aurora.exe", display_name="Aurora"))
    model.refresh()
    widget.refresh_view()
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


@pytest.mark.parametrize("transparency, alpha", [(0, 255), (0.5, 128), (1, 0)])
def test_background_transparency_keeps_content_visible(mini, settings, transparency, alpha):
    settings.set_mini_widget_background_transparency(transparency)
    mini.sync_from_settings()
    mini.apply_scale()
    entry = mini._entries["aurora.exe"]
    assert f"background: rgba(0, 0, 0, {alpha})" in entry.styleSheet()
    assert entry._icon_effect.opacity() == 1
    assert entry._volume_label.isVisible()
    assert mini.windowOpacity() == 1


def test_optional_master_is_first_and_controls_system_volume(qapp, mini, settings, fake_backend):
    settings.set_mini_widget_show_master(True)
    mini.sync_from_settings()
    master = mini._grid.itemAtPosition(0, 0).widget()
    assert master.key == "master"
    assert master._icon_label.pixmap().cacheKey() == load_icon("volume").pixmap(
        BASE_APP_ICON_PX, BASE_APP_ICON_PX
    ).cacheKey()

    master.wheelEvent(wheel_event(-1))
    master.mute_toggled.emit()
    qapp.processEvents()
    assert fake_backend.get_master_volume() == pytest.approx(0.48)
    assert fake_backend.get_master_mute() is True
    assert master._volume_label.text() == "48%"
    assert master._muted_icon_label.isVisible()
    assert mini._entries["aurora.exe"]._volume_label.text() == "100%"

    settings.set_mini_widget_show_master(False)
    mini.sync_from_settings()
    assert mini._grid.itemAtPosition(0, 0).widget().key == "aurora.exe"
    assert "master" not in mini._entries


def test_master_can_be_shown_without_app_sessions(qapp, settings):
    settings.set_mini_widget_show_master(True)
    mini = MiniWidget(MixerModel(FakeAudioBackend(), settings), settings)
    mini.set_enabled(True)
    assert mini.isVisible()
    assert list(mini._entries) == ["master"]
    mini.stop()
    mini.close()


@pytest.mark.parametrize("filter_enabled", [False, True])
def test_whitelist_reordering_updates_existing_widget_and_survives_scaling(mini, settings, filter_enabled):
    apps = []
    for name in ("lumen", "aurora"):
        path = settings.path.parent / f"{name}.exe"
        path.write_bytes(b"MZ")
        apps.append({"path": str(path), "enabled": True})
    settings.set_whitelist_apps(apps)
    settings.set_whitelist_enabled(filter_enabled)
    settings.set_mini_widget_show_master(True)
    mini._model.focus_key("aurora.exe")
    mini._model.refresh()
    mini.sync_from_settings()
    mini.apply_scale()

    assert [mini._grid.itemAtPosition(0, i).widget().key for i in range(3)] == [
        "master", "lumen.exe", "aurora.exe"
    ]
    assert mini._model.focused_entry.key == "aurora.exe"

    settings.set_whitelist_apps(list(reversed(apps)))
    settings.load()
    mini._model.refresh()
    mini.refresh_view()
    assert [mini._grid.itemAtPosition(0, i).widget().key for i in range(3)] == [
        "master", "aurora.exe", "lumen.exe"
    ]


@pytest.mark.parametrize("margins", [(0, 0, 0, 80), (0, 80, 0, 0), (80, 0, 0, 0), (0, 0, 80, 0)])
def test_taskbar_option_uses_full_screen_and_restores_work_area(mini, settings, monkeypatch, margins):
    from types import SimpleNamespace
    from PySide6.QtCore import QRect

    full = QRect(-1000, 0, 1000, 800)
    left, top, right, bottom = margins
    work = full.adjusted(left, top, -right, -bottom)
    screen = SimpleNamespace(geometry=lambda: full, availableGeometry=lambda: work)
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.QGuiApplication", SimpleNamespace(
        screens=lambda: [screen], screenAt=lambda point: screen if full.contains(point) else None,
        primaryScreen=lambda: screen,
    ))
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.raise_without_activating", lambda window: None)
    settings.set_mini_widget_show_above_taskbar(True)
    mini.sync_from_settings()
    mini.move(
        full.left() if left else full.right() - mini.width() + 1,
        full.top() if top else full.bottom() - mini.height() + 1,
    )
    position = mini.pos()
    mini.sync_from_settings()

    assert mini.pos() == position
    assert full.contains(mini.frameGeometry())
    assert not work.contains(mini.frameGeometry())
    mini._save_position()
    settings.load()
    mini.refresh_view()
    assert mini.pos() == position

    settings.set_mini_widget_show_above_taskbar(False)
    mini.sync_from_settings()
    assert work.contains(mini.frameGeometry())


def test_taskbar_stacking_runs_only_when_enabled_and_visible(mini, settings, monkeypatch):
    calls = []
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.raise_without_activating", calls.append)
    mini.refresh_view()
    assert calls == []
    assert not mini._taskbar_timer.isActive()

    settings.set_mini_widget_show_above_taskbar(True)
    mini.sync_from_settings()
    assert calls == [mini]
    assert mini._taskbar_timer.isActive()
    mini._taskbar_timer.timeout.emit()
    assert calls == [mini, mini]

    mini.set_enabled(False)
    assert not mini._taskbar_timer.isActive()
    mini._taskbar_timer.timeout.emit()
    assert len(calls) == 2
    mini.set_enabled(True)
    assert mini._taskbar_timer.isActive()

    settings.set_mini_widget_show_above_taskbar(False)
    mini.sync_from_settings()
    assert not mini._taskbar_timer.isActive()
    count = len(calls)
    mini._taskbar_timer.timeout.emit()
    assert len(calls) == count
    settings.set_mini_widget_show_above_taskbar(True)
    mini.sync_from_settings()
    mini.stop()
    assert not mini._taskbar_timer.isActive()


def test_empty_mini_widget_does_not_keep_taskbar_timer_running(qapp, settings):
    backend = FakeAudioBackend()
    settings.set_mini_widget_show_above_taskbar(True)
    settings.set_mini_widget_show_master(True)
    mini = MiniWidget(MixerModel(backend, settings), settings)
    mini.set_enabled(True)
    assert mini._taskbar_timer.isActive()
    settings.set_mini_widget_show_master(False)
    mini.sync_from_settings()
    assert not mini.isVisible()
    assert not mini._taskbar_timer.isActive()
    mini.stop()
    mini.close()


@pytest.fixture
def dock_screen(monkeypatch):
    from types import SimpleNamespace

    work = QRect(-1200, 100, 1200, 800)
    full = work.adjusted(0, 0, 0, 40)
    screen = SimpleNamespace(geometry=lambda: full, availableGeometry=lambda: work)
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.QGuiApplication", SimpleNamespace(
        screens=lambda: [screen], screenAt=lambda point: screen if full.contains(point) else None,
        primaryScreen=lambda: screen,
    ))
    return screen


def drag_to(widget, position):
    press = widget.pos() + QPoint(widget.width() // 2, widget._pin_row.y() + 4)
    release = press + position - widget.pos()
    widget._pin_button.mousePressEvent(mouse_event(
        QEvent.Type.MouseButtonPress, press.x(), press.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
    ))
    widget._pin_button.mouseMoveEvent(mouse_event(
        QEvent.Type.MouseMove, release.x(), release.y(),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
    ))
    widget._pin_button.mouseReleaseEvent(mouse_event(
        QEvent.Type.MouseButtonRelease, release.x(), release.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
    ))


@pytest.mark.parametrize("edge", ["left", "right", "top", "bottom"])
@pytest.mark.parametrize("initial_edge", ["", "left", "right"])
def test_dock_layout_and_pin_update_before_mouse_release(qapp, mini, dock_screen, edge, initial_edge):
    work = dock_screen.availableGeometry()
    if initial_edge:
        x = work.left() + 5 if initial_edge == "left" else work.right() - mini.width() - 4
        drag_to(mini, QPoint(x, 300))
    else:
        mini.move(work.center())
    mini._pin_button.show()
    qapp.processEvents()
    press = mini._pin_button.mapToGlobal(mini._pin_button.rect().center())
    offset = press - mini.pos()
    size = mini.size()
    mini._pin_button.mousePressEvent(mouse_event(
        QEvent.Type.MouseButtonPress, press.x(), press.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
    ))
    position = work.center()
    gap = SNAP_DISTANCE_PX - 1
    if edge == "left":
        position.setX(work.left() + gap)
    elif edge == "right":
        position.setX(work.right() - size.width() + 1 - gap)
    elif edge == "top":
        position.setY(work.top() + gap)
    else:
        position.setY(work.bottom() - size.height() + 1 - gap)
    cursor = position + offset
    for delta in (QPoint(), QPoint(1, 1), QPoint()):
        point = cursor + delta
        mini._pin_button.mouseMoveEvent(mouse_event(
            QEvent.Type.MouseMove, point.x(), point.y(),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        ))
        qapp.processEvents()

        assert mini._pin_button.is_dragging()
        assert getattr(mini.frameGeometry(), edge)() == getattr(work, edge)()
        assert mini._entries["aurora.exe"]._slider.isVisible() == (edge in ("left", "right"))
        pin = QRect(mini._pin_button.mapTo(mini, QPoint()), mini._pin_button.size())
        content = mini._content.geometry()
        if edge == "left":
            assert pin.left() > content.right()
        elif edge == "right":
            assert pin.right() < content.left()
        elif edge == "top":
            assert pin.top() > content.bottom()
        else:
            assert pin.bottom() < content.top()
        assert mini.rect().contains(pin)
        assert work.contains(mini.frameGeometry())

    cursor = work.center() + offset
    mini._pin_button.mouseMoveEvent(mouse_event(
        QEvent.Type.MouseMove, cursor.x(), cursor.y(),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
    ))
    qapp.processEvents()
    assert mini._pin_button.is_dragging()
    assert mini._entries["aurora.exe"]._volume_label.isVisible()
    assert mini._grid.itemAtPosition(0, 1).widget().key == "lumen.exe"
    mini._pin_button.mouseReleaseEvent(mouse_event(
        QEvent.Type.MouseButtonRelease, cursor.x(), cursor.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
    ))


@pytest.mark.parametrize("edge", ["left", "right"])
@pytest.mark.parametrize("scale", [0.5, 1.0, 3.0])
def test_side_pin_faces_screen_interior_after_docking_and_scaling(qapp, mini, settings, dock_screen, edge, scale):
    work = dock_screen.availableGeometry()
    x = work.left() + 5 if edge == "left" else work.right() - mini.width() - 4
    drag_to(mini, QPoint(x, 300))
    settings.set_mini_widget_scale(scale)
    mini.apply_scale()
    mini._pin_button.show()
    qapp.processEvents()

    pin = QRect(mini._pin_button.mapTo(mini, QPoint()), mini._pin_button.size())
    content = mini._content.geometry()
    if edge == "left":
        assert pin.left() > content.right()
    else:
        assert pin.right() < content.left()
    assert abs(pin.center().y() - content.center().y()) <= 1
    assert mini.rect().contains(pin)
    assert work.contains(mini.frameGeometry())


@pytest.mark.parametrize("edge", ["left", "right", "top", "bottom"])
def test_drag_snaps_to_each_edge_and_restores_after_restart(qapp, mini, settings, dock_screen, edge):
    work = dock_screen.availableGeometry()
    x, y = work.center().x(), work.center().y()
    gap = SNAP_DISTANCE_PX - 1
    if edge == "left":
        x = work.left() + gap
    elif edge == "right":
        x = work.right() - mini.width() + 1 - gap
    elif edge == "top":
        y = work.top() + gap
    else:
        y = work.bottom() - mini.height() + 1 - gap

    drag_to(mini, QPoint(x, y))
    qapp.processEvents()

    assert getattr(mini.frameGeometry(), edge)() == getattr(work, edge)()
    vertical = edge in ("left", "right")
    entries = list(mini._entries.values())
    assert mini._grid.itemAtPosition(1 if vertical else 0, 0 if vertical else 1).widget() is entries[1]
    assert entries[0]._slider.isVisible() == vertical
    assert entries[0]._volume_label.isVisible() != vertical
    assert work.contains(mini.frameGeometry())
    mini.stop()
    settings.load()
    assert settings.get_mini_widget_dock_edge() == edge
    restored = MiniWidget(mini._model, settings)
    try:
        restored.set_enabled(True)
        qapp.processEvents()
        assert restored.frameGeometry() == mini.frameGeometry()
        assert restored._entries[entries[0].key]._slider.isVisible() == vertical
    finally:
        restored.stop()
        restored.close()


def test_dragging_away_restores_percentages_and_horizontal_order(qapp, mini, settings, dock_screen):
    work = dock_screen.availableGeometry()
    drag_to(mini, QPoint(work.left() + 5, work.center().y()))
    mini._on_scrolled("lumen.exe", -1)

    drag_to(mini, work.center())
    qapp.processEvents()
    mini._save_position()
    settings.load()

    assert settings.get_mini_widget_dock_edge() == ""
    assert mini.pos() == work.center()
    assert mini._grid.itemAtPosition(0, 1).widget().key == "lumen.exe"
    assert mini._entries["lumen.exe"]._volume_label.isVisible()
    assert mini._entries["lumen.exe"]._volume_label.text() == "98%"
    assert mini._entries["lumen.exe"]._slider.isHidden()


def test_drag_outside_snap_distance_stays_free(mini, dock_screen, settings):
    work = dock_screen.availableGeometry()
    position = QPoint(work.left() + SNAP_DISTANCE_PX + 1, work.center().y())
    drag_to(mini, position)
    mini._save_position()
    assert mini.pos() == position
    assert settings.get_mini_widget_dock_edge() == ""
    assert mini._entries["aurora.exe"]._volume_label.isVisible()


@pytest.mark.parametrize("edge", ["left", "right", "top", "bottom"])
def test_docking_survives_scale_and_session_changes(qapp, mini, settings, fake_backend, dock_screen, edge):
    work = dock_screen.availableGeometry()
    position = QPoint(work.left() + 1 if edge == "left" else work.right() - mini.width(), work.center().y())
    if edge in ("top", "bottom"):
        position = QPoint(work.center().x(), work.top() + 1 if edge == "top" else work.bottom() - mini.height())
    drag_to(mini, position)
    settings.set_mini_widget_scale(2)
    mini.apply_scale()
    fake_backend.add_session(FakeAudioSession(pid=300, process_name="third.exe", display_name="Third"))
    mini._model.refresh()
    mini.refresh_view()
    qapp.processEvents()

    assert getattr(mini.frameGeometry(), edge)() == getattr(work, edge)()
    assert work.contains(mini.frameGeometry())
    assert len(mini._entries) == 3
    entry = mini._entries["third.exe"]
    assert entry._icon_label.width() == BASE_APP_ICON_PX * 2
    assert entry._slider.isVisible() == (edge in ("left", "right"))


@pytest.mark.parametrize("edge", ["left", "right"])
@pytest.mark.parametrize("scale", [0.5, 1.0, 1.5, 3.0])
def test_side_dock_slider_is_vertical_and_fits_tile_height(qapp, mini, settings, dock_screen, edge, scale):
    work = dock_screen.availableGeometry()
    x = work.left() + 5 if edge == "left" else work.right() - mini.width() - 4
    drag_to(mini, QPoint(x, 300))
    settings.set_mini_widget_scale(scale)
    mini.apply_scale()
    qapp.processEvents()

    entry = mini._entries["lumen.exe"]
    slider = entry._slider
    margins = entry.layout().contentsMargins()
    assert slider.isVisible()
    assert slider.orientation() == Qt.Orientation.Vertical
    assert slider.height() == entry.height() - margins.top() - margins.bottom()
    assert slider.height() == entry._icon_container.height()
    assert slider.width() < slider.height() / 3
    assert slider.geometry().top() == entry._icon_container.geometry().top()
    assert slider.geometry().left() > entry._icon_container.geometry().right()
    assert entry.rect().contains(slider.geometry())
    assert getattr(mini.frameGeometry(), edge)() == getattr(work, edge)()


@pytest.mark.parametrize("scale", [0.5, 1.0, 1.5, 3.0])
def test_mini_indicator_renders_volume_without_a_handle(qapp, mini, settings, dock_screen, monkeypatch, scale):
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.get_accent_color", lambda: "#3a96dd")
    drag_to(mini, QPoint(dock_screen.availableGeometry().left() + 5, 300))
    settings.set_mini_widget_scale(scale)
    mini.apply_scale()
    mini._model.focus_key("lumen.exe")
    fills = []
    for volume in (0.0, 0.5, 1.0):
        mini._model.set_volume(volume)
        mini.refresh_view()
        qapp.processEvents()
        rendered = mini._entries["lumen.exe"]._slider.grab().toImage()
        pixels = [rendered.pixelColor(x, y).name()
                  for x in range(rendered.width()) for y in range(rendered.height())]
        assert "#ffffff" not in pixels
        column = [rendered.pixelColor(rendered.width() // 2, y).name() for y in range(rendered.height())]
        fills.append(column.count("#3a96dd"))
        if volume == 0.5:
            assert column[rendered.height() // 4] == "#555555"
            assert column[3 * rendered.height() // 4] == "#3a96dd"
    assert fills[0] == 0
    assert 0 < fills[1] < fills[2]
    assert fills[1] == pytest.approx(fills[2] / 2, abs=2)


def test_vertical_indicator_preserves_click_wheel_and_model_sync(qapp, mini, dock_screen, fake_backend):
    drag_to(mini, QPoint(dock_screen.availableGeometry().left() + 5, 300))
    qapp.processEvents()
    entry = mini._entries["lumen.exe"]
    slider = entry._slider
    assert slider.isVisible()
    assert not slider.isEnabled()
    assert slider.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert slider.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    point = slider.geometry().center()
    assert entry.childAt(point) is None
    QTest.mouseClick(entry, Qt.MouseButton.LeftButton, pos=point)
    assert mini._model.focused_entry.key == "lumen.exe"
    assert mini._model.focused_entry.muted
    assert slider.value() == 100
    assert entry._muted_icon_label.isVisible()
    qapp.sendEvent(entry, wheel_event(-1))
    assert mini._model.focused_entry.volume == pytest.approx(0.98)
    assert slider.value() == 98
    assert mini._entries["aurora.exe"]._slider.value() == 100
    assert fake_backend.get_master_volume() == 0.5
    mini._model.set_volume(0.37)
    mini.refresh_view()
    assert slider.value() == 37
    assert mini.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus


def test_vertical_list_wraps_top_to_bottom_without_losing_apps(qapp, mini, fake_backend, dock_screen):
    for index in range(20):
        fake_backend.add_session(FakeAudioSession(
            pid=1000 + index, process_name=f"extra{index}.exe", display_name=f"Extra {index}",
        ))
    mini._model.refresh()
    mini.refresh_view()
    drag_to(mini, QPoint(dock_screen.availableGeometry().left() + 5, 300))
    qapp.processEvents()

    assert len(mini._entries) == 22
    assert dock_screen.availableGeometry().contains(mini.frameGeometry())
    positions = [mini._grid.getItemPosition(i)[:2] for i in range(mini._grid.count())]
    assert max(column for row, column in positions) > 0
    ordered = sorted(positions, key=lambda position: (position[1], position[0]))
    assert [mini._grid.itemAtPosition(*position).widget().key for position in ordered] == list(mini._entries)


def test_bottom_dock_follows_taskbar_option(mini, settings, dock_screen, monkeypatch):
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.raise_without_activating", lambda window: None)
    work = dock_screen.availableGeometry()
    drag_to(mini, QPoint(work.center().x(), work.bottom() - mini.height() - 4))
    assert mini.frameGeometry().bottom() == work.bottom()

    settings.set_mini_widget_show_above_taskbar(True)
    mini.sync_from_settings()
    assert mini.frameGeometry().bottom() == dock_screen.geometry().bottom()
    settings.set_mini_widget_show_above_taskbar(False)
    mini.sync_from_settings()
    assert mini.frameGeometry().bottom() == work.bottom()


def test_docks_to_secondary_monitor_then_recovers_when_it_is_removed(mini, settings, monkeypatch):
    from types import SimpleNamespace

    primary_rect = QRect(0, 0, 1200, 800)
    secondary_rect = QRect(-1200, -100, 1200, 800)
    primary = SimpleNamespace(geometry=lambda: primary_rect, availableGeometry=lambda: primary_rect)
    secondary = SimpleNamespace(geometry=lambda: secondary_rect, availableGeometry=lambda: secondary_rect)
    screens = [primary, secondary]
    monkeypatch.setattr("sound_mixer.overlay.mini_widget.QGuiApplication", SimpleNamespace(
        screens=lambda: screens,
        screenAt=lambda point: next((screen for screen in screens if screen.geometry().contains(point)), None),
        primaryScreen=lambda: primary,
    ))
    drag_to(mini, QPoint(secondary_rect.right() - mini.width() - 4, 200))
    assert mini.frameGeometry().right() == secondary_rect.right()
    assert secondary_rect.contains(mini.frameGeometry())
    screens.remove(secondary)
    mini.refresh_view()
    assert primary_rect.contains(mini.frameGeometry())
    assert mini.frameGeometry().right() == primary_rect.right()
