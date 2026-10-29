import json

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import flags as flagmod
from . import installer, tweaks
from .config import cfg
from .constants import APP_NAME, APP_VERSION
from .i18n import TrMixin, i18n, tr
from .icon import app_icon
from .theme import THEMES, theme
from .widgets import (
    AnimatedSlider,
    Card,
    Dialog,
    FancyButton,
    FramelessWindow,
    GradientLabel,
    IconButton,
    Logo,
    Page,
    Segmented,
    SettingRow,
    Sidebar,
    SliderControl,
    Swatches,
    ThemedLabel,
    Toggle,
)

NAV = [
    ("home", "nav_general"),
    ("palette", "nav_appearance"),
    ("bolt", "nav_performance"),
    ("cube", "nav_graphics"),
    ("flag", "nav_fastflags"),
    ("info", "nav_about"),
]
FLAGS_INDEX = 4


def toggle_for(key, after=None):
    toggle = Toggle(bool(cfg.get(key)))

    def changed(state):
        cfg.set(key, state)
        if after:
            after(state)

    toggle.toggled.connect(changed)
    return toggle


def pref_toggle(preset_id):
    toggle = Toggle(bool(cfg.graphic(preset_id, flagmod.BY_ID[preset_id].default)))
    toggle.toggled.connect(lambda state: cfg.set_graphic(preset_id, state))
    return toggle


def pref_choice(preset_id):
    preset = flagmod.BY_ID[preset_id]
    current = flagmod.preset_value(preset, cfg.data["graphics"])
    seg = Segmented([(o.id, o.key) for o in preset.options], current)
    seg.valueChanged.connect(lambda value: cfg.set_graphic(preset_id, value))
    return seg


class GeneralPage(Page):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.heading("nav_general", "general_sub")

        lang = Segmented([("en", "lang_en"), ("ru", "lang_ru")], i18n.lang)
        lang.valueChanged.connect(i18n.set_language)
        self.add(SettingRow("set_language", "set_language_d", lang, "globe"))

        self.add(SettingRow("set_close", "set_close_d", toggle_for("close_on_launch"), "play"))
        self.add(SettingRow("set_auto_cleanup", "set_auto_cleanup_d", toggle_for("auto_cleanup"), "trash"))
        self.add(SettingRow("set_auto_install", "set_auto_install_d", toggle_for("auto_install"), "download"))
        if hasattr(tweaks, "set_protocol_handler"):
            self.add(SettingRow("set_protocol", "set_protocol_d", toggle_for("register_protocol", self._protocol), "flag"))

        self.group("grp_install")
        self.path_label = ThemedLabel("", "sub", 9.0, False, True)
        browse = FancyButton(tr("btn_browse"), "folder", "ghost", 40)
        browse.clicked.connect(self._browse)
        self.browse = browse
        row = SettingRow("set_location", None, browse, "folder")
        row.layout().itemAt(0).layout().addWidget(self.path_label)
        self.add(row)
        self._refresh_path()

        self.rows = {}
        for kind in ("player", "studio"):
            self._kind_row(kind)
        self._old_row()

        self.finish()
        cfg.changed.connect(self._cfg_changed)
        ctrl.cleaned.connect(self._refresh_old)
        i18n.changed.connect(self._retr)

    def _retr(self):
        self.browse.setText(tr("btn_browse"))
        self._refresh_all()

    def _protocol(self, state):
        if not tweaks.set_protocol_handler(state):
            QTimer.singleShot(0, lambda: cfg.set("register_protocol", False))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, tr("set_location"), str(cfg.install_root()))
        if path:
            cfg.set("install_root", path)
            self._refresh_path()

    def _refresh_path(self):
        self.path_label.setText(str(cfg.install_root()))

    def _kind_row(self, kind):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        reinstall = FancyButton("", "refresh", "ghost", 40)
        remove = FancyButton("", "trash", "danger", 40)
        reinstall.clicked.connect(lambda: self.ctrl.reinstall(kind))
        remove.clicked.connect(lambda: self._remove(kind))
        lay.addWidget(reinstall)
        lay.addWidget(remove)
        row = SettingRow("name_" + kind, None, box, "cube" if kind == "studio" else "play")
        status = ThemedLabel("", "sub", 9.0, False, True)
        row.layout().itemAt(0).layout().addWidget(status)
        self.add(row)
        self.rows[kind] = (status, reinstall, remove)
        self._refresh_kind(kind)

    def _old_row(self):
        self.clean_btn = FancyButton(tr("btn_cleanup"), "trash", "ghost", 40)
        self.clean_btn.clicked.connect(self._cleanup)
        row = SettingRow("set_old_versions", None, self.clean_btn, "trash")
        self.old_status = ThemedLabel("", "sub", 9.0, False, True)
        row.layout().itemAt(0).layout().addWidget(self.old_status)
        self.add(row)
        self._refresh_old()

    def _refresh_old(self):
        found = installer.old_versions()
        if found:
            size = sum(installer.dir_size(path) for path in found)
            self.old_status.setText(tr("old_found", n=len(found), size=installer.format_size(size)))
        else:
            self.old_status.setText(tr("old_none"))
        self.clean_btn.setText(tr("btn_cleanup"))
        self.clean_btn.setEnabled(bool(found))

    def _cleanup(self):
        self.clean_btn.setEnabled(False)
        self.ctrl.cleanup()

    def _remove(self, kind):
        ok, _ = Dialog.ask(
            self.window(),
            "warning",
            tr("dlg_remove_title", name=tr("name_" + kind)),
            tr("dlg_remove_text"),
            "btn_remove",
            "btn_cancel",
            danger=True,
        )
        if ok:
            self.ctrl.uninstall(kind)

    def _refresh_kind(self, kind):
        status, reinstall, remove = self.rows[kind]
        version = installer.installed_version(kind)
        status.setText(tr("inst_version", v=version[-12:]) if version else tr("inst_missing"))
        reinstall.setText(tr("btn_reinstall") if version else tr("btn_install"))
        reinstall.setGlyph("refresh" if version else "download")
        remove.setText(tr("btn_remove"))
        remove.setEnabled(bool(version))

    def _refresh_all(self):
        self._refresh_path()
        for kind in self.rows:
            self._refresh_kind(kind)
        self._refresh_old()

    def _cfg_changed(self, key):
        if key in ("installed", "install_root", "*"):
            self._refresh_all()


class AppearancePage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading("nav_appearance", "appearance_sub")

        themes = Segmented([(k, "theme_" + k) for k in THEMES], cfg.get("theme"))
        themes.valueChanged.connect(self._theme)
        self.add(SettingRow("set_theme", "set_theme_d", themes, "palette"))

        self.swatches = Swatches()
        self.swatches.picked.connect(self._accent)
        self.swatches.customRequested.connect(self._custom)
        self.add(SettingRow("set_accent", "set_accent_d", self.swatches, "palette"))

        radius = SliderControl(4, 30, 1, int(cfg.get("radius")), lambda v: f"{v} px")
        radius.valueChanged.connect(self._radius)
        self.add(SettingRow("set_radius", "set_radius_d", radius, "cube"))

        self.add(SettingRow("set_anim", "set_anim_d", toggle_for("animations"), "bolt"))

        speed = SliderControl(50, 200, 10, int(cfg.get("anim_speed")), lambda v: f"{v}%")
        speed.valueChanged.connect(lambda v: cfg.set("anim_speed", v))
        self.add(SettingRow("set_anim_speed", "set_anim_speed_d", speed, "refresh"))

        self.add(SettingRow("set_orbs", "set_orbs_d", toggle_for("orbs"), "globe"))

        opacity = SliderControl(60, 100, 5, int(cfg.get("opacity")), lambda v: f"{v}%")
        opacity.valueChanged.connect(lambda v: cfg.set("opacity", v))
        self.add(SettingRow("set_opacity", "set_opacity_d", opacity, "info"))
        self.finish()

    def _theme(self, value):
        cfg.set("theme", value)
        theme.apply()

    def _accent(self, value):
        cfg.set("accent", value)
        self.swatches.set_color(value)
        theme.apply()

    def _custom(self):
        color = QColorDialog.getColor(QColor(cfg.get("accent")), self.window(), tr("set_accent"))
        if color.isValid():
            self._accent(color.name())

    def _radius(self, value):
        cfg.set("radius", value)
        theme.apply()


class PerformancePage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading("nav_performance", "performance_sub")

        self.group("grp_profiles")
        card = Card()
        grid = QHBoxLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setSpacing(4)
        self.profile_buttons = []
        for name, glyph, variant in (
            ("balanced", "check", "ghost"),
            ("max_fps", "bolt", "primary"),
            ("quality", "palette", "secondary"),
            ("reset", "refresh", "ghost"),
        ):
            button = FancyButton(tr("prof_" + name), glyph, variant, 42)
            button.clicked.connect(lambda _=False, n=name: self._profile(n))
            self.profile_buttons.append((button, name))
            grid.addWidget(button)
        self.add(card)
        i18n.changed.connect(self._retr)

        self.group("grp_system")
        priority = Segmented([("normal", "prio_normal"), ("above", "prio_above"), ("high", "prio_high")], cfg.get("priority"))
        priority.valueChanged.connect(lambda v: cfg.set("priority", v))
        self.add(SettingRow("set_priority", "set_priority_d", priority, "bolt"))
        self.add(SettingRow("set_gpu", "set_gpu_d", toggle_for("gpu_high_performance"), "cube"))
        self.add(SettingRow("set_fso", "set_fso_d", toggle_for("disable_fso"), "play"))

        self.group("grp_render_tuning")
        self.fps = SliderControl(0, 1000, 10, int(cfg.graphic("fps", 0)), self._fps_text, 230)
        self.fps.valueChanged.connect(lambda v: cfg.set_graphic("fps", v))
        self.add(SettingRow("set_fps", "set_fps_d", self.fps, "refresh"))
        self.toggles = {}
        for pid, glyph in (("no_shadows", "cube"), ("no_postfx", "palette"), ("no_grass", "globe")):
            toggle = pref_toggle(pid)
            self.toggles[pid] = toggle
            self.add(SettingRow("p_" + pid, "p_" + pid + "_d", toggle, glyph))
        self.finish()
        cfg.changed.connect(self._cfg_changed)

    @staticmethod
    def _fps_text(value):
        if value <= 0:
            return tr("fps_default")
        if value >= 1000:
            return tr("fps_unlimited")
        return f"{value} FPS"

    def _retr(self):
        for button, name in self.profile_buttons:
            button.setText(tr("prof_" + name))
        self.fps.refresh_label()

    def _profile(self, name):
        prefs = flagmod.profile_prefs(name)
        if name == "reset":
            cfg.clear_graphics()
        else:
            for key, value in prefs.items():
                cfg.data["graphics"][key] = value
            cfg.touch("graphics")
        self._sync()

    def _sync(self):
        self.fps.setValue(int(cfg.graphic("fps", 0)))
        for pid, toggle in self.toggles.items():
            toggle.set_silent(bool(cfg.graphic(pid, False)))

    def _cfg_changed(self, key):
        if key in ("*",):
            self._sync()


class GraphicsPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading("nav_graphics", "graphics_sub")
        self.choices = {}
        self.toggles = {}
        self.group("grp_pipeline")
        for pid, glyph in (("api", "cube"), ("lighting", "bolt"), ("msaa", "palette"), ("texture", "globe")):
            control = pref_choice(pid)
            self.choices[pid] = control
            self.add(SettingRow("p_" + pid, "p_" + pid + "_d", control, glyph))
        self.group("grp_window")
        for pid, glyph in (("no_dpi", "info"), ("alt_enter", "play"), ("hide_bar", "minimize")):
            toggle = pref_toggle(pid)
            self.toggles[pid] = toggle
            self.add(SettingRow("p_" + pid, "p_" + pid + "_d", toggle, glyph))
        self.finish()
        cfg.changed.connect(self._cfg_changed)

    def _cfg_changed(self, key):
        if key in ("graphics", "*"):
            for pid, control in self.choices.items():
                control.set_value(flagmod.preset_value(flagmod.BY_ID[pid], cfg.data["graphics"]))
            for pid, toggle in self.toggles.items():
                toggle.set_silent(bool(cfg.graphic(pid, False)))


class FlagsPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading("nav_fastflags", "flags_sub")

        self.summary = ThemedLabel("", "accent", 10.0, True, True)
        self.add(self.summary)

        card = Card()
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(8)
        self.name_edit = QLineEdit()
        self.value_edit = QLineEdit()
        self.value_edit.setFixedWidth(150)
        self.add_btn = FancyButton(tr("btn_add"), "plus", "primary", 38)
        row.addWidget(self.name_edit, 1)
        row.addWidget(self.value_edit)
        row.addWidget(self.add_btn)
        self.add(card)
        self.add_btn.clicked.connect(self._add)
        self.name_edit.returnPressed.connect(self.value_edit.setFocus)
        self.value_edit.returnPressed.connect(self._add)

        self.error = ThemedLabel("", "danger", 9.0, False, True)
        self.add(self.error, reveal=False)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFixedHeight(260)
        self.table.setFrameShape(QTableWidget.Shape.NoFrame)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 170)
        self.table.itemChanged.connect(self._edited)
        holder = Card()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(8, 6, 8, 8)
        hl.addWidget(self.table)
        self.add(holder)

        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.btn_delete = FancyButton("", "trash", "danger", 40)
        self.btn_import = FancyButton("", "download", "ghost", 40)
        self.btn_export = FancyButton("", "upload", "ghost", 40)
        self.btn_copy = FancyButton("", "copy", "ghost", 40)
        self.btn_clear = FancyButton("", "close", "ghost", 40)
        for button in (self.btn_delete, self.btn_import, self.btn_export, self.btn_copy, self.btn_clear):
            bar.addWidget(button)
        bar.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(bar)
        self.add(wrap)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_clear.clicked.connect(self._clear)

        self.finish()
        self._loading = False
        i18n.changed.connect(self._retr)
        self._retr()
        self._load()

    def _retr(self):
        self.name_edit.setPlaceholderText(tr("flag_name"))
        self.value_edit.setPlaceholderText(tr("flag_value"))
        self.add_btn.setText(tr("btn_add"))
        self.btn_delete.setText(tr("btn_delete"))
        self.btn_import.setText(tr("btn_import"))
        self.btn_export.setText(tr("btn_export"))
        self.btn_copy.setText(tr("btn_copy"))
        self.btn_clear.setText(tr("btn_clear"))
        self.table.setHorizontalHeaderLabels([tr("flag_name"), tr("flag_value")])
        self._summary()

    def _summary(self):
        preset = len(flagmod.build_preset_flags(cfg.data["graphics"]))
        custom = len(cfg.data["custom_flags"])
        self.summary.setText(tr("flags_summary", preset=preset, custom=custom))

    def _load(self):
        self._loading = True
        self.table.setRowCount(0)
        for name, value in sorted(cfg.data["custom_flags"].items()):
            self._append(name, value)
        self._loading = False
        self._summary()

    def _append(self, name, value):
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, QTableWidgetItem(flagmod.format_value(value)))
        self.table.setRowHeight(row, 40)

    def _error(self, key=""):
        self.error.setText(tr(key) if key else "")

    def _add(self):
        name = self.name_edit.text().strip()
        raw = self.value_edit.text()
        if not flagmod.valid_name(name):
            self._error("err_flag_name")
            return
        if not raw.strip():
            self._error("err_flag_value")
            return
        self._error()
        cfg.data["custom_flags"][name] = flagmod.parse_value(raw)
        cfg.touch("custom_flags")
        self.name_edit.clear()
        self.value_edit.clear()
        self.name_edit.setFocus()
        self._load()

    def _edited(self, item):
        if self._loading or item.column() != 1:
            return
        name = self.table.item(item.row(), 0).text()
        text = item.text()
        if not text.strip():
            self._load()
            return
        cfg.data["custom_flags"][name] = flagmod.parse_value(text)
        cfg.touch("custom_flags")
        self._summary()

    def _delete(self):
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        for row in rows:
            name = self.table.item(row, 0).text()
            cfg.data["custom_flags"].pop(name, None)
        if rows:
            cfg.touch("custom_flags")
            self._load()

    def _clear(self):
        if not cfg.data["custom_flags"]:
            return
        ok, _ = Dialog.ask(self.window(), "warning", tr("dlg_clear_title"), tr("dlg_clear_text"), "btn_clear", "btn_cancel", danger=True)
        if ok:
            cfg.data["custom_flags"] = {}
            cfg.touch("custom_flags")
            self._load()

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("btn_import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            loaded = flagmod.load_flags_file(path)
        except (OSError, ValueError):
            self._error("err_flag_file")
            return
        self._error()
        cfg.data["custom_flags"].update(loaded)
        cfg.touch("custom_flags")
        self._load()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("btn_export"), "ClientAppSettings.json", "JSON (*.json)")
        if not path:
            return
        merged = flagmod.build_flags(cfg.data["graphics"], cfg.data["custom_flags"])
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(flagmod.dump_flags(merged))
        except OSError:
            self._error("err_flag_file")

    def _copy(self):
        merged = flagmod.build_flags(cfg.data["graphics"], cfg.data["custom_flags"])
        QGuiApplication.clipboard().setText(flagmod.dump_flags(merged))

    def refresh(self):
        self._load()


class AboutPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading("nav_about")
        card = Card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(4)
        lay.addWidget(Logo(96), 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(GradientLabel(APP_NAME, 26.0), 0, Qt.AlignmentFlag.AlignHCenter)
        self.version = ThemedLabel("", "sub", 10.0)
        self.version.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.version)
        lay.addSpacing(10)
        self.text = ThemedLabel("", "text", 10.0, False, True)
        self.text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.text)
        lay.addSpacing(6)
        self.note = ThemedLabel("", "sub", 9.0, False, True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.note)
        self.add(card)
        self.finish()
        i18n.changed.connect(self._retr)
        self._retr()

    def _retr(self):
        self.version.setText(tr("about_version", v=APP_VERSION))
        self.text.setText(tr("about_text"))
        self.note.setText(tr("about_note"))


class SettingsWindow(TrMixin, FramelessWindow):
    def __init__(self, ctrl):
        super().__init__()
        self.init_tr()
        self.setup_frame(orbs=True, drag_height=64)
        self.setWindowTitle(f"{APP_NAME} - " + tr("btn_settings"))
        self.setWindowIcon(app_icon())
        self.resize(1000, 700)
        self.setMinimumSize(900, 620)
        self._warned = False
        self._last = 0

        m = self.MARGIN
        root = QVBoxLayout(self)
        root.setContentsMargins(m + 18, m + 12, m + 18, m + 16)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(6, 0, 0, 0)
        logo = GradientLabel(APP_NAME, 16.0)
        top.addWidget(logo)
        top.addStretch(1)
        self.min_btn = IconButton("minimize")
        self.close_btn = IconButton("close", danger=True)
        self.min_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)
        top.addWidget(self.min_btn)
        top.addWidget(self.close_btn)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.sidebar = Sidebar(NAV)
        body.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.pages = [
            GeneralPage(ctrl),
            AppearancePage(),
            PerformancePage(),
            GraphicsPage(),
            FlagsPage(),
            AboutPage(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.sidebar.requested.connect(self.go)
        self.sidebar.set_current(0, animate=False)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(60, lambda: self.pages[self.stack.currentIndex()].reveal())

    def go(self, index):
        if index == self.stack.currentIndex():
            return
        if index == FLAGS_INDEX and not self._warned:
            ok, _ = Dialog.ask(
                self,
                "warning",
                tr("warn_title"),
                tr("warn_text"),
                "warn_ok",
                "warn_back",
                danger=True,
                countdown=5,
            )
            if not ok:
                return
            self._warned = True
        self._last = self.stack.currentIndex()
        self.sidebar.set_current(index)
        self.stack.setCurrentIndex(index)
        page = self.pages[index]
        if hasattr(page, "refresh"):
            page.refresh()
        page.reveal()
