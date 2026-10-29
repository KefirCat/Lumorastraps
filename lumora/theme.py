from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor

from .config import cfg

THEMES = {
    "nova": {
        "dark": True,
        "bg1": "#020827",
        "bg2": "#0a2c78",
        "card": (255, 255, 255, 14),
        "card_hi": (255, 255, 255, 28),
        "border": (140, 190, 255, 38),
        "text": "#eaf3ff",
        "sub": "#8fb0e0",
        "a2_shift": -24,
        "a3_shift": 18,
    },
    "midnight": {
        "dark": True,
        "bg1": "#0d0e1b",
        "bg2": "#171935",
        "card": (255, 255, 255, 13),
        "card_hi": (255, 255, 255, 26),
        "border": (255, 255, 255, 24),
        "text": "#eef0ff",
        "sub": "#9aa1c9",
    },
    "amoled": {
        "dark": True,
        "bg1": "#000000",
        "bg2": "#0a0a12",
        "card": (255, 255, 255, 11),
        "card_hi": (255, 255, 255, 22),
        "border": (255, 255, 255, 20),
        "text": "#f4f4ff",
        "sub": "#8d90ad",
    },
    "light": {
        "dark": False,
        "bg1": "#f6f7fd",
        "bg2": "#e4e7f6",
        "card": (255, 255, 255, 150),
        "card_hi": (255, 255, 255, 230),
        "border": (30, 34, 80, 34),
        "text": "#15172b",
        "sub": "#5a5f86",
    },
    "aurora": {
        "dark": True,
        "bg1": "#07182a",
        "bg2": "#1c0f3a",
        "card": (255, 255, 255, 15),
        "card_hi": (255, 255, 255, 30),
        "border": (255, 255, 255, 28),
        "text": "#ecfbff",
        "sub": "#93b4cc",
    },
}

ACCENTS = ["#1f7bff", "#7c5cff", "#22d3ee", "#f43f8e", "#34d399", "#fbbf24", "#fb7185", "#60a5fa", "#a3e635"]


def with_alpha(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class Theme(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.refresh(emit=False)

    def refresh(self, emit=True):
        spec = THEMES.get(cfg.get("theme"), THEMES["midnight"])
        self.dark = spec["dark"]
        self.bg1 = QColor(spec["bg1"])
        self.bg2 = QColor(spec["bg2"])
        self.card = QColor(*spec["card"])
        self.card_hi = QColor(*spec["card_hi"])
        self.border = QColor(*spec["border"])
        self.text = QColor(spec["text"])
        self.sub = QColor(spec["sub"])
        accent = QColor(cfg.get("accent"))
        if not accent.isValid():
            accent = QColor("#7c5cff")
        self.accent = accent
        h, s, v, _ = accent.getHsv()
        shift2 = spec.get("a2_shift", 38)
        shift3 = spec.get("a3_shift", 300)
        self.accent2 = QColor.fromHsv((h + shift2) % 360, max(120, min(255, s)), min(255, v + 25))
        self.accent3 = QColor.fromHsv((h + shift3) % 360, max(120, min(255, s)), min(255, v + 10))
        self.danger = QColor("#ff5d73")
        self.ok = QColor("#34d399")
        self.radius = int(cfg.get("radius"))
        if emit:
            self.changed.emit()

    def apply(self):
        from PyQt6.QtWidgets import QApplication

        self.refresh(emit=False)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(self.qss())
        self.changed.emit()

    def qss(self) -> str:
        t = self.text.name()
        sub = self.sub.name()
        acc = self.accent.name()
        card = f"rgba({self.card.red()},{self.card.green()},{self.card.blue()},{self.card.alpha()})"
        hi = f"rgba({self.card_hi.red()},{self.card_hi.green()},{self.card_hi.blue()},{self.card_hi.alpha()})"
        bd = f"rgba({self.border.red()},{self.border.green()},{self.border.blue()},{self.border.alpha()})"
        pop = "#1b1d3a" if self.dark else "#ffffff"
        return f"""
        QToolTip {{ background: {pop}; color: {t}; border: 1px solid {bd}; padding: 6px 9px; border-radius: 8px; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
        QScrollBar::handle:vertical {{ background: {bd}; border-radius: 3px; min-height: 36px; margin: 0 2px; }}
        QScrollBar::handle:vertical:hover {{ background: {acc}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0; }}
        QLineEdit {{ background: {card}; color: {t}; border: 1px solid {bd}; border-radius: 10px; padding: 8px 12px; selection-background-color: {acc}; }}
        QLineEdit:focus {{ border: 1px solid {acc}; background: {hi}; }}
        QTableWidget {{ background: transparent; color: {t}; border: none; gridline-color: transparent; outline: 0; selection-background-color: transparent; }}
        QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {bd}; }}
        QTableWidget::item:selected {{ background: {hi}; color: {t}; }}
        QTableWidget QLineEdit {{ border-radius: 6px; padding: 4px 8px; }}
        QHeaderView {{ background: transparent; }}
        QHeaderView::section {{ background: transparent; color: {sub}; border: none; border-bottom: 1px solid {bd}; padding: 8px 10px; font-weight: 600; }}
        QTableCornerButton::section {{ background: transparent; border: none; }}
        QMenu {{ background: {pop}; color: {t}; border: 1px solid {bd}; border-radius: 10px; padding: 6px; }}
        QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
        QMenu::item:selected {{ background: {acc}; color: white; }}
        """


theme = Theme()
