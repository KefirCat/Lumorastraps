import subprocess

from . import installer, tweaks
from .config import cfg
from .constants import IS_WINDOWS

ABOVE_NORMAL = 0x00008000
HIGH = 0x00000080

PRIORITY_FLAGS = {"normal": 0, "above": ABOVE_NORMAL, "high": HIGH}


class LaunchError(Exception):
    pass


def kind_for_uri(uri: str):
    low = uri.lower()
    if low.startswith("roblox-studio:"):
        return "studio"
    if low.startswith("roblox-player:") or low.startswith("roblox:"):
        return "player"
    return None


def start(kind: str, uri: str = ""):
    if not IS_WINDOWS:
        raise LaunchError("platform")
    exe = installer.exe_path(kind)
    if exe is None:
        raise LaunchError("missing")
    installer.write_client_settings(kind)
    tweaks.apply_exe_tweaks(exe)
    args = [str(exe)]
    if uri:
        args.append(uri)
    elif kind == "player":
        args.append("--app")
    flags = PRIORITY_FLAGS.get(cfg.get("priority"), 0)
    try:
        subprocess.Popen(args, cwd=str(exe.parent), creationflags=flags, close_fds=True)
    except OSError as exc:
        raise LaunchError(str(exc)) from exc
