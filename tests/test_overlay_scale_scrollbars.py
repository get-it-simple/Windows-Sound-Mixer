import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import MAX_VISIBLE_ENTRIES, OverlayWindow


@pytest.mark.parametrize("mode", ["horizontal", "vertical"])
@pytest.mark.parametrize("count", [3, MAX_VISIBLE_ENTRIES, MAX_VISIBLE_ENTRIES + 1])
@pytest.mark.parametrize("ignored", ["none", "collapsed", "expanded"])
def test_repeated_scale_changes_preserve_scroll_threshold(qapp, fake_backend, settings, mode, count, ignored):
    settings.set_layout_mode(mode)
    for index in range(count - 3):
        fake_backend.add_session(FakeAudioSession(
            pid=1000 + index, process_name=f"app{index}.exe", display_name=f"App {index}",
        ))
    model = MixerModel(fake_backend, settings)
    if ignored != "none":
        model.ignore_app("lumen.exe")
    overlay = OverlayWindow(model, settings)
    overlay._finish_warm_up()
    if ignored == "expanded":
        overlay._on_expand_ignored()
    overlay.show()
    try:
        scales = [100, 125, 150, 175, 200, 135, 85, 50, 75, 110, 100]
        scales += list(range(50, 301, 5)) + list(range(300, 49, -5))
        for percent in scales:
            settings.set_ui_scale(max(50, percent - 10) / 100)
            overlay.apply_scale()
            settings.set_ui_scale(percent / 100)
            overlay.apply_scale()
            QTest.qWait(50)
            area = overlay._scroll_area
            scrollbar = area.horizontalScrollBar() if mode == "vertical" else area.verticalScrollBar()
            visible_count = count - (ignored == "collapsed")
            assert scrollbar.isVisible() == (visible_count > MAX_VISIBLE_ENTRIES), (mode, ignored, percent)
            if visible_count > MAX_VISIBLE_ENTRIES:
                assert scrollbar.maximum() > 0, (mode, ignored, percent)
            if visible_count <= MAX_VISIBLE_ENTRIES:
                assert scrollbar.maximum() == 0, (mode, ignored, percent, scrollbar.maximum())
                widgets = overlay._entry_widgets + (overlay._ignored_widgets if ignored == "expanded" else [])
                for widget in widgets:
                    top_left = widget.mapTo(area.viewport(), QPoint(0, 0))
                    bottom_right = widget.mapTo(area.viewport(), widget.rect().bottomRight())
                    assert area.viewport().rect().contains(top_left), (mode, ignored, percent, top_left)
                    assert area.viewport().rect().contains(bottom_right), (mode, ignored, percent, bottom_right)
    finally:
        overlay.close()
        overlay.deleteLater()
