from PyQt6.QtCore import QObject, pyqtSignal

from .config import cfg
from .strings import STRINGS


class I18n(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.lang = cfg.get("language") if cfg.get("language") in STRINGS else "en"

    def set_language(self, lang: str):
        if lang not in STRINGS or lang == self.lang:
            return
        self.lang = lang
        cfg.set("language", lang)
        self.changed.emit()

    def tr(self, key: str, **kw) -> str:
        text = STRINGS[self.lang].get(key)
        if text is None:
            text = STRINGS["en"].get(key, key)
        if kw:
            try:
                return text.format(**kw)
            except (KeyError, IndexError):
                return text
        return text


i18n = I18n()
tr = i18n.tr


class TrMixin:
    def init_tr(self):
        self._tr_items = []
        i18n.changed.connect(self.retranslate)

    def t(self, setter, key, **kw):
        self._tr_items.append((setter, key, kw))
        setter(tr(key, **kw))

    def retranslate(self):
        for setter, key, kw in self._tr_items:
            setter(tr(key, **kw))
