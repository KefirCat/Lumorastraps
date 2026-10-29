import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from . import installer, launcher
from .config import cfg
from .constants import IS_WINDOWS
from .i18n import tr
from .widgets import Dialog


class Controller(QObject):
    state = pyqtSignal(str, str)
    progress = pyqtSignal(float, str, str)
    busy = pyqtSignal(bool, str)
    finished = pyqtSignal(str, bool, str, str)
    cleaned = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._busy = False
        self._cancel = threading.Event()
        self._old = {}
        self.window = None
        self.finished.connect(self._on_finished)

    def is_busy(self) -> bool:
        return self._busy

    def launch(self, kind: str, uri: str = ""):
        if self._busy:
            return
        if not IS_WINDOWS:
            self.state.emit("err_platform", "")
            return
        missing = installer.installed_version(kind) is None
        if missing and not cfg.get("auto_install"):
            ok, always = Dialog.ask(
                self.window,
                "download",
                tr("dlg_install_title", name=tr("name_" + kind)),
                tr("dlg_install_text", name=tr("name_" + kind)),
                "btn_install",
                "btn_cancel",
                check_key="chk_always_install",
            )
            if not ok:
                self.state.emit("st_cancelled", "")
                return
            if always:
                cfg.set("auto_install", True)
        self._begin(kind, uri, missing)

    def reinstall(self, kind: str):
        if self._busy or not IS_WINDOWS:
            return
        installer.uninstall(kind)
        self._begin(kind, "", True, launch_after=False)

    def uninstall(self, kind: str):
        if self._busy:
            return
        installer.uninstall(kind)
        self.state.emit("st_uninstalled", tr("name_" + kind))

    def cancel(self):
        self._cancel.set()

    def _begin(self, kind, uri, missing, launch_after=True):
        self._busy = True
        self._cancel = threading.Event()
        self.busy.emit(True, kind)
        self.progress.emit(0.0, "st_checking", "")
        thread = threading.Thread(target=self._work, args=(kind, uri, missing, launch_after), daemon=True)
        thread.start()

    def _emit_progress(self, fraction, key, detail):
        self.progress.emit(fraction, key, detail)

    def cleanup(self):
        def work():
            installer.cleanup_orphans()
            self.cleaned.emit()

        threading.Thread(target=work, daemon=True).start()

    def _work(self, kind, uri, missing, launch_after):
        error_key = ""
        error = ""
        try:
            current = installer.installed_version(kind)
            latest = None
            try:
                latest = installer.latest_version(kind)
            except installer.InstallError as exc:
                installer.log(f"version check failed: {exc}")
                if current is None:
                    raise
            if latest and (current is None or latest != current):
                replaced = installer.install(kind, latest, self._emit_progress, self._cancel)
                size = sum(installer.dir_size(path) for path in replaced)
                self._old[kind] = (replaced, size)
        except installer.Cancelled:
            error_key = "st_cancelled"
        except Exception as exc:
            error_key = "err_failed"
            error = str(exc)
            installer.log(f"work failed: {exc}")
        if error_key:
            self.finished.emit(kind, False, error_key, error)
        else:
            self.finished.emit(kind, True, "", uri + "\0" + ("1" if launch_after else "0"))

    def _offer_cleanup(self, kind, old, size):
        if not cfg.get("auto_cleanup"):
            accepted, always = Dialog.ask(
                self.window,
                "trash",
                tr("dlg_old_title"),
                tr(
                    "dlg_old_text",
                    name=tr("name_" + kind),
                    folders=", ".join(path.name for path in old),
                    size=installer.format_size(size),
                ),
                "btn_remove_old",
                "btn_keep",
                check_key="chk_auto_cleanup",
            )
            if not accepted:
                self.cleaned.emit()
                return
            if always:
                cfg.set("auto_cleanup", True)
        self._remove_async(old)

    def _remove_async(self, paths):
        def work():
            installer.remove_dirs(paths)
            self.cleaned.emit()

        threading.Thread(target=work, daemon=True).start()

    def _on_finished(self, kind, ok, error_key, payload):
        self._busy = False
        self.busy.emit(False, kind)
        if not ok:
            self.state.emit(error_key, payload if error_key == "err_failed" else "")
            return
        installer.sync_config(kind)
        cfg.flush()
        old, size = self._old.pop(kind, ([], 0))
        if old:
            self._offer_cleanup(kind, old, size)
        uri, _, flag = payload.partition("\0")
        if flag != "1":
            self.state.emit("stage_done", tr("name_" + kind))
            return
        try:
            launcher.start(kind, uri)
        except launcher.LaunchError as exc:
            reason = str(exc)
            if reason == "missing":
                self.state.emit("err_failed", "")
            else:
                self.state.emit("err_launch", reason)
            return
        self.state.emit("st_launched", tr("name_" + kind))
        if cfg.get("close_on_launch"):
            QTimer.singleShot(900, QApplication.quit)
