from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation

from .config import cfg


def enabled() -> bool:
    return bool(cfg.get("animations"))


def dur(ms: int) -> int:
    if not enabled():
        return 0
    speed = max(25, min(300, int(cfg.get("anim_speed")))) / 100.0
    return int(ms / speed)


def animate(target, prop: bytes, start, end, ms: int = 220, easing=QEasingCurve.Type.OutCubic):
    holder = target.__dict__.setdefault("_running_anims", {})
    old = holder.get(prop)
    if old is not None:
        old.stop()
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(dur(ms))
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    holder[prop] = anim
    anim.start()
    return anim


def value_anim(parent, start, end, ms, callback, easing=QEasingCurve.Type.OutCubic, finished=None):
    anim = QVariantAnimation(parent)
    anim.setDuration(dur(ms))
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    anim.valueChanged.connect(callback)
    if finished is not None:
        anim.finished.connect(finished)
    anim.start()
    return anim
