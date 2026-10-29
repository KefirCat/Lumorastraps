import copy
import json
import os
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .constants import data_root

DEFAULTS = {
    "language": "en",
    "theme": "nova",
    "accent": "#1f7bff",
    "radius": 16,
    "animations": True,
    "anim_speed": 100,
    "orbs": True,
    "opacity": 100,
    "install_root": "",
    "auto_install": False,
    "check_updates": True,
    "close_on_launch": False,
    "register_protocol": False,
    "protocol_decided": False,
    "protocol_backup": {},
    "priority": "normal",
    "gpu_high_performance": False,
    "disable_fso": False,
    "installed": {"player": "", "studio": ""},
    "install_paths": {"player": "", "studio": ""},
    "auto_cleanup": False,
    "graphics": {},
    "custom_flags": {},
}


def _merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict) and key not in ("graphics", "custom_flags", "protocol_backup"):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Config(QObject):
    changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.path = data_root() / "config.json"
        self.data = copy.deepcopy(DEFAULTS)
        self._lock = threading.RLock()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self.flush)
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = _merge(DEFAULTS, raw)
        except (OSError, ValueError):
            self.data = copy.deepcopy(DEFAULTS)

    def write_now(self) -> bool:
        with self._lock:
            payload = json.dumps(self.data, indent=2, ensure_ascii=False)
            tmp = self.path.with_suffix(".tmp")
            for attempt in range(8):
                try:
                    with open(tmp, "w", encoding="utf-8") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(tmp, self.path)
                    return True
                except OSError:
                    time.sleep(0.06 * (attempt + 1))
            return False

    def flush(self):
        self._timer.stop()
        self.write_now()

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default) if default is None else default)

    def set(self, key, value):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self.changed.emit(key)
        self._timer.start()

    def touch(self, key):
        self.changed.emit(key)
        self._timer.start()

    def graphic(self, preset_id, default=None):
        return self.data["graphics"].get(preset_id, default)

    def set_graphic(self, preset_id, value):
        self.data["graphics"][preset_id] = value
        self.touch("graphics")

    def clear_graphics(self):
        self.data["graphics"] = {}
        self.touch("graphics")

    def set_installed(self, kind, version, path=""):
        with self._lock:
            self.data["installed"][kind] = version
            self.data["install_paths"][kind] = path
            saved = self.write_now()
        self.changed.emit("installed")
        return saved

    def reset(self):
        keep = {
            "installed": copy.deepcopy(self.data["installed"]),
            "install_paths": copy.deepcopy(self.data["install_paths"]),
            "install_root": self.data["install_root"],
        }
        self.data = copy.deepcopy(DEFAULTS)
        self.data.update(keep)
        self.changed.emit("*")
        self.flush()

    def install_root(self) -> Path:
        custom = self.data.get("install_root")
        root = Path(custom) if custom else data_root()
        root.mkdir(parents=True, exist_ok=True)
        return root


cfg = Config()
