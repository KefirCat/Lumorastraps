import hashlib
import json
import os
import shutil
import stat
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import flags as flagmod
from .config import cfg
from .constants import API_BASE, CDN_BASES, USER_AGENT, data_root


class InstallError(Exception):
    pass


class Cancelled(InstallError):
    pass


PLAYER_MAP = {
    "RobloxApp.zip": "",
    "shaders.zip": "shaders/",
    "ssl.zip": "ssl/",
    "WebView2.zip": "",
    "WebView2RuntimeInstaller.zip": "WebView2RuntimeInstaller/",
    "content-avatar.zip": "content/avatar/",
    "content-configs.zip": "content/configs/",
    "content-fonts.zip": "content/fonts/",
    "content-sky.zip": "content/sky/",
    "content-sounds.zip": "content/sounds/",
    "content-textures2.zip": "content/textures/",
    "content-models.zip": "content/models/",
    "content-textures3.zip": "PlatformContent/pc/textures/",
    "content-terrain.zip": "PlatformContent/pc/terrain/",
    "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
    "extracontent-translations.zip": "ExtraContent/translations/",
    "extracontent-models.zip": "ExtraContent/models/",
    "extracontent-textures.zip": "ExtraContent/textures/",
    "extracontent-places.zip": "ExtraContent/places/",
}

STUDIO_MAP = {
    "RobloxStudio.zip": "",
    "Libraries.zip": "",
    "LibrariesQt5.zip": "",
    "WebView2.zip": "",
    "WebView2RuntimeInstaller.zip": "",
    "shaders.zip": "shaders/",
    "ssl.zip": "ssl/",
    "Qml.zip": "Qml/",
    "Plugins.zip": "Plugins/",
    "StudioFonts.zip": "StudioFonts/",
    "BuiltInPlugins.zip": "BuiltInPlugins/",
    "ApplicationConfig.zip": "ApplicationConfig/",
    "BuiltInStandalonePlugins.zip": "BuiltInStandalonePlugins/",
    "content-qt_translations.zip": "content/qt_translations/",
    "content-sky.zip": "content/sky/",
    "content-fonts.zip": "content/fonts/",
    "content-avatar.zip": "content/avatar/",
    "content-models.zip": "content/models/",
    "content-sounds.zip": "content/sounds/",
    "content-configs.zip": "content/configs/",
    "content-api-docs.zip": "content/api_docs/",
    "content-textures2.zip": "content/textures/",
    "content-studio_svg_textures.zip": "content/studio_svg_textures/",
    "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
    "content-terrain.zip": "PlatformContent/pc/terrain/",
    "content-textures3.zip": "PlatformContent/pc/textures/",
    "extracontent-translations.zip": "ExtraContent/translations/",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
    "extracontent-textures.zip": "ExtraContent/textures/",
    "extracontent-scripts.zip": "ExtraContent/scripts/",
    "extracontent-models.zip": "ExtraContent/models/",
}


@dataclass(frozen=True)
class Kind:
    id: str
    binary_type: str
    exe: str
    package_map: dict


KINDS = {
    "player": Kind("player", "WindowsPlayer", "RobloxPlayerBeta.exe", PLAYER_MAP),
    "studio": Kind("studio", "WindowsStudio64", "RobloxStudioBeta.exe", STUDIO_MAP),
}

APP_SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<Settings>\n"
    "\t<ContentFolder>content</ContentFolder>\n"
    "\t<BaseUrl>http://www.roblox.com</BaseUrl>\n"
    "</Settings>\n"
)

MARKER = ".lumora-complete"


@dataclass
class Package:
    name: str
    md5: str
    size: int
    usize: int


def versions_dir() -> Path:
    path = cfg.install_root() / "Versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_valid(kind: str, path: Path) -> bool:
    return path.is_dir() and (path / KINDS[kind].exe).is_file() and (path / MARKER).is_file()


def _discover(kind: str):
    best = None
    best_stamp = -1.0
    try:
        entries = list(versions_dir().iterdir())
    except OSError:
        return None
    for entry in entries:
        if entry.name.startswith(".") or not _is_valid(kind, entry):
            continue
        try:
            stamp = (entry / MARKER).stat().st_mtime
        except OSError:
            continue
        if stamp > best_stamp:
            best, best_stamp = entry, stamp
    return best


def installed_dir(kind: str):
    recorded = cfg.get("install_paths").get(kind) or ""
    name = cfg.get("installed").get(kind) or ""
    if recorded:
        path = Path(recorded)
        if _is_valid(kind, path):
            if name != path.name:
                cfg.set_installed(kind, path.name, str(path))
            return path
    if name:
        path = versions_dir() / name
        if _is_valid(kind, path):
            cfg.set_installed(kind, path.name, str(path))
            return path
    found = _discover(kind)
    if found is not None:
        cfg.set_installed(kind, found.name, str(found))
        return found
    if name or recorded:
        cfg.set_installed(kind, "", "")
    return None


def installed_version(kind: str):
    path = installed_dir(kind)
    return path.name if path else None


def exe_path(kind: str):
    path = installed_dir(kind)
    return path / KINDS[kind].exe if path else None


def sync_config(kind: str, expected: str = "") -> bool:
    path = installed_dir(kind)
    if path is None:
        return False
    if expected and path.name != expected:
        return False
    recorded = cfg.get("install_paths").get(kind) or ""
    if recorded != str(path) or (cfg.get("installed").get(kind) or "") != path.name:
        cfg.set_installed(kind, path.name, str(path))
    return True


def dir_size(path: Path) -> int:
    total = 0
    for root, _, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def format_size(value: float) -> str:
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.1f} GB"
    return f"{value / 1024 ** 2:.0f} MB"


def _remove_tree(path) -> bool:
    def handler(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    try:
        shutil.rmtree(path, onexc=handler)
    except TypeError:
        shutil.rmtree(path, onerror=handler)
    except OSError:
        pass
    return not Path(path).exists()


def remove_dirs(paths) -> int:
    removed = 0
    for path in paths:
        if _remove_tree(path):
            removed += 1
    return removed


def old_versions():
    keep = set()
    for value in cfg.get("install_paths").values():
        if value:
            try:
                keep.add(Path(value).resolve())
            except OSError:
                pass
    found = []
    try:
        entries = list(versions_dir().iterdir())
    except OSError:
        return found
    for entry in entries:
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        if not (entry / MARKER).is_file():
            continue
        if entry.resolve() in keep:
            continue
        found.append(entry)
    return found


def _request(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def latest_version(kind: str, timeout: float = 8) -> str:
    url = f"{API_BASE}/v2/client-version/{KINDS[kind].binary_type}"
    try:
        with _request(url, timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise InstallError(str(exc)) from exc
    version = data.get("clientVersionUpload")
    if not isinstance(version, str) or not version:
        raise InstallError("bad version response")
    return version


def parse_manifest(text: str):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise InstallError("empty manifest")
    lines = lines[1:]
    packages = []
    for i in range(0, len(lines) - 3, 4):
        try:
            packages.append(Package(lines[i], lines[i + 1], int(lines[i + 2]), int(lines[i + 3])))
        except ValueError as exc:
            raise InstallError("bad manifest") from exc
    if not packages:
        raise InstallError("empty manifest")
    return packages


def _fetch_text(path: str) -> str:
    last = None
    for base in CDN_BASES:
        try:
            with _request(f"{base}/{path}") as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            last = exc
    raise InstallError(str(last))


OPTIONAL_PACKAGES = {"WebView2RuntimeInstaller.zip", "content-api-docs.zip"}
ATTEMPTS = 4


def log(message: str):
    try:
        with open(data_root() / "install.log", "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except OSError:
        pass


def cache_root() -> Path:
    return versions_dir() / ".cache"


def cache_dir(version: str) -> Path:
    path = cache_root() / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def prune_cache(version: str):
    root = cache_root()
    if not root.is_dir():
        return
    for entry in root.iterdir():
        if entry.name != version:
            shutil.rmtree(entry, ignore_errors=True)


def _md5_of(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, pkg: Package) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size == 0:
        return False
    if pkg.md5:
        return _md5_of(path).lower() == pkg.md5.lower()
    return pkg.size <= 0 or size == pkg.size


def _pause(seconds: float, cancel: threading.Event):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cancel.is_set():
            raise Cancelled("cancelled")
        time.sleep(0.1)


def _fetch_file(version: str, pkg: Package, dest: Path, on_bytes, cancel: threading.Event):
    part = dest.with_name(dest.name + ".part")
    last = None
    tries = 0
    for round_index in range(2):
        for base in CDN_BASES:
            tries += 1
            got = 0
            try:
                with _request(f"{base}/{version}-{pkg.name}", timeout=30) as resp, open(part, "wb") as out:
                    expected = resp.headers.get("Content-Length")
                    while True:
                        if cancel.is_set():
                            raise Cancelled("cancelled")
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)
                        got += len(chunk)
                        on_bytes(len(chunk))
                if expected and expected.isdigit() and got != int(expected):
                    raise InstallError(f"incomplete download ({got} of {expected} bytes)")
                if not _verify(part, pkg):
                    raise InstallError("checksum mismatch")
                os.replace(part, dest)
                return
            except Cancelled:
                part.unlink(missing_ok=True)
                raise
            except (InstallError, urllib.error.URLError, OSError, ValueError) as exc:
                if got:
                    on_bytes(-got)
                part.unlink(missing_ok=True)
                last = exc
                log(f"{pkg.name}: {base}: {exc}")
                _pause(min(0.7 * tries, 3.0), cancel)
    raise InstallError(str(last))


def _extract(zip_path: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/"):
                continue
            out = (target / name).resolve()
            if root != out and root not in out.parents:
                raise InstallError("unsafe archive entry")
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 256)


def _place(source: Path, pkg: Package, target: Path):
    if pkg.name.lower().endswith(".zip") and zipfile.is_zipfile(source):
        _extract(source, target)
        return
    if not pkg.md5:
        raise InstallError("not a valid archive")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target / pkg.name)


def _mb(value: float) -> str:
    return f"{value / 1048576:.1f}"


def install(kind: str, version: str, progress, cancel: threading.Event):
    info = KINDS[kind]
    progress(0.0, "stage_manifest", "")
    previous = installed_dir(kind)
    manifest = _fetch_text(f"{version}-rbxPkgManifest.txt")
    packages = parse_manifest(manifest)
    total = sum(max(p.size, 1) for p in packages)

    base = versions_dir()
    staging = base / f".{version}.partial"
    final = base / version
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    prune_cache(version)
    cache = cache_dir(version)

    done_bytes = [0]
    lock = threading.Lock()

    def on_bytes(delta: int):
        with lock:
            done_bytes[0] += delta
            frac = min(max(done_bytes[0] / total, 0.0), 1.0) * 0.9
            progress(frac, "stage_download", f"{_mb(max(done_bytes[0], 0))} / {_mb(total)} MB")

    def job(pkg: Package):
        dest = cache / pkg.name
        target = staging / info.package_map.get(pkg.name, "")
        counted = [0]

        def bump(delta: int):
            counted[0] += delta
            on_bytes(delta)

        last = None
        for attempt in range(ATTEMPTS):
            if cancel.is_set():
                raise Cancelled("cancelled")
            try:
                if dest.is_file() and _verify(dest, pkg):
                    if counted[0] == 0:
                        bump(dest.stat().st_size)
                else:
                    dest.unlink(missing_ok=True)
                    if counted[0]:
                        bump(-counted[0])
                    _fetch_file(version, pkg, dest, bump, cancel)
                _place(dest, pkg, target)
                return
            except Cancelled:
                raise
            except (InstallError, zipfile.BadZipFile, OSError) as exc:
                last = exc
                log(f"{pkg.name}: attempt {attempt + 1}: {exc}")
                if not isinstance(exc, OSError):
                    dest.unlink(missing_ok=True)
                _pause(1.0 + attempt, cancel)
        if pkg.name in OPTIONAL_PACKAGES:
            log(f"{pkg.name}: skipped")
            return
        raise InstallError(f"{pkg.name}: {last}")

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(job, pkg) for pkg in packages]
            try:
                for future in as_completed(futures):
                    future.result()
            except BaseException:
                cancel.set()
                for future in futures:
                    future.cancel()
                raise
        progress(0.94, "stage_finish", "")
        (staging / "AppSettings.xml").write_text(APP_SETTINGS_XML, encoding="utf-8")
        if not (staging / info.exe).is_file():
            raise InstallError(f"{info.exe} missing")
        (staging / MARKER).write_text(version, encoding="utf-8")
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        staging.rename(final)
    except BaseException as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if not isinstance(exc, Cancelled):
            log(f"install {kind} {version} failed: {exc}")
        raise

    shutil.rmtree(cache_root(), ignore_errors=True)
    if not cfg.set_installed(kind, version, str(final)):
        log(f"config write failed for {kind} {version}")
    progress(1.0, "stage_done", "")
    others = {Path(v).resolve() for k, v in cfg.get("install_paths").items() if v and k != kind}
    if previous is None or previous.resolve() == final.resolve() or previous.resolve() in others:
        return []
    return [previous]


def cleanup_orphans() -> int:
    removed = remove_dirs(old_versions())
    shutil.rmtree(cache_root(), ignore_errors=True)
    try:
        for entry in versions_dir().iterdir():
            if entry.name.endswith(".partial"):
                _remove_tree(entry)
    except OSError:
        pass
    return removed


def uninstall(kind: str):
    path = installed_dir(kind)
    if path is not None:
        _remove_tree(path)
    cfg.set_installed(kind, "", "")


def write_client_settings(kind: str):
    path = installed_dir(kind)
    if path is None:
        return None
    folder = path / "ClientSettings"
    target = folder / "ClientAppSettings.json"
    merged = flagmod.build_flags(cfg.get("graphics"), cfg.get("custom_flags"))
    if not merged:
        if target.exists():
            target.unlink()
        return None
    folder.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(merged, indent=4), encoding="utf-8")
    return target
