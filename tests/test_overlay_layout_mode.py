import sys

import pytest
from PySide6.QtCore import QDeadlineTimer, QEventLoop, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QBoxLayout, QFrame

from sound_mixer import __version__
from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.icons import TOGGLE_SWITCH_HEIGHT_PX, TOGGLE_SWITCH_WIDTH_PX
from sound_mixer.overlay.window import (
    BACKGROUND_BORDER_PX,
    MAX_VISIBLE_ENTRIES,
    OverlayWindow,
)


def make_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    model = MixerModel(fake_backend, settings)
    return OverlayWindow(model, settings)


def key_event(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def make_managed_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    settings.set_layout_mode("vertical")
    manager = SubprocessManager(settings, on_tick=lambda: None)
    return OverlayWindow(MixerModel(fake_backend, settings), settings, subprocess_manager=manager)


def test_overlay_starts_in_persisted_layout_mode(qapp, fake_backend, settings):
    settings.set_layout_mode("vertical")

    overlay = make_overlay(qapp, fake_backend, settings)

    assert overlay.layout_mode() == "vertical"
    assert overlay._container_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert overlay._active_layout.direction() == QBoxLayout.Direction.LeftToRight


def test_switching_to_vertical_flips_layout_and_sliders(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    assert settings.get_layout_mode() == "vertical"
    assert overlay._container_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert overlay._divider.frameShape() == QFrame.Shape.VLine
    for widget in overlay._entry_widgets:
        assert widget._slider.orientation() == Qt.Orientation.Vertical


def test_switching_back_to_horizontal_restores_layout(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")
    overlay.set_layout_mode("horizontal")

    assert overlay._container_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert overlay._divider.frameShape() == QFrame.Shape.HLine
    for widget in overlay._entry_widgets:
        assert widget._slider.orientation() == Qt.Orientation.Horizontal


def test_vertical_mode_fixes_width_and_frees_height(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    assert overlay.minimumWidth() == overlay.maximumWidth()
    assert overlay.maximumHeight() > overlay.minimumHeight()
    assert overlay.minimumHeight() == max(
        overlay._title_bar.sizeHint().height() + 2 * BACKGROUND_BORDER_PX,
        max(widget.minimumSizeHint().height() for widget in overlay._entry_widgets)
        + overlay._container_layout.contentsMargins().top()
        + overlay._container_layout.contentsMargins().bottom()
        + 2 * BACKGROUND_BORDER_PX,
    )


def test_vertical_window_width_grows_with_entry_count(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    initial_width = overlay.width()
    initial_count = len(overlay._entry_widgets)

    for i in range(MAX_VISIBLE_ENTRIES - initial_count):
        fake_backend.add_session(
            FakeAudioSession(pid=300 + i, process_name=f"nimbus{i}.exe", display_name=f"Nimbus {i}", volume=1.0)
        )
    overlay._model.refresh()
    overlay.refresh_view()

    assert len(overlay._entry_widgets) == MAX_VISIBLE_ENTRIES
    assert overlay.width() > initial_width


def test_vertical_mode_turns_the_title_bar_into_a_side_column(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    assert overlay._background_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert overlay._title_bar.layout().direction() == QBoxLayout.Direction.TopToBottom
    assert overlay._title_name_label.isHidden()
    assert overlay._title_version_label.isHidden()
    assert not overlay._title_icon_label.isHidden()
    assert overlay._title_icon_label.toolTip() == f"Sound Mixer\nv{__version__}"


def test_switching_back_to_horizontal_restores_the_title_bar(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")
    overlay.set_layout_mode("horizontal")

    assert overlay._background_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert overlay._title_bar.layout().direction() == QBoxLayout.Direction.LeftToRight
    assert not overlay._title_name_label.isHidden()
    assert not overlay._title_version_label.isHidden()


def test_retranslate_updates_the_title_icon_tooltip(qapp, fake_backend, settings, monkeypatch):
    import sound_mixer.overlay.window as window_module

    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")

    monkeypatch.setattr(window_module, "t", lambda key: "Локалізований мікшер" if key == "sound_mixer_title" else key)
    overlay.retranslate()

    assert overlay._title_icon_label.toolTip() == f"Локалізований мікшер\nv{__version__}"


def test_vertical_minimum_height_fits_the_whole_title_column(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    title_column = overlay._title_bar.sizeHint().height() + 2 * BACKGROUND_BORDER_PX
    assert overlay.minimumHeight() >= title_column


def test_minimum_height_fits_the_visible_subprocess_toggle(qapp, fake_backend, settings):
    overlay = make_managed_overlay(qapp, fake_backend, settings)

    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    overlay.sync_subprocess_management_toggle()

    assert overlay._subprocess_management_toggle.isVisible()
    assert overlay.minimumHeight() >= overlay._title_bar.sizeHint().height() + 2 * BACKGROUND_BORDER_PX


def test_vertical_title_column_centers_the_subprocess_toggle(qapp, fake_backend, settings):
    settings.set_managed_apps([{"path": sys.executable, "enabled": True}])

    overlay = make_managed_overlay(qapp, fake_backend, settings)

    toggle = overlay._subprocess_management_toggle
    assert toggle.width() == TOGGLE_SWITCH_WIDTH_PX
    assert toggle.height() == TOGGLE_SWITCH_HEIGHT_PX
    geometry = toggle.geometry()
    assert abs(geometry.x() + geometry.width() / 2 - overlay._title_bar.width() / 2) <= 1


def test_vertical_title_column_centers_its_controls(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")
    overlay.resize(overlay.width(), 600)

    center = overlay._title_bar.width() / 2
    for widget in (
        overlay._title_icon_label,
        overlay._settings_button,
        overlay._guide_button,
        overlay._close_button,
    ):
        geometry = widget.geometry()
        assert abs(geometry.x() + geometry.width() / 2 - center) <= 1


def test_vertical_title_column_is_narrower_than_the_horizontal_title_bar(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    horizontal_width = overlay._title_bar.sizeHint().width()

    overlay.set_layout_mode("vertical")

    assert overlay._title_bar.sizeHint().width() < horizontal_width


def test_vertical_window_width_is_the_title_column_plus_the_entries(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    margins = overlay._container_layout.contentsMargins()
    spacing = overlay._container_layout.spacing()
    count = len(overlay._entry_widgets)
    entries_width = count * overlay._entry_widgets[0].sizeHint().width() + (count - 1) * spacing
    container_width = margins.left() + margins.right() + entries_width

    expected = overlay._title_bar.sizeHint().width() + container_width + 2 * BACKGROUND_BORDER_PX
    assert overlay.width() == expected


def test_vertical_window_width_caps_after_max_visible_entries(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")

    for i in range(MAX_VISIBLE_ENTRIES + 4):
        fake_backend.add_session(
            FakeAudioSession(pid=1000 + i, process_name=f"app{i}.exe", display_name=f"App {i}", volume=1.0)
        )
    overlay._model.refresh()
    overlay.refresh_view()
    width_at_cap = overlay.width()

    fake_backend.add_session(FakeAudioSession(pid=2000, process_name="extra.exe", display_name="Extra", volume=1.0))
    overlay._model.refresh()
    overlay.refresh_view()

    assert overlay.width() == width_at_cap


def test_vertical_resize_handle_changes_height(qapp, fake_backend, settings):
    from tests.test_overlay_resize import move_event

    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    overlay.resize(overlay.width(), overlay.minimumHeight() + 100)

    handle = overlay._resize_handle
    handle._drag_start_pos = 100
    handle._start_size = overlay.height()

    handle.mouseMoveEvent(move_event(global_y=160))

    assert overlay.height() == overlay.minimumHeight() + 160


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_vertical_minimum_height_fits_the_entry_minimum(qapp, fake_backend, settings, scale):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    settings.set_ui_scale(scale)
    overlay.apply_scale()

    margins = overlay._container_layout.contentsMargins()
    entry_min = max(widget.minimumSizeHint().height() for widget in overlay._entry_widgets)

    assert overlay.minimumHeight() >= entry_min + margins.top() + margins.bottom()


def test_vertical_resize_handle_stops_at_the_entry_minimum_height(qapp, fake_backend, settings):
    from tests.test_overlay_resize import move_event

    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    overlay.resize(overlay.width(), overlay.minimumHeight() + 200)

    handle = overlay._resize_handle
    handle._drag_start_pos = 500
    handle._start_size = overlay.height()

    handle.mouseMoveEvent(move_event(global_y=0))

    entry_min = max(widget.minimumSizeHint().height() for widget in overlay._entry_widgets)
    assert overlay.height() == overlay.minimumHeight()
    assert overlay.height() >= entry_min


def test_vertical_resize_handle_starts_after_the_title_column(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    handle = overlay._resize_handle
    assert handle.x() == overlay._title_bar.width()
    assert handle.x() + handle.width() == overlay.width()


def test_each_layout_mode_keeps_its_own_geometry(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.resize(400, overlay.height())
    overlay.set_layout_mode("vertical")
    overlay.resize(overlay.width(), 500)
    overlay.set_layout_mode("horizontal")

    assert overlay.width() == 400

    overlay.set_layout_mode("vertical")

    assert overlay.height() == 500


def test_vertical_mode_swaps_arrow_key_axes(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    overlay._model.focused_index = 0
    start_volume = overlay._model.entries[0].volume

    overlay.keyPressEvent(key_event(Qt.Key.Key_Right))
    assert overlay._model.focused_index == 1

    overlay.keyPressEvent(key_event(Qt.Key.Key_Left))
    assert overlay._model.focused_index == 0

    overlay.keyPressEvent(key_event(Qt.Key.Key_Down))
    assert overlay._model.entries[0].volume < start_volume

    overlay.keyPressEvent(key_event(Qt.Key.Key_Up))
    assert overlay._model.entries[0].volume == start_volume


def test_horizontal_mode_keeps_original_arrow_key_axes(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay._model.focused_index = 0
    start_volume = overlay._model.entries[0].volume

    overlay.keyPressEvent(key_event(Qt.Key.Key_Down))
    assert overlay._model.focused_index == 1

    overlay.keyPressEvent(key_event(Qt.Key.Key_Up))
    assert overlay._model.focused_index == 0

    overlay.keyPressEvent(key_event(Qt.Key.Key_Left))
    assert overlay._model.entries[0].volume < start_volume


def test_vertical_scrollbar_appears_only_after_the_visible_entry_limit(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")

    for i in range(MAX_VISIBLE_ENTRIES - len(overlay._entry_widgets)):
        fake_backend.add_session(
            FakeAudioSession(pid=3000 + i, process_name=f"limit{i}.exe", display_name=f"Limit {i}", volume=1.0)
        )
    overlay._model.refresh()
    overlay.refresh_view()
    overlay.show()
    qapp.processEvents()

    scrollbar = overlay._scroll_area.horizontalScrollBar()
    assert len(overlay._entry_widgets) == MAX_VISIBLE_ENTRIES
    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not scrollbar.isVisible()
    minimum_without_scrollbar = overlay.minimumHeight()

    fake_backend.add_session(
        FakeAudioSession(pid=4000, process_name="overflow.exe", display_name="Overflow", volume=1.0)
    )
    overlay._model.refresh()
    overlay.refresh_view()
    qapp.processEvents()

    assert len(overlay._entry_widgets) == MAX_VISIBLE_ENTRIES + 1
    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    deadline = QDeadlineTimer(1000)
    while not scrollbar.isVisible() and not deadline.hasExpired():
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    assert scrollbar.isVisible()
    margins = overlay._container_layout.contentsMargins()
    entry_minimum = max(widget.minimumSizeHint().height() for widget in overlay._entry_widgets)
    expected_minimum = max(
        overlay._title_bar.sizeHint().height() + 2 * BACKGROUND_BORDER_PX,
        entry_minimum
        + margins.top()
        + margins.bottom()
        + scrollbar.sizeHint().height()
        + 2 * BACKGROUND_BORDER_PX,
    )
    assert overlay.minimumHeight() == expected_minimum
    assert overlay.minimumHeight() > minimum_without_scrollbar

    fake_backend.remove_session("overflow.exe")
    overlay._model.refresh()
    overlay.refresh_view()
    qapp.processEvents()

    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not scrollbar.isVisible()
    assert overlay.minimumHeight() == minimum_without_scrollbar
    assert overlay._scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_vertical_scrollbar_counts_ignored_entries_only_while_expanded(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")

    for i in range(MAX_VISIBLE_ENTRIES + 1 - len(overlay._entry_widgets)):
        fake_backend.add_session(
            FakeAudioSession(pid=5000 + i, process_name=f"ignored{i}.exe", display_name=f"Ignored {i}", volume=1.0)
        )
    overlay._model.refresh()
    ignored_key = overlay._model.entries[-1].key
    overlay._model.ignore_app(ignored_key)
    overlay.refresh_view()

    assert len(overlay._entry_widgets) == MAX_VISIBLE_ENTRIES
    assert len(overlay._ignored_widgets) == 1
    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    overlay._on_expand_ignored()

    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn

    overlay._on_collapse_ignored()

    assert overlay._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_vertical_mode_pins_ignored_buttons_to_a_thin_strip(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")

    for button in (overlay._expand_button, overlay._collapse_button):
        thickness = button.sizeHint().height()
        assert button.minimumWidth() == thickness
        assert button.maximumWidth() == thickness


def test_horizontal_mode_releases_ignored_button_width(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    overlay.set_layout_mode("vertical")
    overlay.set_layout_mode("horizontal")

    for button in (overlay._expand_button, overlay._collapse_button):
        assert button.minimumWidth() == 0
        assert button.maximumWidth() > button.sizeHint().width()


def test_ignored_buttons_stretch_full_width_only_in_horizontal_mode(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    assert "width: 100%" in overlay._background.styleSheet()

    overlay.set_layout_mode("vertical")

    assert "width: 100%" not in overlay._background.styleSheet()


def test_vertical_ignored_strip_does_not_dominate_the_window_width(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay.set_layout_mode("vertical")
    entry_width = overlay._entry_widgets[0].sizeHint().width()

    overlay._model.ignore_app(overlay._model.entries[0].key)
    overlay.refresh_view()

    assert overlay._expand_button.width() < entry_width
