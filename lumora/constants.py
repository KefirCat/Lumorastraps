import os
import sys
from pathlib import Path

APP_NAME = "Lumora"
APP_VERSION = "1.0.0"
IS_WINDOWS = sys.platform == "win32"

API_BASE = os.environ.get("LUMORA_API", "https://clientsettings.roblox.com")

if os.environ.get("LUMORA_CDN"):
    CDN_BASES = [os.environ["LUMORA_CDN"].rstrip("/")]
else:
    CDN_BASES = [
        "https://setup.rbxcdn.com",
        "https://roblox-setup.cachefly.net",
        "https://s3.amazonaws.com/setup.roblox.com",
    ]

USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
PROTOCOL_SCHEMES = ("roblox-player", "roblox", "roblox-studio")


def data_root() -> Path:
    override = os.environ.get("LUMORA_HOME")
    if override:
        root = Path(override)
    else:
        if IS_WINDOWS:
            base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        else:
            base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        root = Path(base) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


COMPILED = "__compiled__" in globals()
FROZEN = COMPILED or bool(getattr(sys, "frozen", False))


def app_executable() -> str:
    if FROZEN:
        candidate = Path(sys.argv[0]).resolve()
        if candidate.suffix.lower() == ".exe" and candidate.is_file():
            return str(candidate)
    return sys.executable


def project_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    if FROZEN:
        return Path(app_executable()).parent
    return Path(__file__).resolve().parent.parent
