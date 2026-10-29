import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lumora.config import cfg
from lumora.constants import APP_NAME
from lumora.controller import Controller
from lumora.icon import app_icon
from lumora.launcher import kind_for_uri
from lumora.settings_window import SettingsWindow
from lumora.splash import LauncherWindow
from lumora.tweaks import ensure_protocol
from lumora.theme import theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    theme.apply()
    ensure_protocol()

    controller = Controller()
    window = LauncherWindow(controller)
    controller.window = window
    state = {"settings": None}

    def open_settings():
        win = state["settings"]
        if win is None:
            win = SettingsWindow(controller)
            win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            win.destroyed.connect(lambda: state.update(settings=None))
            state["settings"] = win
        win.show()
        win.raise_()
        win.activateWindow()

    window.btn_settings.clicked.connect(open_settings)
    window.show()

    uri = next((a for a in sys.argv[1:] if kind_for_uri(a)), "")
    if uri:
        controller.launch(kind_for_uri(uri), uri)

    code = app.exec()
    cfg.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
