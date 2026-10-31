import pytest
from PySide6.QtCore import QEventLoop, QObject, QPoint, QRect, Signal
from PySide6.QtGui import QGuiApplication

from sound_mixer.media.model import MediaItem
from sound_mixer.overlay.window import OverlayWindow
from test_playing_media import make_overlay


def settle(qapp):
    for _ in range(6):
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)


@pytest.mark.parametrize("count", [4, 5, 8])
def test_vertical_media_uses_available_space(qapp, fake_backend, settings, monkeypatch, count):
    settings.set_layout_mode("vertical")
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(0, 0, 1600, 1600), raising=False)
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(100, 50)
        owner = overlay._model.entries[1].key
        overlay.set_media_items(tuple(MediaItem(str(i), owner, f"Track {i}", owner_key=owner) for i in range(count)))
        settle(qapp)
        area = overlay._media_footer
        assert len(overlay._footer_cards) == count
        assert area.verticalScrollBar().maximum() == 0
        assert not area.verticalScrollBar().isVisible()
        for card in overlay._footer_cards:
            assert area.viewport().rect().contains(card.mapTo(area.viewport(), QPoint(0, 0)))
            assert area.viewport().rect().contains(card.mapTo(area.viewport(), card.rect().bottomRight()))
        assert overlay.y() == 50
        assert overlay.frameGeometry().bottom() < 1600
    finally:
        overlay.close()


@pytest.mark.parametrize("mode", ["vertical", "horizontal"])
def test_media_overflow_fits_monitor_and_recalculates(qapp, fake_backend, settings, monkeypatch, mode):
    settings.set_layout_mode(mode)
    available = QRect(0, 0, 1400, 650)
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(available), raising=False)
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(100, 80)
        owner = overlay._model.entries[1].key
        items = tuple(MediaItem(str(i), owner, f"Track {i}", owner_key=owner) for i in range(8))
        overlay.set_media_items(items)
        settle(qapp)
        area = overlay._media_footer if mode == "vertical" else overlay._scroll_area
        assert area.verticalScrollBar().isVisible()
        assert area.verticalScrollBar().maximum() > 0
        assert overlay.frameGeometry().bottom() <= available.bottom()
        if mode == "vertical":
            assert area.verticalScrollBar().maximum() >= overlay._footer_cards[0].height() + overlay._media_footer_layout.spacing()
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        settle(qapp)
        last = overlay._footer_cards[-1] if mode == "vertical" else overlay._entry_widgets[-1]
        assert area.viewport().rect().contains(last.mapTo(area.viewport(), last.rect().bottomRight()))
        available.setHeight(2000)
        overlay._settle_media_layout()
        settle(qapp)
        assert area.verticalScrollBar().maximum() == 0
        assert not area.verticalScrollBar().isVisible()
        overlay.set_media_items(())
        settle(qapp)
        assert not overlay._media_footer.isVisible()
    finally:
        overlay.close()


def test_same_owner_sessions_keep_separate_cards_and_commands(qapp, fake_backend, settings, monkeypatch):
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    actions = []
    overlay.media_action_requested.connect(lambda *args: actions.append(args))
    try:
        owner = overlay._model.entries[1].key
        items = tuple(MediaItem(str(i), "same.browser", "Same title", owner_key=owner, can_pause=True, generation=12) for i in range(3))
        overlay.set_media_items(items)
        settle(qapp)
        cards = overlay._entry_widgets[1]._media_cards
        assert len(cards) == 3
        for card in cards:
            card.buttons["pause"].click()
        assert actions == [(str(i), 12, "pause") for i in range(3)]
        overlay.set_layout_mode("vertical")
        settle(qapp)
        assert [card.item.session_id for card in overlay._footer_cards] == ["0", "1", "2"]
        overlay.set_media_items(items[1:])
        settle(qapp)
        assert [card.item.session_id for card in overlay._footer_cards] == ["1", "2"]
    finally:
        overlay.close()


@pytest.mark.parametrize("excess", [0, 1, 5])
def test_footer_exact_fit_and_small_overflow(qapp, fake_backend, settings, monkeypatch, excess):
    settings.set_layout_mode("vertical")
    available = QRect(0, 0, 1600, 1600)
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(available))
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(100, 50)
        overlay.resize(overlay.width(), overlay.minimumHeight())
        owner = overlay._model.entries[1].key
        overlay.set_media_items(tuple(MediaItem(str(i), owner, "Track", owner_key=owner) for i in range(4)))
        settle(qapp)
        available.setBottom(overlay.frameGeometry().bottom() - excess)
        overlay._settle_media_layout()
        settle(qapp)
        area = overlay._media_footer
        assert area.verticalScrollBar().isVisible() == bool(excess)
        if excess:
            assert area.verticalScrollBar().maximum() >= overlay._footer_cards[0].height() + overlay._media_footer_layout.spacing()
        else:
            assert area.verticalScrollBar().maximum() == 0
        assert overlay.frameGeometry().bottom() <= available.bottom()
        assert overlay.y() == 50
        geometry = overlay.geometry()
        scroll_range = area.verticalScrollBar().maximum()
        for _ in range(5):
            overlay._settle_media_layout()
            settle(qapp)
            assert overlay.geometry() == geometry
            assert area.verticalScrollBar().maximum() == scroll_range
    finally:
        overlay.close()


@pytest.mark.parametrize("mode", ["horizontal", "vertical"])
@pytest.mark.parametrize("scale", [0.5, 1.0, 3.0])
def test_monitor_limits_override_entry_count(qapp, fake_backend, settings, monkeypatch, mode, scale):
    settings.set_layout_mode(mode)
    settings.set_ui_scale(scale)
    available = QRect(-1400, 0, 1400, 1100)
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(available))
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(-1300, 50)
        owner = overlay._model.entries[1].key
        overlay.set_media_items(tuple(MediaItem(str(i), owner, "Track", owner_key=owner) for i in range(40)))
        settle(qapp)
        assert len(overlay._entry_widgets) < 6
        assert overlay.width() <= available.width()
        assert overlay.frameGeometry().bottom() <= available.bottom()
        if mode == "horizontal":
            assert overlay._scroll_area.verticalScrollBar().isVisible()
        else:
            assert overlay._media_footer.verticalScrollBar().isVisible()
        overlay.move(-1300, available.bottom() - 10)
        settle(qapp)
        assert overlay.y() < available.bottom() - 10
        assert overlay.frameGeometry().bottom() <= available.bottom()
    finally:
        overlay.close()


def test_monitor_and_work_area_changes_update_media_automatically(qapp, fake_backend, settings, monkeypatch):
    class Screen(QObject):
        availableGeometryChanged = Signal(QRect)
        geometryChanged = Signal(QRect)

        def __init__(self, rect):
            super().__init__()
            self.rect = rect

        def availableGeometry(self):
            return QRect(self.rect)

    small = Screen(QRect(0, 0, 1600, 800))
    large = Screen(QRect(1600, 0, 1600, 1800))
    monkeypatch.setattr(QGuiApplication, "screenAt", lambda point: small if point.x() < 1600 else large)
    settings.set_layout_mode("vertical")
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(100, 50)
        overlay.set_media_items(tuple(MediaItem(str(i), "unknown", "Track") for i in range(12)))
        settle(qapp)
        bar = overlay._media_footer.verticalScrollBar()
        assert bar.isVisible()
        overlay.move(1700, 50)
        settle(qapp)
        assert not bar.isVisible() and bar.maximum() == 0
        large.rect.setHeight(650)
        large.availableGeometryChanged.emit(large.rect)
        settle(qapp)
        assert bar.isVisible()
        assert overlay.frameGeometry().bottom() <= large.rect.bottom()
        large.rect.setHeight(1800)
        large.availableGeometryChanged.emit(large.rect)
        settle(qapp)
        assert not bar.isVisible() and bar.maximum() == 0
    finally:
        overlay.close()


def test_vertical_main_list_scrolls_when_monitor_is_narrow(qapp, fake_backend, settings, monkeypatch):
    settings.set_layout_mode("vertical")
    settings.set_ui_scale(2.0)
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(0, 0, 400, 1600))
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(0, 50)
        settle(qapp)
        assert len(overlay._entry_widgets) < 6
        assert overlay.width() <= 400
        area = overlay._scroll_area
        assert area.horizontalScrollBar().isVisible()
        area.horizontalScrollBar().setValue(area.horizontalScrollBar().maximum())
        settle(qapp)
        last = overlay._entry_widgets[-1]
        point = last.mapTo(area.viewport(), last.rect().bottomRight())
        assert 0 <= point.x() < area.viewport().width()
    finally:
        overlay.close()


def test_scrolled_media_connections_stay_below_volume_controls(qapp, fake_backend, settings, monkeypatch):
    settings.set_layout_mode("vertical")
    monkeypatch.setattr(OverlayWindow, "_available_geometry", lambda self: QRect(0, 0, 1600, 650))
    overlay = make_overlay(qapp, fake_backend, settings, monkeypatch)
    try:
        overlay.move(100, 30)
        owner_key = overlay._model.entries[1].key
        overlay.set_media_items(tuple(MediaItem(str(i), owner_key, "Track", owner_key=owner_key) for i in range(10)))
        settle(qapp)
        area = overlay._media_footer
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        settle(qapp)
        connections = overlay._media_connections
        owner = overlay._entry_widgets[1]
        origin = connections.mapFromGlobal(owner.mapToGlobal(QPoint()))
        image = connections.grab().toImage()
        for y in range(origin.y() + owner.height() // 3, origin.y() + 2 * owner.height() // 3):
            for x in range(origin.x() + owner.width() // 2 - 1, origin.x() + owner.width() // 2 + 2):
                color = image.pixelColor(x, y)
                assert not (color.blue() > 100 and color.blue() > color.red() * 1.2)
        assert len(connections._links) == 10
    finally:
        overlay.close()
