import re

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QWheelEvent

from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.entry_widget import BASE_APP_ICON_PX, BASE_FONT_PX, EntryWidget, slider_style


def wheel_event(direction: int = 1) -> QWheelEvent:
    from PySide6.QtCore import Qt

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


def wheel_event_horizontal(direction: int = 1) -> QWheelEvent:
    from PySide6.QtCore import Qt

    return QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(120 * direction, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.AltModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def make_entry(volume: float = 0.5, muted: bool = False) -> MixerEntry:
    return MixerEntry(key="aurora.exe", display_name="Aurora Browser", volume=volume, muted=muted, is_master=False)


def test_set_entry_updates_spinbox_value(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.42), focused=False)

    assert widget._volume_spinbox.value() == 42
    assert widget._slider.value() == 42


def test_editing_spinbox_emits_volume_changed(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    received = []
    widget.volume_changed.connect(received.append)
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    widget._volume_spinbox.setValue(75)

    assert received == [0.75]
    assert focus_requests == [True]


def test_set_entry_does_not_emit_volume_changed(qapp):
    widget = EntryWidget()

    received = []
    widget.volume_changed.connect(received.append)

    widget.set_entry(make_entry(volume=0.42), focused=False)

    assert received == []


def test_apply_scale_resizes_spinbox_font(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._volume_spinbox.font().pixelSize() == round(BASE_FONT_PX * 2.0)


def test_apply_scale_fits_spinbox_to_max_value_text(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._volume_spinbox.width() == widget._volume_spinbox.minimumSizeHint().width()


def test_entry_layout_places_icon_mute_spinbox_and_slider_in_order(qapp):
    widget = EntryWidget()
    layout = widget.layout()

    mute_idx = layout.indexOf(widget._mute_button)
    spinbox_idx = layout.indexOf(widget._volume_spinbox)
    column_idx = layout.indexOf(widget._slider_column)

    assert mute_idx > -1
    assert spinbox_idx > mute_idx
    assert column_idx > spinbox_idx
    assert widget._slider_column.layout().indexOf(widget._slider) == 0
    assert widget._slider_column.layout().indexOf(widget._process_name_label) == 1


def test_scroll_on_slider_uses_entry_wheel_handling(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    handled = widget.eventFilter(widget._slider, wheel_event(direction=1))

    assert handled is True
    assert scrolled == [1]
    assert focus_requests == [True]


def test_scroll_on_spinbox_uses_entry_wheel_handling(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    handled = widget.eventFilter(widget._volume_spinbox, wheel_event(direction=-1))

    assert handled is True
    assert scrolled == [-1]


def test_set_entry_shows_display_name_as_tooltip(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert widget._icon_label.toolTip() == "Aurora Browser"


def test_set_entry_keeps_icon_container_visible_for_master(qapp):
    widget = EntryWidget()

    widget.set_entry(
        MixerEntry(key="master", display_name="System", volume=0.5, muted=False, is_master=True), focused=False
    )

    assert not widget._icon_container.isHidden()
    assert widget._icon_label.isHidden()


def test_set_entry_hide_button_suppressed_for_master(qapp):
    widget = EntryWidget()

    widget.set_entry(
        MixerEntry(key="master", display_name="System", volume=0.5, muted=False, is_master=True), focused=False
    )
    widget.enterEvent(None)

    assert widget._hide_button.isHidden()


def test_set_entry_shows_fallback_icon_for_unknown_app(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert not widget._icon_label.pixmap().isNull()


def test_apply_scale_resizes_icon_label(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._icon_label.width() == round(BASE_APP_ICON_PX * 2.0)
    assert widget._icon_label.height() == round(BASE_APP_ICON_PX * 2.0)


@pytest.mark.parametrize("scale_percent", range(50, 301))
def test_slider_handle_stays_round_at_every_scale(scale_percent):
    css = slider_style(scale_percent / 100, "#3a96dd")

    handle_size = int(re.search(r"QSlider::handle:horizontal \{\s*width: (\d+)px", css).group(1))
    groove_height = int(re.search(r"QSlider::groove:horizontal \{\s*height: (\d+)px", css).group(1))

    # The handle is centered over the groove with a negative margin; if the
    # difference is odd, Qt renders the handle as a square instead of a circle.
    assert (handle_size - groove_height) % 2 == 0


def test_hide_button_hidden_by_default(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=False)

    assert widget._hide_button.isHidden()



def test_hide_button_hidden_when_unfocused(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=True)
    widget.set_entry(make_entry(), focused=False)

    assert widget._hide_button.isHidden()


def test_hide_button_emits_ignore_requested(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=True)

    received = []
    widget.ignore_requested.connect(lambda: received.append(True))
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    widget._hide_button.click()

    assert received == [True]
    assert focus_requests == [True]


def test_set_ignore_tooltip_changes_button_tooltip(qapp):
    widget = EntryWidget()

    widget.set_ignore_tooltip("Restore")

    assert widget._hide_button.toolTip() == "Restore"


def test_hide_button_default_tooltip_is_ignore(qapp):
    widget = EntryWidget()

    assert widget._hide_button.toolTip() == "Ignore"


def test_apply_scale_resizes_hide_button_icon(qapp):
    from sound_mixer.overlay.entry_widget import BASE_ICON_PX

    widget = EntryWidget()

    widget.apply_scale(2.0)

    expected = round(BASE_ICON_PX * 2.0)
    assert widget._hide_button.iconSize().width() == expected
    assert widget._hide_button.iconSize().height() == expected


def test_scroll_up_with_alt_held_increases_volume(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    widget.wheelEvent(wheel_event_horizontal(direction=1))

    assert scrolled == [1]


def test_scroll_down_with_alt_held_decreases_volume(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    widget.wheelEvent(wheel_event_horizontal(direction=-1))

    assert scrolled == [-1]


def test_process_name_label_text_set_from_entry(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)
    assert widget._process_name_label.text() == "Aurora Browser"


def test_process_name_label_is_left_aligned(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    assert widget._process_name_label.alignment() & Qt.AlignmentFlag.AlignLeft


def test_set_entry_identical_state_does_not_reload_app_icon(qapp, monkeypatch):
    import sound_mixer.overlay.entry_widget as entry_widget_module

    calls = []
    real_load = entry_widget_module.load_app_icon
    monkeypatch.setattr(
        entry_widget_module, "load_app_icon", lambda path: (calls.append(path), real_load(path))[1]
    )

    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)
    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert len(calls) == 1


def test_set_entry_changed_icon_path_reloads_icon(qapp, monkeypatch):
    import sound_mixer.overlay.entry_widget as entry_widget_module

    calls = []
    real_load = entry_widget_module.load_app_icon
    monkeypatch.setattr(
        entry_widget_module, "load_app_icon", lambda path: (calls.append(path), real_load(path))[1]
    )

    widget = EntryWidget()
    entry = make_entry(volume=0.5)
    widget.set_entry(entry, focused=False)
    changed = MixerEntry(
        key=entry.key, display_name=entry.display_name, volume=entry.volume, muted=entry.muted, icon_path="C:/other.exe"
    )
    widget.set_entry(changed, focused=False)

    assert calls == ["", "C:/other.exe"]


def test_set_entry_reflects_external_volume_change(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.42), focused=False)

    widget.set_entry(make_entry(volume=0.55), focused=False)

    assert widget._volume_spinbox.value() == 55
    assert widget._slider.value() == 55


def test_set_entry_reflects_external_mute_change(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(muted=False), focused=False)
    unmuted_key = widget._mute_button.icon().cacheKey()

    widget.set_entry(make_entry(muted=True), focused=False)

    assert widget._mute_button.icon().cacheKey() != unmuted_key


def test_set_entry_focus_change_updates_property(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(), focused=True)
    assert widget.property("focused") is True

    widget.set_entry(make_entry(), focused=False)
    assert widget.property("focused") is False


def test_widget_reassigned_to_different_entry_updates_everything(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.3), focused=False)

    other = MixerEntry(
        key="player.exe", display_name="Media Player", volume=0.8, muted=True, icon_path="C:/player.exe"
    )
    widget.set_entry(other, focused=True)

    assert widget._process_name_label.text() == "Media Player"
    assert widget.toolTip() == "Media Player"
    assert widget._volume_spinbox.value() == 80
    assert widget._slider.value() == 80
    assert widget.property("focused") is True


def test_zero_delta_wheel_event_does_not_scroll(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    zero_event = QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    widget.wheelEvent(zero_event)

    assert scrolled == []


def test_vertical_mode_uses_vertical_slider(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QBoxLayout

    widget = EntryWidget()
    widget.set_layout_mode("vertical")

    assert widget.is_vertical() is True
    assert widget._slider.orientation() == Qt.Orientation.Vertical
    assert widget.layout().direction() == QBoxLayout.Direction.TopToBottom


def test_switching_back_to_horizontal_restores_slider_orientation(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QBoxLayout

    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.set_layout_mode("horizontal")

    assert widget._slider.orientation() == Qt.Orientation.Horizontal
    assert widget.layout().direction() == QBoxLayout.Direction.LeftToRight
    assert widget.maximumWidth() > widget.sizeHint().width()


def test_vertical_mode_pins_column_width_to_scale(qapp):
    from sound_mixer.overlay.entry_widget import BASE_VERTICAL_ENTRY_WIDTH_PX

    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.apply_scale(2.0)

    expected = round(BASE_VERTICAL_ENTRY_WIDTH_PX * 2.0)
    assert widget.width() == expected
    assert widget.sizeHint().width() == expected


def test_vertical_column_width_is_not_narrower_than_its_content(qapp):
    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert widget.sizeHint().width() >= widget.minimumSizeHint().width()


def test_vertical_mode_hides_process_name_and_keeps_it_on_hover(qapp):
    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.set_entry(
        MixerEntry(key="p.exe", display_name="A Very Long Application Name", volume=0.5, muted=False),
        focused=False,
    )

    assert widget._process_name_label.isHidden()
    assert widget.toolTip() == "A Very Long Application Name"
    assert widget._slider.toolTip() == "A Very Long Application Name"


def test_switching_back_to_horizontal_shows_process_name_again(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)
    widget.set_layout_mode("vertical")

    widget.set_layout_mode("horizontal")

    assert not widget._process_name_label.isHidden()
    assert widget._process_name_label.text() == "Aurora Browser"


def test_horizontal_mode_shows_full_process_name(qapp):
    widget = EntryWidget()
    widget.set_entry(
        MixerEntry(key="p.exe", display_name="A Very Long Application Name", volume=0.5, muted=False),
        focused=False,
    )

    assert widget._process_name_label.text() == "A Very Long Application Name"


@pytest.mark.parametrize("scale_percent", range(50, 301))
def test_vertical_slider_handle_stays_round_at_every_scale(scale_percent):
    css = slider_style(scale_percent / 100, "#3a96dd")

    handle_size = int(re.search(r"QSlider::handle:vertical \{\s*width: (\d+)px", css).group(1))
    groove_width = int(re.search(r"QSlider::groove:vertical \{\s*width: (\d+)px", css).group(1))

    assert (handle_size - groove_width) % 2 == 0


def test_vertical_slider_style_fills_below_the_handle(qapp):
    css = slider_style(1.0, "#3a96dd")

    filled = re.search(r"QSlider::add-page:vertical \{[^}]*background: ([^;]+);", css).group(1)

    assert filled == "#3a96dd"


def styled_vertical_widget(scale: float) -> EntryWidget:
    from PySide6.QtWidgets import QFrame, QVBoxLayout

    from sound_mixer.overlay.window import background_style

    background = QFrame()
    background.setObjectName("background")
    background.setStyleSheet(background_style(scale, "#3a96dd", True, True))
    layout = QVBoxLayout(background)
    widget = EntryWidget(background)
    layout.addWidget(widget)
    widget.set_layout_mode("vertical")
    widget.apply_scale(scale)
    widget.set_entry(make_entry(volume=1.0), focused=False)
    widget._background_holder = background
    return widget


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0, 3.0])
def test_vertical_value_box_is_never_wider_than_the_mute_button(qapp, scale):
    widget = styled_vertical_widget(scale)

    assert widget._volume_spinbox.width() <= widget._mute_button.sizeHint().width()


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0, 3.0])
def test_vertical_value_box_matches_the_mute_button_width(qapp, scale):
    widget = styled_vertical_widget(scale)

    assert widget._volume_spinbox.width() == widget._mute_button.sizeHint().width()


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0, 3.0])
def test_vertical_value_font_is_smaller_than_the_body_font(qapp, scale):
    from sound_mixer.overlay.entry_widget import BASE_VERTICAL_VALUE_FONT_PX

    widget = styled_vertical_widget(scale)

    assert BASE_VERTICAL_VALUE_FONT_PX < BASE_FONT_PX
    assert widget._volume_spinbox.font().pixelSize() == round(BASE_VERTICAL_VALUE_FONT_PX * scale)


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0, 3.0])
def test_vertical_stylesheet_drives_the_value_font(qapp, scale):
    from sound_mixer.overlay.entry_widget import BASE_VERTICAL_VALUE_FONT_PX
    from sound_mixer.overlay.window import background_style

    vertical = background_style(scale, "#3a96dd", True, True)
    horizontal = background_style(scale, "#3a96dd", True, False)

    vertical_rule = vertical.split("#background #entryWidget QSpinBox {")[1].split("}")[0]
    horizontal_rule = horizontal.split("#background #entryWidget QSpinBox {")[1].split("}")[0]

    assert f"font-size: {round(BASE_VERTICAL_VALUE_FONT_PX * scale)}px" in vertical_rule
    assert f"font-size: {round(BASE_FONT_PX * scale)}px" in horizontal_rule


def test_horizontal_value_box_keeps_its_own_width(qapp):
    widget = EntryWidget()
    widget.apply_scale(1.0)

    assert widget._volume_spinbox.width() == widget._volume_spinbox.minimumSizeHint().width()
    assert widget._volume_spinbox.font().pixelSize() == BASE_FONT_PX


def test_vertical_mode_centers_every_element(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    layout = widget.layout()

    for child in (widget._icon_container, widget._mute_button, widget._volume_spinbox, widget._slider_column):
        index = layout.indexOf(child)
        assert layout.itemAt(index).alignment() & Qt.AlignmentFlag.AlignHCenter

    column_layout = widget._slider_column.layout()
    slider_index = column_layout.indexOf(widget._slider)
    assert column_layout.itemAt(slider_index).alignment() & Qt.AlignmentFlag.AlignHCenter


def test_horizontal_mode_centers_elements_vertically(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.set_layout_mode("horizontal")
    layout = widget.layout()

    index = layout.indexOf(widget._mute_button)
    assert layout.itemAt(index).alignment() & Qt.AlignmentFlag.AlignVCenter


def test_vertical_slider_is_thicker_than_the_horizontal_one(qapp):
    css = slider_style(1.0, "#3a96dd")

    horizontal = int(re.search(r"QSlider::groove:horizontal \{\s*height: (\d+)px", css).group(1))
    vertical = int(re.search(r"QSlider::groove:vertical \{\s*width: (\d+)px", css).group(1))
    h_handle = int(re.search(r"QSlider::handle:horizontal \{\s*width: (\d+)px", css).group(1))
    v_handle = int(re.search(r"QSlider::handle:vertical \{\s*width: (\d+)px", css).group(1))

    assert vertical > horizontal
    assert v_handle > h_handle


def test_vertical_slider_reserves_room_for_the_wider_handle(qapp):
    from sound_mixer.overlay.entry_widget import BASE_VERTICAL_SLIDER_HEIGHT_PX

    css = slider_style(1.0, "#3a96dd")
    handle = int(re.search(r"QSlider::handle:vertical \{\s*width: (\d+)px", css).group(1))

    widget = EntryWidget()
    widget.set_layout_mode("vertical")
    widget.apply_scale(1.0)

    assert widget._slider.minimumWidth() >= handle
    assert widget._slider.minimumHeight() == BASE_VERTICAL_SLIDER_HEIGHT_PX
