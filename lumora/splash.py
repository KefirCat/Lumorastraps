from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

from .constants import APP_NAME
from .i18n import TrMixin, tr
from .icon import app_icon
from .widgets import (
    FancyButton,
    FramelessWindow,
    GradientLabel,
    IconButton,
    Logo,
    ProgressBar,
    ThemedLabel,
    fade_stagger,
)


class LauncherWindow(TrMixin, FramelessWindow):
    def __init__(self, controller):
        super().__init__()
        self.init_tr()
        self.setup_frame(orbs=True)
        self.ctrl = controller
        self._state = ("st_ready", "")
        self._staged = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setFixedSize(680, 340)

        m = self.MARGIN
        root = QVBoxLayout(self)
        root.setContentsMargins(m + 24, m + 12, m + 24, m + 18)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        top.addStretch(1)
        self.min_btn = IconButton("minimize")
        self.close_btn = IconButton("close", danger=True)
        self.min_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(QApplication.quit)
        top.addWidget(self.min_btn)
        top.addWidget(self.close_btn)
        root.addLayout(top)

        main = QHBoxLayout()
        main.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(0)
        left.addStretch(1)
        self.logo = Logo(72)
        left.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.name = GradientLabel(APP_NAME, 28.0)
        left.addWidget(self.name, 0, Qt.AlignmentFlag.AlignHCenter)
        self.tag = ThemedLabel("", "sub", 9.5)
        self.t(self.tag.setText, "tagline")
        left.addSpacing(4)
        left.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addStretch(1)
        main.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addStretch(1)
        self.btn_player = FancyButton("", "play", "primary", 46, "left")
        self.btn_studio = FancyButton("", "cube", "secondary", 46, "left")
        self.btn_settings = FancyButton("", "gear", "ghost", 46, "left")
        self.t(self.btn_player.setText, "btn_launch_player")
        self.t(self.btn_studio.setText, "btn_launch_studio")
        self.t(self.btn_settings.setText, "btn_settings")
        for button in (self.btn_player, self.btn_studio, self.btn_settings):
            button.setFixedWidth(272)
            right.addWidget(button)
        right.addStretch(1)
        main.addLayout(right)
        root.addLayout(main, 1)

        self.status = ThemedLabel("", "sub", 9.0)
        self.bar = ProgressBar()
        root.addWidget(self.status)
        root.addSpacing(7)
        root.addWidget(self.bar)

        self.btn_player.clicked.connect(lambda: self.ctrl.launch("player"))
        self.btn_studio.clicked.connect(lambda: self.ctrl.launch("studio"))

        self.ctrl.state.connect(self.set_state)
        self.ctrl.progress.connect(self._on_progress)
        self.ctrl.busy.connect(self._on_busy)
        self._render_state()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._staged:
            self._staged = True
            fade_stagger([self.logo], 60, 0, 520)
            fade_stagger([self.btn_player, self.btn_studio, self.btn_settings], 200, 95, 460)

    def retranslate(self):
        super().retranslate()
        self._render_state()

    def set_state(self, key, detail=""):
        self._state = (key, detail)
        self._render_state()

    def _render_state(self):
        key, detail = self._state
        text = tr(key)
        if detail:
            text = f"{text}  ·  {detail}"
        self.status.setText(text)
        if key.startswith("err_"):
            self.status.setRole("danger")
        elif key == "st_launched":
            self.status.setRole("ok")
        else:
            self.status.setRole("sub")

    def _on_progress(self, fraction, key, detail):
        waiting = key in ("st_checking", "stage_manifest")
        self.bar.set_indeterminate(waiting)
        if not waiting:
            self.bar.set_value(fraction)
        self.set_state(key, detail)

    def _on_busy(self, busy, kind):
        for button, own in ((self.btn_player, "player"), (self.btn_studio, "studio")):
            button.setEnabled(not busy)
            button.setBusy(busy and own == kind)
        if busy:
            self.bar.set_indeterminate(True)
        else:
            self.bar.set_indeterminate(False)
            QTimer.singleShot(1600, self._idle_bar)

    def _idle_bar(self):
        if not self.ctrl.is_busy():
            self.bar.set_value(0.0)
