import copy
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from sound_mixer.app_key import normalize_app_key
from sound_mixer.executable_path import InvalidExecutablePathError, resolve_application_path
from sound_mixer.i18n import t
from sound_mixer.overlay.icons import DelayedTooltipButton, load_icon
from sound_mixer.settings.presets import MAX_PRESETS
from sound_mixer.settings_window.managed_apps_editor import AppDropZone, ManagedAppRow


def action_button(icon, tooltip, parent, delay, *, checkable=False):
    button = DelayedTooltipButton(parent, tooltip_delay_ms=delay)
    button.setIcon(load_icon(icon))
    button.setToolTip(t(tooltip))
    button.setAccessibleName(t(tooltip))
    button.setCheckable(checkable)
    if icon == "muted" and checkable:
        button.setIcon(load_icon("volume"))
        button.toggled.connect(lambda checked: button.setIcon(load_icon("muted" if checked else "volume")))
    button.setStyleSheet(
        "QToolButton { background: #626071; border: none; border-radius: 4px; padding: 4px; }"
        "QToolButton:hover { background: #716f82; }"
        "QToolButton:checked { background: #526481; }"
    )
    return button


def volume_control(value, parent):
    control = QSpinBox(parent)
    control.setRange(0, 100)
    control.setSuffix("%")
    control.setValue(round(value * 100))
    control.setProperty("initialVolume", value)
    return control


def volume_value(control):
    original = control.property("initialVolume")
    return original if control.value() == round(original * 100) else control.value() / 100


class PresetAppRow(ManagedAppRow):
    def __init__(self, key, state, isolated, parent, delay):
        super().__init__(key, isolated, parent)
        self.key = key
        self.isolate = self._enabled_checkbox
        self.isolate.setToolTip(t("isolate_app"))
        self.isolate.setAccessibleName(t("isolate_app"))
        self.volume = volume_control(state["volume"], self)
        self.volume.setAccessibleName(t("preset_volume"))
        self.mute = action_button("muted", "mute_unmute_tooltip", self, delay, checkable=True)
        self.mute.setChecked(state["muted"])
        self.layout().insertWidget(2, self.volume)
        self.layout().insertWidget(3, self.mute)
        self._remove_button.set_tooltip_delay_ms(delay)
        self._remove_button.setStyleSheet(self.mute.styleSheet())

    def state(self):
        return {"volume": volume_value(self.volume), "muted": self.mute.isChecked()}


class PresetCard(QFrame):
    def __init__(self, preset, editor):
        super().__init__(editor)
        self.editor = editor
        self.preset_id = preset["id"]
        self._source = copy.deepcopy(preset)
        self.rows = {}
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.active = action_button("toggle_off", "activate_preset", self, editor.delay, checkable=True)
        self.active.clicked.connect(lambda: editor.select(self.preset_id if self.active.isChecked() else None))
        header.addWidget(self.active)
        self.name = QLineEdit(preset["name"], self)
        self.name.setPlaceholderText(t("preset_name"))
        self.name.setAccessibleName(t("preset_name"))
        self.name.textChanged.connect(lambda text: editor.structure_changed.emit())
        header.addWidget(self.name, 1)
        self.shortcut = action_button("redirect", "preset_shortcut", self, editor.delay)
        self.shortcut.clicked.connect(lambda: editor.shortcut_requested.emit(self.preset_id))
        header.addWidget(self.shortcut)
        self.remove = action_button("trash", "delete_preset", self, editor.delay)
        self.remove.clicked.connect(lambda: editor.remove_card(self))
        header.addWidget(self.remove)
        layout.addLayout(header)
        master = QHBoxLayout()
        master.addWidget(QLabel(t("preset_system_volume"), self), 1)
        self.master_volume = volume_control(preset["master_volume"], self)
        self.master_mute = action_button("muted", "mute_unmute_tooltip", self, editor.delay, checkable=True)
        self.master_mute.setChecked(preset["master_muted"])
        master.addWidget(self.master_volume)
        master.addWidget(self.master_mute)
        layout.addLayout(master)
        self.drop_zone = AppDropZone(self)
        self.drop_zone.app_dropped.connect(self.add_path)
        layout.addWidget(self.drop_zone)
        self.error = QLabel(self)
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #e05555;")
        self.error.hide()
        layout.addWidget(self.error)
        self.rows_layout = QVBoxLayout()
        layout.addLayout(self.rows_layout)
        for key, state in preset["apps"].items():
            self.add_row(key, state, key == preset["isolated_app"])
        self.refresh_whitelist()

    def add_path(self, path):
        try:
            key = normalize_app_key(resolve_application_path(path))
        except InvalidExecutablePathError:
            self.error.setText(t("invalid_application_drop"))
            self.error.show()
            return
        if not self.editor.is_allowed(key):
            self.error.setText(t("preset_not_whitelisted"))
            self.error.show()
            return
        self.error.hide()
        if key not in self.rows:
            volume, muted = self.editor.initial_state(key)
            self.add_row(key, {"volume": volume, "muted": muted})
            self.refresh_whitelist()

    def add_row(self, key, state, isolated=False):
        row = PresetAppRow(key, state, isolated, self, self.editor.delay)
        row.remove_requested.connect(lambda: self.remove_row(key))
        row.isolate.toggled.connect(lambda checked: self.select_isolation(key, checked))
        self.rows[key] = row
        self.rows_layout.addWidget(row)
        return row

    def remove_row(self, key):
        row = self.rows.pop(key)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self.refresh_whitelist()

    def select_isolation(self, key, checked):
        if checked:
            for other_key, row in self.rows.items():
                if other_key != key:
                    row.isolate.blockSignals(True)
                    row.isolate.setChecked(False)
                    row.isolate.blockSignals(False)
        self.refresh_whitelist()

    def refresh_whitelist(self):
        for key, row in self.rows.items():
            if not self.editor.is_allowed(key):
                row.isolate.blockSignals(True)
                row.isolate.setChecked(False)
                row.isolate.blockSignals(False)
        isolated = next((key for key, row in self.rows.items() if row.isolate.isChecked()), None)
        for key, row in self.rows.items():
            allowed = self.editor.is_allowed(key)
            row.isolate.setEnabled(allowed)
            editable = allowed and (isolated is None or isolated == key)
            row.volume.setEnabled(editable)
            row.mute.setEnabled(editable)
            row._name_label.setEnabled(allowed)
            row.setToolTip("" if allowed else t("preset_not_whitelisted"))

    def preset(self):
        result = copy.deepcopy(self._source)
        result.update({
            "name": self.name.text().strip() or t("preset_default_name"),
            "master_volume": volume_value(self.master_volume),
            "master_muted": self.master_mute.isChecked(),
            "apps": {key: row.state() for key, row in self.rows.items()},
            "isolated_app": next((key for key, row in self.rows.items() if row.isolate.isChecked()), None),
        })
        return result


class PresetsEditor(QWidget):
    structure_changed = Signal()
    shortcut_requested = Signal(str)

    def __init__(self, settings, model=None, is_allowed=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.model = model
        self.is_allowed = is_allowed or settings.is_app_whitelisted
        self.delay = settings.get_tooltip_delay_ms()
        self.initial_presets = settings.get_presets()
        self.active_id = settings.get_active_preset_id()
        self.cards = []
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.normal_button = action_button("toggle_on", "default_mode", self, self.delay, checkable=True)
        self.normal_button.clicked.connect(lambda: self.select(None))
        header.addWidget(self.normal_button)
        header.addWidget(QLabel(t("default_mode"), self), 1)
        self.add_button = action_button("plus", "add_preset", self, self.delay)
        self.add_button.clicked.connect(self.add_preset)
        header.addWidget(self.add_button)
        layout.addLayout(header)
        hint = QLabel(t("presets_hint"), self)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget(scroll)
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        for preset in self.initial_presets:
            self.add_card(preset)
        self.select(self.active_id)

    def initial_state(self, key):
        if self.model is not None:
            for entry in self.model.entries + self.model.ignored_entries:
                if entry.key == key:
                    if entry.volume_locked:
                        return self.settings.get_profile_app_state(key)
                    return entry.volume, entry.muted
        return self.settings.get_app_volume(key), self.settings.get_app_muted(key)

    def add_preset(self):
        if len(self.cards) >= MAX_PRESETS:
            return None
        if self.model is not None:
            entry = self.model.entries[0]
            volume, muted = entry.volume, entry.muted
        else:
            volume, muted = self.settings.get_profile_master_state()
        preset = {"id": uuid4().hex, "name": t("preset_default_name"), "apps": {},
                  "master_volume": volume, "master_muted": muted, "isolated_app": None,
                  "hotkey": {"combo": "", "enabled": False}}
        card = self.add_card(preset)
        self.structure_changed.emit()
        card.name.setFocus()
        card.name.selectAll()
        return card

    def add_card(self, preset):
        card = PresetCard(preset, self)
        self.cards.append(card)
        self.cards_layout.addWidget(card)
        self.add_button.setEnabled(len(self.cards) < MAX_PRESETS)
        return card

    def remove_card(self, card):
        self.cards.remove(card)
        self.add_button.setEnabled(len(self.cards) < MAX_PRESETS)
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        if self.active_id == card.preset_id:
            self.select(None)
        self.structure_changed.emit()

    def select(self, preset_id):
        self.active_id = preset_id
        self.normal_button.setChecked(preset_id is None)
        self.normal_button.setIcon(load_icon("toggle_on" if preset_id is None else "toggle_off"))
        for card in self.cards:
            card.active.setChecked(card.preset_id == preset_id)
            card.active.setIcon(load_icon("toggle_on" if card.preset_id == preset_id else "toggle_off"))

    def refresh_whitelist(self):
        for card in self.cards:
            card.refresh_whitelist()

    def presets(self):
        return [card.preset() for card in self.cards]


def merge_preset_edits(initial, edited, current):
    missing = object()

    def merge(old, draft, live):
        if old == draft:
            return copy.deepcopy(live)
        if isinstance(old, dict) and isinstance(draft, dict) and isinstance(live, dict):
            result = copy.deepcopy(live)
            for key in old.keys() | draft.keys():
                if key not in draft:
                    result.pop(key, None)
                elif key not in old:
                    result[key] = copy.deepcopy(draft[key])
                elif draft[key] != old[key]:
                    result[key] = merge(old[key], draft[key], live.get(key, missing))
            return result
        return copy.deepcopy(draft)

    before = {p["id"]: p for p in initial}
    latest = {p["id"]: p for p in current}
    return [merge(before.get(p["id"], missing), p, latest.get(p["id"], missing)) for p in edited]
