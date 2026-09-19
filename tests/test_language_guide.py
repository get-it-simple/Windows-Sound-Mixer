from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QScrollArea

from sound_mixer.settings_window.language_guide import LanguageGuideDialog
from sound_mixer.settings_window.window import SettingsWindow


def test_language_button_opens_readable_modal_guide(qapp, settings):
    window = SettingsWindow(settings)
    button = window._language_guide_button
    group = button.parentWidget().layout()
    language_field = window._language_combo.parentWidget()
    assert group.indexOf(button) == group.indexOf(language_field) + 1
    assert window.findChild(LanguageGuideDialog) is None
    observed = {}

    def inspect_dialog():
        dialog = qapp.activeModalWidget()
        if not isinstance(dialog, LanguageGuideDialog):
            observed["wrong_dialog"] = dialog
            if dialog is not None:
                dialog.close()
            return
        observed["title"] = dialog.windowTitle()
        observed["visible"] = dialog.isVisible()
        observed["icon"] = not dialog.windowIcon().isNull()
        observed["texts"] = [label.text() for label in dialog.findChildren(QLabel)]
        scroll = dialog.findChild(QScrollArea)
        observed["horizontal_scroll"] = scroll.horizontalScrollBar().maximum()
        observed["fits"] = all(label.height() >= label.heightForWidth(label.width()) for label in dialog.findChildren(QLabel))
        dialog.accept()

    QTimer.singleShot(50, inspect_dialog)
    button.click()
    window.close()

    assert observed["title"] == "Add a language"
    assert observed["visible"] and observed["icon"] and observed["fits"]
    assert observed["horizontal_scroll"] == 0
    text = "\n".join(observed["texts"])
    assert "sound_mixer/i18n/en/strings.json" in text
    assert "UTF-8" in text
    assert "Missing entries automatically use English" in text
    assert "python build.py" in text
