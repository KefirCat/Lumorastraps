import sys
from pathlib import Path

from .config import cfg
from .constants import FROZEN, IS_WINDOWS, PROTOCOL_SCHEMES, app_executable

FSO_FLAG = "DISABLEDXMAXIMIZEDWINDOWEDMODE"
LAYERS_PATH = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
GPU_PATH = r"Software\Microsoft\DirectX\UserGpuPreferences"
GPU_VALUE = "GpuPreference=2;"


def apply_exe_tweaks(exe: Path):
    if not IS_WINDOWS:
        return
    import winreg

    target = str(exe)

    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, LAYERS_PATH, 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                current = winreg.QueryValueEx(key, target)[0]
            except FileNotFoundError:
                current = ""
            tokens = [t for t in current.split() if t != "~"]
            has = FSO_FLAG in tokens
            if cfg.get("disable_fso") and not has:
                tokens.append(FSO_FLAG)
                winreg.SetValueEx(key, target, 0, winreg.REG_SZ, "~ " + " ".join(tokens))
            elif not cfg.get("disable_fso") and has:
                tokens.remove(FSO_FLAG)
                if tokens:
                    winreg.SetValueEx(key, target, 0, winreg.REG_SZ, "~ " + " ".join(tokens))
                else:
                    winreg.DeleteValue(key, target)
    except OSError:
        pass

    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, GPU_PATH, 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                current = winreg.QueryValueEx(key, target)[0]
            except FileNotFoundError:
                current = None
            if cfg.get("gpu_high_performance"):
                if current != GPU_VALUE:
                    winreg.SetValueEx(key, target, 0, winreg.REG_SZ, GPU_VALUE)
            elif current == GPU_VALUE:
                winreg.DeleteValue(key, target)
    except OSError:
        pass


def handler_command() -> str:
    if FROZEN:
        return f'"{app_executable()}" "%1"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    script = Path(sys.argv[0]).resolve()
    return f'"{interpreter}" "{script}" "%1"'


def set_protocol_handler(enable: bool):
    if not IS_WINDOWS:
        return False
    import winreg

    backup = dict(cfg.get("protocol_backup") or {})
    try:
        for scheme in PROTOCOL_SCHEMES:
            base = rf"Software\Classes\{scheme}"
            cmd_path = base + r"\shell\open\command"
            if enable:
                if scheme not in backup:
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
                            current = winreg.QueryValueEx(key, "")[0]
                    except FileNotFoundError:
                        current = ""
                    backup[scheme] = "" if current == handler_command() else current
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, base, 0, winreg.KEY_ALL_ACCESS) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL: {scheme} Protocol")
                    winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cmd_path, 0, winreg.KEY_ALL_ACCESS) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, handler_command())
            else:
                previous = backup.pop(scheme, None)
                if previous:
                    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cmd_path, 0, winreg.KEY_ALL_ACCESS) as key:
                        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, previous)
                else:
                    _delete_tree(winreg, winreg.HKEY_CURRENT_USER, base)
    except OSError:
        return False
    cfg.set("protocol_backup", backup)
    return True


def _delete_tree(winreg, root, path):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    sub = winreg.EnumKey(key, 0)
                except OSError:
                    break
                _delete_tree(winreg, root, path + "\\" + sub)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def ensure_protocol():
    if not IS_WINDOWS:
        return
    if not cfg.get("protocol_decided"):
        cfg.set("protocol_decided", True)
        cfg.set("register_protocol", True)
    if cfg.get("register_protocol"):
        set_protocol_handler(True)
