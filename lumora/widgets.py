import math
import random

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import anim
from .config import cfg
from .glyphs import draw_glyph
from .i18n import TrMixin, i18n, tr
from .icon import render_icon
from .theme import ACCENTS, mix, theme, with_alpha

WHITE = QColor(255, 255, 255)


def aa(p: QPainter):
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)


class Tweener:
    def tween(self, attr, target, ms=160, easing=QEasingCurve.Type.OutCubic):
        tweens = self.__dict__.setdefault("_tweens", {})
        old = tweens.get(attr)
        if old is not None:
            old.stop()
        if anim.dur(ms) == 0:
            setattr(self, attr, float(target))
            self.update()
            return

        def step(value, name=attr):
            setattr(self, name, float(value))
            self.update()

        tweens[attr] = anim.value_anim(self, float(getattr(self, attr)), float(target), ms, step, easing)


class ThemedLabel(QLabel):
    def __init__(self, text="", role="text", size=10.0, bold=False, wrap=False, parent=None):
        super().__init__(text, parent)
        self._role = role
        font = QFont(self.font())
        font.setPointSizeF(size)
        font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(wrap)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        theme.changed.connect(self._apply)
        self._apply()

    def setRole(self, role):
        self._role = role
        self._apply()

    def _apply(self):
        colors = {
            "text": theme.text,
            "sub": theme.sub,
            "accent": theme.accent,
            "danger": theme.danger,
            "ok": theme.ok,
        }
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, colors.get(self._role, theme.text))
        self.setPalette(palette)


class GradientLabel(QWidget):
    def __init__(self, text="", size=26.0, parent=None):
        super().__init__(parent)
        self._text = text
        self._size = size
        theme.changed.connect(self.update)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def setText(self, text):
        self._text = text
        self.updateGeometry()
        self.update()

    def _font(self):
        font = QFont(self.font())
        font.setPointSizeF(self._size)
        font.setWeight(QFont.Weight.Bold)
        return font

    def sizeHint(self):
        metrics = QFontMetrics(self._font())
        return QSize(metrics.horizontalAdvance(self._text) + 6, metrics.height() + 4)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        p.setFont(self._font())
        grad = QLinearGradient(0, 0, max(self.width(), 1), 0)
        grad.setColorAt(0.0, theme.text)
        grad.setColorAt(0.55, mix(theme.text, theme.accent2, 0.55))
        grad.setColorAt(1.0, theme.accent)
        p.setPen(QPen(QBrush(grad), 1))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)


class _Orb:
    def __init__(self, index):
        rnd = random.Random(index * 11 + 5)
        self.x = rnd.random()
        self.y = rnd.random()
        angle = rnd.random() * math.tau
        speed = 0.018 + rnd.random() * 0.022
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.r = 0.3 + rnd.random() * 0.22


class FrameMixin:
    MARGIN = 20

    def setup_frame(self, orbs=True, drag_height=None):
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._use_orbs = orbs
        self._drag_h = drag_height
        self._shadow = None
        self._entered = False
        self._orbs = [_Orb(i) for i in range(4)]
        self._orb_timer = QTimer(self)
        self._orb_timer.setInterval(33)
        self._orb_timer.timeout.connect(self._orb_tick)
        theme.changed.connect(self._rebuild_shadow)
        theme.changed.connect(self.update)
        cfg.changed.connect(self._frame_cfg)

    def body_rect(self):
        m = self.MARGIN
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def _frame_cfg(self, key):
        if key in ("orbs", "animations", "*"):
            self._sync_orbs()
            self.update()
        if key in ("opacity", "*"):
            self.setWindowOpacity(cfg.get("opacity") / 100.0)

    def _sync_orbs(self):
        if not hasattr(self, "_orb_timer"):
            return
        running = (
            self._use_orbs
            and cfg.get("orbs")
            and cfg.get("animations")
            and self.isVisible()
            and not self.isMinimized()
        )
        if running and not self._orb_timer.isActive():
            self._orb_timer.start()
        elif not running and self._orb_timer.isActive():
            self._orb_timer.stop()

    def _orb_tick(self):
        dt = 0.033
        for orb in self._orbs:
            orb.x += orb.vx * dt
            orb.y += orb.vy * dt
            if orb.x < -0.1 or orb.x > 1.1:
                orb.vx = -orb.vx
                orb.x = max(-0.1, min(1.1, orb.x))
            if orb.y < -0.1 or orb.y > 1.1:
                orb.vy = -orb.vy
                orb.y = max(-0.1, min(1.1, orb.y))
        self.update()

    def _rebuild_shadow(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        aa(p)
        body = self.body_rect().translated(0, 5)
        rad = theme.radius + 6
        strength = 95 if theme.dark else 50
        steps = self.MARGIN - 4
        for i in range(steps):
            t = i / steps
            alpha = int(strength * (1 - t) ** 2.4 * 0.5)
            p.setPen(QPen(QColor(0, 0, 0, alpha), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(body.adjusted(-i, -i, i, i), rad + i, rad + i)
        p.end()
        self._shadow = pm

    def resizeEvent(self, event):
        self._rebuild_shadow()
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        if self._shadow is not None:
            p.drawPixmap(0, 0, self._shadow)
        body = self.body_rect()
        rad = theme.radius + 6
        path = QPainterPath()
        path.addRoundedRect(body, rad, rad)
        grad = QLinearGradient(body.topLeft(), body.bottomRight())
        grad.setColorAt(0.0, theme.bg1)
        grad.setColorAt(1.0, theme.bg2)
        p.fillPath(path, QBrush(grad))
        if self._use_orbs and cfg.get("orbs"):
            p.save()
            p.setClipPath(path)
            base = max(body.width(), body.height())
            colors = [theme.accent, theme.accent2, theme.accent3, theme.accent]
            alpha = 80 if theme.dark else 62
            for orb, color in zip(self._orbs, colors):
                cx = body.left() + orb.x * body.width()
                cy = body.top() + orb.y * body.height()
                radius = orb.r * base
                g = QRadialGradient(QPointF(cx, cy), radius)
                g.setColorAt(0.0, with_alpha(color, alpha))
                g.setColorAt(1.0, with_alpha(color, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(cx, cy), radius, radius)
            p.restore()
        p.setPen(QPen(theme.border, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            y = event.position().y() - self.MARGIN
            if self._drag_h is None or y <= self._drag_h:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
        super().mousePressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_orbs()
        if not self._entered:
            self._entered = True
            QTimer.singleShot(0, self.fade_in)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_orbs()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_orbs()

    def fade_in(self):
        target = cfg.get("opacity") / 100.0
        if not anim.enabled():
            self.setWindowOpacity(target)
            return
        end = self.pos()
        self.setWindowOpacity(0.0)
        self.move(end + QPoint(0, 18))
        group = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(anim.dur(380))
        fade.setStartValue(0.0)
        fade.setEndValue(target)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(anim.dur(460))
        slide.setStartValue(end + QPoint(0, 18))
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.Type.OutBack)
        group.addAnimation(fade)
        group.addAnimation(slide)
        self._entry_group = group
        group.start()


class FramelessWindow(FrameMixin, QWidget):
    pass


class IconButton(QAbstractButton, Tweener):
    def __init__(self, glyph, danger=False, size=30, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._danger = danger
        self._hover = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, event):
        self.tween("_hover", 1.0, 140)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tween("_hover", 0.0, 200)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        base = theme.danger if self._danger else theme.accent
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(with_alpha(base, int(150 * self._hover)) if self._danger else mix(QColor(0, 0, 0, 0), theme.card_hi, self._hover))
        p.drawEllipse(r)
        color = mix(theme.sub, WHITE if self._danger else theme.text, self._hover)
        draw_glyph(p, self._glyph, r.adjusted(7, 7, -7, -7), color, 2.2)


class FancyButton(QAbstractButton, Tweener):
    MARGIN = 6

    def __init__(self, text="", glyph=None, variant="primary", height=44, align="center", parent=None):
        super().__init__(parent)
        self._text = text
        self._glyph = glyph
        self._variant = variant
        self._h = height
        self._align = align
        self._hover = 0.0
        self._press = 0.0
        self._ripple = 1.0
        self._ripple_pos = QPointF()
        self._busy = False
        self._spin = 0.0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._spin_step)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        theme.changed.connect(self.update)

    def setText(self, text):
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def setGlyph(self, glyph):
        self._glyph = glyph
        self.update()

    def setBusy(self, busy):
        self._busy = busy
        if busy:
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
        self.update()

    def _spin_step(self):
        self._spin = (self._spin + 9) % 360
        self.update()

    def _font(self):
        font = QFont(self.font())
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def sizeHint(self):
        metrics = QFontMetrics(self._font())
        width = metrics.horizontalAdvance(self._text) + 44 + (28 if self._glyph else 0)
        return QSize(width + 2 * self.MARGIN, self._h + 2 * self.MARGIN)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, event):
        self.tween("_hover", 1.0, 150)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tween("_hover", 0.0, 220)
        self.tween("_press", 0.0, 120)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._ripple_pos = event.position()
            self._ripple = 0.0
            self.tween("_ripple", 1.0, 620, QEasingCurve.Type.OutQuad)
            self.tween("_press", 1.0, 80)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.tween("_press", 0.0, 160, QEasingCurve.Type.OutBack)
        super().mouseReleaseEvent(event)

    def _colors(self):
        v = self._variant
        if v == "primary":
            return theme.accent, theme.accent2
        if v == "secondary":
            return theme.accent3, theme.accent
        if v == "danger":
            return QColor("#ff4d6d"), QColor("#ff8a5c")
        return None

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        m = self.MARGIN
        r = QRectF(self.rect()).adjusted(m, m, -m, -m)
        r.translate(0, -1.6 * self._hover + 1.2 * self._press)
        rad = min(float(theme.radius), r.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        if not self.isEnabled() and not self._busy:
            p.setOpacity(0.45)
        colors = self._colors()
        if colors:
            c1, c2 = colors
            if self._hover > 0.01:
                for i in range(1, 7):
                    a = int(46 * self._hover * (1 - i / 7.0) ** 1.5)
                    p.setPen(QPen(with_alpha(c1, a), 1.6))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(r.adjusted(-i, -i, i, i), rad + i, rad + i)
            grad = QLinearGradient(r.topLeft(), r.topRight())
            grad.setColorAt(0.0, mix(c1, WHITE, 0.14 * self._hover))
            grad.setColorAt(1.0, mix(c2, WHITE, 0.14 * self._hover))
            p.fillPath(path, QBrush(grad))
            p.save()
            p.setClipPath(path)
            gloss = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))
            gloss.setColorAt(0.0, QColor(255, 255, 255, 52))
            gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(r.left(), r.top(), r.width(), r.height() / 2), QBrush(gloss))
            p.restore()
            fg = WHITE
        else:
            p.fillPath(path, mix(theme.card, theme.card_hi, self._hover))
            p.setPen(QPen(mix(theme.border, theme.accent, 0.55 * self._hover), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            fg = theme.text
        if self._ripple < 1.0:
            p.save()
            p.setClipPath(path)
            radius = self._ripple * r.width() * 0.9
            ripple_color = QColor(255, 255, 255, int(70 * (1 - self._ripple))) if colors else with_alpha(theme.accent, int(70 * (1 - self._ripple)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ripple_color)
            p.drawEllipse(self._ripple_pos + QPointF(0, 0), radius, radius)
            p.restore()
        if self.hasFocus() and self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            p.setPen(QPen(with_alpha(theme.accent2, 200), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), rad + 2, rad + 2)
        font = self._font()
        p.setFont(font)
        metrics = QFontMetrics(font)
        text_w = metrics.horizontalAdvance(self._text)
        icon = 20.0 if (self._glyph or self._busy) else 0.0
        gap = 11.0 if icon else 0.0
        total = icon + gap + text_w
        x = r.left() + 20 if self._align == "left" else r.center().x() - total / 2
        cy = r.center().y()
        if icon:
            box = QRectF(x, cy - icon / 2, icon, icon)
            if self._busy:
                pen = QPen(fg, 2.2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(box.adjusted(2, 2, -2, -2), int(-self._spin * 16), 270 * 16)
            else:
                draw_glyph(p, self._glyph, box, fg, 2.1)
        p.setPen(fg)
        p.drawText(
            QRectF(x + icon + gap, r.top(), text_w + 4, r.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )


class Toggle(QAbstractButton, Tweener):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self._hover = 0.0
        self.setFixedSize(54, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.toggled.connect(self._on_toggled)
        theme.changed.connect(self.update)

    def _on_toggled(self, state):
        self.tween("_pos", 1.0 if state else 0.0, 300, QEasingCurve.Type.OutBack)

    def set_silent(self, value):
        self.blockSignals(True)
        self.setChecked(value)
        self.blockSignals(False)
        self._pos = 1.0 if value else 0.0
        self.update()

    def enterEvent(self, event):
        self.tween("_hover", 1.0, 140)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tween("_hover", 0.0, 200)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        if not self.isEnabled():
            p.setOpacity(0.4)
        r = QRectF(self.rect()).adjusted(2, 4, -2, -4)
        t = max(0.0, min(1.0, self._pos))
        off = mix(theme.border, theme.card_hi, 0.6)
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0.0, mix(off, theme.accent, t))
        grad.setColorAt(1.0, mix(off, theme.accent2, t))
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(mix(theme.border, with_alpha(theme.accent2, 160), t), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        knob = r.height() - 7
        x = r.left() + 3.5 + t * (r.width() - knob - 7)
        cy = r.center().y()
        if self._hover > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(WHITE, int(34 * self._hover)))
            p.drawEllipse(QPointF(x + knob / 2, cy), knob / 2 + 4, knob / 2 + 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawEllipse(QPointF(x + knob / 2, cy + 1.4), knob / 2, knob / 2)
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(x + knob / 2, cy), knob / 2, knob / 2)
        if self.hasFocus():
            p.setPen(QPen(with_alpha(theme.accent2, 200), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), r.height() / 2 + 2, r.height() / 2 + 2)


class AnimatedSlider(QWidget, Tweener):
    valueChanged = pyqtSignal(int)

    PAD = 14

    def __init__(self, lo, hi, step=1, value=None, parent=None):
        super().__init__(parent)
        self._lo = lo
        self._hi = hi
        self._step = max(1, step)
        self._value = lo if value is None else value
        self._vis = self._frac(self._value)
        self._hover = 0.0
        self._drag = 0.0
        self._dragging = False
        self.setFixedHeight(34)
        self.setMinimumWidth(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMouseTracking(True)
        theme.changed.connect(self.update)

    def _frac(self, value):
        return (value - self._lo) / float(self._hi - self._lo)

    def value(self):
        return self._value

    def setValue(self, value, emit=False, animate=True):
        value = self._snap(value)
        if value == self._value:
            return
        self._value = value
        if animate and not self._dragging:
            self.tween("_vis", self._frac(value), 200)
        else:
            self._vis = self._frac(value)
            self.update()
        if emit:
            self.valueChanged.emit(value)

    def _snap(self, value):
        value = round((value - self._lo) / self._step) * self._step + self._lo
        return int(max(self._lo, min(self._hi, value)))

    def _from_x(self, x):
        span = max(1.0, self.width() - 2 * self.PAD)
        frac = max(0.0, min(1.0, (x - self.PAD) / span))
        return self._snap(self._lo + frac * (self._hi - self._lo))

    def enterEvent(self, event):
        self.tween("_hover", 1.0, 140)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tween("_hover", 0.0, 200)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.tween("_drag", 1.0, 120)
            self.setValue(self._from_x(event.position().x()), emit=True, animate=False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.setValue(self._from_x(event.position().x()), emit=True, animate=False)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.tween("_drag", 0.0, 220)
        self._vis = self._frac(self._value)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.setValue(self._value + delta * self._step, emit=True)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.setValue(self._value - self._step, emit=True)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.setValue(self._value + self._step, emit=True)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        if not self.isEnabled():
            p.setOpacity(0.4)
        left = self.PAD
        right = self.width() - self.PAD
        cy = self.height() / 2.0
        groove = QRectF(left, cy - 3, right - left, 6)
        track = QPainterPath()
        track.addRoundedRect(groove, 3, 3)
        p.fillPath(track, mix(theme.border, theme.card_hi, 0.5))
        x = left + (right - left) * max(0.0, min(1.0, self._vis))
        fill = QRectF(left, cy - 3, max(0.0, x - left), 6)
        if fill.width() > 0:
            grad = QLinearGradient(groove.topLeft(), groove.topRight())
            grad.setColorAt(0.0, theme.accent)
            grad.setColorAt(1.0, theme.accent2)
            fp = QPainterPath()
            fp.addRoundedRect(fill, 3, 3)
            p.fillPath(fp, QBrush(grad))
        radius = 8.0 + 1.5 * self._hover + 1.5 * self._drag
        glow = max(self._hover * 0.5, self._drag)
        if glow > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(theme.accent2, int(70 * glow)))
            p.drawEllipse(QPointF(x, cy), radius + 6 * glow, radius + 6 * glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 55))
        p.drawEllipse(QPointF(x, cy + 1.3), radius, radius)
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(x, cy), radius, radius)
        p.setBrush(mix(theme.accent, theme.accent2, 0.5))
        p.drawEllipse(QPointF(x, cy), radius * 0.38, radius * 0.38)
        if self.hasFocus():
            p.setPen(QPen(with_alpha(theme.accent2, 200), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, cy), radius + 3, radius + 3)


class SliderControl(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, lo, hi, step=1, value=None, formatter=None, width=250, parent=None):
        super().__init__(parent)
        self._fmt = formatter or (lambda v: str(v))
        self.slider = AnimatedSlider(lo, hi, step, value)
        self.slider.setFixedWidth(width)
        self.label = ThemedLabel("", "accent", 10.0, True)
        self.label.setFixedWidth(84)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.slider)
        row.addWidget(self.label)
        self.slider.valueChanged.connect(self._changed)
        i18n.changed.connect(self.refresh_label)
        self.refresh_label()

    def _changed(self, value):
        self.refresh_label()
        self.valueChanged.emit(value)

    def refresh_label(self):
        self.label.setText(self._fmt(self.slider.value()))

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value, animate=False)
        self.refresh_label()


class Segmented(QWidget, Tweener):
    valueChanged = pyqtSignal(str)

    def __init__(self, options, value=None, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._index = 0
        if value is not None:
            ids = [o[0] for o in self._options]
            self._index = ids.index(value) if value in ids else 0
        self._pos = float(self._index)
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        i18n.changed.connect(self._relabel)
        theme.changed.connect(self.update)
        self._relabel()

    def _font(self):
        font = QFont(self.font())
        font.setPointSizeF(9.8)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _item_w(self):
        metrics = QFontMetrics(self._font())
        widest = max(metrics.horizontalAdvance(tr(o[1])) for o in self._options)
        return widest + 30

    def sizeHint(self):
        return QSize(self._item_w() * len(self._options) + 8, 40)

    def _relabel(self):
        self.setFixedSize(self.sizeHint())
        self.updateGeometry()
        self.update()

    def value(self):
        return self._options[self._index][0]

    def set_value(self, value, animate=True):
        ids = [o[0] for o in self._options]
        if value not in ids:
            return
        self._index = ids.index(value)
        if animate:
            self.tween("_pos", float(self._index), 320, QEasingCurve.Type.OutBack)
        else:
            self._pos = float(self._index)
            self.update()

    def _pick(self, index):
        index = max(0, min(len(self._options) - 1, index))
        if index == self._index:
            return
        self._index = index
        self.tween("_pos", float(index), 320, QEasingCurve.Type.OutBack)
        self.valueChanged.emit(self._options[index][0])

    def _index_at(self, x):
        return int((x - 4) // self._item_w())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(self._index_at(event.position().x()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        idx = self._index_at(event.position().x())
        if idx != self._hover:
            self._hover = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._pick(self._index - 1)
        elif event.key() == Qt.Key.Key_Right:
            self._pick(self._index + 1)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = min(float(theme.radius), outer.height() / 2)
        bg = QPainterPath()
        bg.addRoundedRect(outer, rad, rad)
        p.fillPath(bg, theme.card)
        p.setPen(QPen(theme.border, 1))
        p.drawPath(bg)
        item_w = self._item_w()
        pill = QRectF(4 + self._pos * item_w, 4, item_w, outer.height() - 7)
        grad = QLinearGradient(pill.topLeft(), pill.topRight())
        grad.setColorAt(0.0, theme.accent)
        grad.setColorAt(1.0, theme.accent2)
        pp = QPainterPath()
        pp.addRoundedRect(pill, max(4.0, rad - 3), max(4.0, rad - 3))
        p.fillPath(pp, QBrush(grad))
        p.setFont(self._font())
        for i, (_, key) in enumerate(self._options):
            near = max(0.0, 1.0 - abs(self._pos - i))
            base = mix(theme.sub, theme.text, 0.6 if i == self._hover else 0.0)
            p.setPen(mix(base, WHITE, near))
            p.drawText(QRectF(4 + i * item_w, 0, item_w, outer.height()), Qt.AlignmentFlag.AlignCenter, tr(key))
        if self.hasFocus():
            p.setPen(QPen(with_alpha(theme.accent2, 200), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(outer.adjusted(-1, -1, 1, 1), rad + 1, rad + 1)


class Swatches(QWidget, Tweener):
    picked = pyqtSignal(str)
    customRequested = pyqtSignal()

    SIZE = 30
    GAP = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = list(ACCENTS)
        self._current = cfg.get("accent")
        self._hover = -1
        self._ring = 1.0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        total = len(self._colors) + 1
        self.setFixedSize(total * self.SIZE + (total - 1) * self.GAP + 8, self.SIZE + 10)
        theme.changed.connect(self.update)

    def set_color(self, value):
        self._current = value
        self._ring = 0.0
        self.tween("_ring", 1.0, 360, QEasingCurve.Type.OutBack)

    def _rect(self, i):
        return QRectF(4 + i * (self.SIZE + self.GAP), 5, self.SIZE, self.SIZE)

    def _index_at(self, pos):
        for i in range(len(self._colors) + 1):
            if self._rect(i).adjusted(-4, -4, 4, 4).contains(pos):
                return i
        return -1

    def mouseMoveEvent(self, event):
        idx = self._index_at(event.position())
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()

    def mousePressEvent(self, event):
        idx = self._index_at(event.position())
        if idx < 0:
            return
        if idx == len(self._colors):
            self.customRequested.emit()
        else:
            self.picked.emit(self._colors[idx])

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        known = [c.lower() for c in self._colors]
        is_custom = self._current.lower() not in known
        for i in range(len(self._colors) + 1):
            r = self._rect(i)
            grow = 2.0 if i == self._hover else 0.0
            r = r.adjusted(-grow, -grow, grow, grow)
            custom = i == len(self._colors)
            selected = is_custom if custom else self._colors[i].lower() == self._current.lower()
            p.setPen(Qt.PenStyle.NoPen)
            if custom:
                conic = QConicalGradient(r.center(), 0)
                for stop, col in ((0.0, "#ff4d6d"), (0.2, "#fbbf24"), (0.4, "#34d399"), (0.6, "#22d3ee"), (0.8, "#7c5cff"), (1.0, "#ff4d6d")):
                    conic.setColorAt(stop, QColor(col))
                p.setBrush(QBrush(conic))
                p.drawEllipse(r)
                if selected:
                    p.setBrush(QColor(self._current))
                    p.drawEllipse(r.adjusted(7, 7, -7, -7))
                else:
                    draw_glyph(p, "plus", r.adjusted(7, 7, -7, -7), WHITE, 2.6)
            else:
                p.setBrush(QColor(self._colors[i]))
                p.drawEllipse(r)
            if selected:
                ring = r.adjusted(-5, -5, 5, 5)
                scale = 0.7 + 0.3 * min(1.0, self._ring)
                cx = ring.center()
                ring = QRectF(0, 0, ring.width() * scale, ring.height() * scale)
                ring.moveCenter(cx)
                p.setPen(QPen(with_alpha(theme.text, int(230 * min(1.0, self._ring))), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(ring)


class Card(QWidget, Tweener):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = 0.0
        theme.changed.connect(self.update)

    def enterEvent(self, event):
        self.tween("_hover", 1.0, 200)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tween("_hover", 0.0, 280)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = float(theme.radius)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, mix(theme.card, theme.card_hi, 0.35 * self._hover))
        p.setPen(QPen(mix(theme.border, with_alpha(theme.accent, 150), 0.7 * self._hover), 1))
        p.drawPath(path)


class SettingRow(TrMixin, Card):
    def __init__(self, title_key, desc_key=None, control=None, glyph=None, parent=None):
        super().__init__(parent)
        self.init_tr()
        self._glyph = glyph
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20 if not glyph else 62, 15, 20, 15)
        lay.setSpacing(18)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.title = ThemedLabel("", "text", 10.5, True)
        self.t(self.title.setText, title_key)
        text.addWidget(self.title)
        self.desc = None
        if desc_key:
            self.desc = ThemedLabel("", "sub", 9.0, False, True)
            self.t(self.desc.setText, desc_key)
            text.addWidget(self.desc)
        lay.addLayout(text, 1)
        self.control = control
        if control is not None:
            lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._glyph:
            p = QPainter(self)
            aa(p)
            box = QRectF(18, (self.height() - 30) / 2, 30, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(theme.accent, 40))
            p.drawRoundedRect(box, 9, 9)
            draw_glyph(p, self._glyph, box.adjusted(7, 7, -7, -7), mix(theme.accent, theme.text, 0.25), 2.0)


class ProgressBar(QWidget, Tweener):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._shown = 0.0
        self._shimmer = 0.0
        self._indeterminate = False
        self.setFixedHeight(10)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        theme.changed.connect(self.update)

    def _tick(self):
        self._shimmer = (self._shimmer + 0.022) % 1.4
        self.update()

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def set_indeterminate(self, flag):
        self._indeterminate = flag
        self.update()

    def set_value(self, value, instant=False):
        self._value = max(0.0, min(1.0, value))
        if instant:
            self._shown = self._value
            self.update()
        else:
            self.tween("_shown", self._value, 260)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, mix(theme.border, theme.card_hi, 0.4))
        p.save()
        p.setClipPath(path)
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0.0, theme.accent)
        grad.setColorAt(1.0, theme.accent2)
        if self._indeterminate:
            span = r.width() * 0.35
            x = -span + (r.width() + span) * (self._shimmer / 1.4)
            p.fillRect(QRectF(x, 0, span, r.height()), QBrush(grad))
        else:
            width = r.width() * self._shown
            p.fillRect(QRectF(0, 0, width, r.height()), QBrush(grad))
            sx = (width + 60) * (self._shimmer / 1.4) - 60
            sh = QLinearGradient(sx, 0, sx + 60, 0)
            sh.setColorAt(0.0, QColor(255, 255, 255, 0))
            sh.setColorAt(0.5, QColor(255, 255, 255, 90))
            sh.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(0, 0, width, r.height()), QBrush(sh))
        p.restore()


class Logo(QWidget):
    def __init__(self, size=104, parent=None):
        super().__init__(parent)
        self._size = size
        self._pulse = 0.0
        self._phase = 0.0
        self._pix = None
        pad = int(size * 0.25)
        self.setFixedSize(size + pad * 2, size + pad * 2)
        self._pad = pad
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        theme.changed.connect(self.update)
        cfg.changed.connect(self._sync)

    def _sync(self, key):
        if key in ("animations", "*"):
            self._run()

    def _run(self):
        if cfg.get("animations") and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def showEvent(self, event):
        self._run()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        self._phase = (self._phase + 0.025) % (math.tau * 4)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        dpr = self.devicePixelRatioF()
        if self._pix is None or self._pix.devicePixelRatio() != dpr:
            self._pix = render_icon(int(self._size * dpr))
            self._pix.setDevicePixelRatio(dpr)
        breathe = (math.sin(self._phase) + 1) / 2
        bob = math.sin(self._phase * 0.5) * 2.4 if cfg.get("animations") else 0.0
        c = QPointF(self.width() / 2, self.height() / 2 + bob)
        radius = self._size * (0.78 + 0.12 * breathe)
        g = QRadialGradient(c, radius)
        g.setColorAt(0.0, with_alpha(theme.accent, int(120 + 70 * breathe)))
        g.setColorAt(0.55, with_alpha(theme.accent2, int(34 + 30 * breathe)))
        g.setColorAt(1.0, with_alpha(theme.accent2, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, radius, radius)
        p.drawPixmap(QPointF(self._pad, self._pad + bob), self._pix)


class Sidebar(QWidget, Tweener):
    requested = pyqtSignal(int)

    ITEM_H = 46
    GAP = 6
    PAD = 8

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._cur = 0
        self._ind = 0.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setFixedWidth(206)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.changed.connect(self.update)
        i18n.changed.connect(self.update)

    def current(self):
        return self._cur

    def set_current(self, index, animate=True):
        self._cur = index
        if animate:
            self.tween("_ind", float(index), 380, QEasingCurve.Type.OutBack)
        else:
            self._ind = float(index)
            self.update()

    def _index_at(self, pos):
        y = pos.y() - self.PAD
        idx = int(y // (self.ITEM_H + self.GAP))
        if 0 <= idx < len(self._items) and (y - idx * (self.ITEM_H + self.GAP)) <= self.ITEM_H:
            return idx
        return -1

    def mouseMoveEvent(self, event):
        idx = self._index_at(event.position())
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.position())
            if idx >= 0:
                self.requested.emit(idx)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        font = QFont(self.font())
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        step = self.ITEM_H + self.GAP
        rad = min(float(theme.radius), self.ITEM_H / 2.0)
        for i, (glyph, key) in enumerate(self._items):
            y = self.PAD + i * step
            row = QRectF(6, y, self.width() - 12, self.ITEM_H)
            if i == self._hover and i != self._cur:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.card)
                p.drawRoundedRect(row, rad, rad)
        iy = self.PAD + self._ind * step
        ind = QRectF(6, iy, self.width() - 12, self.ITEM_H)
        grad = QLinearGradient(ind.topLeft(), ind.topRight())
        grad.setColorAt(0.0, with_alpha(theme.accent, 78))
        grad.setColorAt(1.0, with_alpha(theme.accent2, 22))
        path = QPainterPath()
        path.addRoundedRect(ind, rad, rad)
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(with_alpha(theme.accent, 90), 1))
        p.drawPath(path)
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(ind.left() + 2, ind.top() + 11, 3.5, ind.height() - 22), 1.75, 1.75)
        p.fillPath(bar, theme.accent2)
        for i, (glyph, key) in enumerate(self._items):
            y = self.PAD + i * step
            near = max(0.0, 1.0 - abs(self._ind - i))
            fg = mix(theme.sub, theme.text, near)
            ic = mix(theme.sub, theme.accent2 if theme.dark else theme.accent, near)
            draw_glyph(p, glyph, QRectF(22, y + (self.ITEM_H - 20) / 2, 20, 20), ic, 2.0)
            p.setPen(fg)
            p.drawText(
                QRectF(54, y, self.width() - 66, self.ITEM_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                tr(key),
            )


class Page(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.setWidget(self.body)
        self.body.setAutoFillBackground(False)
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(4, 4, 14, 28)
        self.lay.setSpacing(10)
        self._items = []
        self._gen = 0

    def add(self, widget, reveal=True):
        self.lay.addWidget(widget)
        if reveal:
            self._items.append(widget)
        return widget

    def heading(self, key, sub_key=None):
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(2, 4, 0, 10)
        col.setSpacing(4)
        title = ThemedLabel("", "text", 20.0, True)
        sub = ThemedLabel("", "sub", 10.0, False, True) if sub_key else None
        holder = _Heading(box, title, sub, key, sub_key)
        col.addWidget(title)
        if sub:
            col.addWidget(sub)
        box._holder = holder
        return self.add(box)

    def group(self, key):
        label = _GroupLabel(key)
        label.setContentsMargins(4, 12, 0, 2)
        return self.add(label)

    def finish(self):
        self.lay.addStretch(1)

    def reveal(self):
        self._gen += 1
        gen = self._gen
        self.verticalScrollBar().setValue(0)
        if not anim.enabled():
            return
        for i, widget in enumerate(self._items):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            QTimer.singleShot(anim.dur(40 + i * 38), lambda w=widget, e=effect, g=gen: self._fade(w, e, g))

    def _fade(self, widget, effect, gen):
        if gen != self._gen or widget.graphicsEffect() is not effect:
            return
        fade = QPropertyAnimation(effect, b"opacity", effect)
        fade.setDuration(anim.dur(320))
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.finished.connect(lambda w=widget, e=effect: w.graphicsEffect() is e and w.setGraphicsEffect(None))
        fade.start()


def _run_fade(widget, effect, ms):
    try:
        if widget.graphicsEffect() is not effect:
            return
    except RuntimeError:
        return
    fade = QPropertyAnimation(effect, b"opacity", effect)
    fade.setDuration(anim.dur(ms))
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.finished.connect(lambda: widget.graphicsEffect() is effect and widget.setGraphicsEffect(None))
    fade.start()


def fade_stagger(widgets, start=100, step=70, ms=420):
    if not anim.enabled():
        return
    for i, widget in enumerate(widgets):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        QTimer.singleShot(anim.dur(start + i * step), lambda w=widget, e=effect: _run_fade(w, e, ms))


class _Heading(TrMixin, QWidget):
    def __init__(self, box, title, sub, key, sub_key):
        super().__init__(box)
        self.init_tr()
        self.t(title.setText, key)
        if sub:
            self.t(sub.setText, sub_key)
        self.hide()


class _GroupLabel(TrMixin, ThemedLabel):
    def __init__(self, key):
        super().__init__("", "accent", 9.0, True)
        self.init_tr()
        self.t(lambda text: self.setText(text.upper()), key)


class Dialog(FrameMixin, QDialog):
    def __init__(self, parent, glyph, title, text, ok_key, cancel_key=None, danger=False, countdown=0, check_key=None):
        super().__init__(parent)
        self.setup_frame(orbs=False)
        self.setModal(True)
        self.setFixedWidth(520 + 2 * self.MARGIN)
        self._countdown = countdown
        self._ok_key = ok_key
        self._checked = False

        root = QVBoxLayout(self)
        m = self.MARGIN
        root.setContentsMargins(m + 26, m + 24, m + 26, m + 22)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(16)
        badge = _Badge(glyph, theme.danger if danger else theme.accent)
        head.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(ThemedLabel(title, "text", 14.0, True, True))
        col.addWidget(ThemedLabel(text, "sub", 10.0, False, True))
        head.addLayout(col, 1)
        root.addLayout(head)

        self._toggle = None
        if check_key:
            row = QHBoxLayout()
            row.setContentsMargins(64, 4, 0, 0)
            self._toggle = Toggle(False)
            self._toggle.toggled.connect(self._on_check)
            row.addWidget(self._toggle)
            row.addWidget(ThemedLabel(tr(check_key), "text", 10.0), 1)
            root.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = None
        if cancel_key:
            self.cancel_btn = FancyButton(tr(cancel_key), None, "ghost", 42)
            self.cancel_btn.clicked.connect(self.reject)
            buttons.addWidget(self.cancel_btn)
        self.ok_btn = FancyButton(tr(ok_key), None, "danger" if danger else "primary", 42)
        self.ok_btn.clicked.connect(self.accept)
        buttons.addWidget(self.ok_btn)
        root.addLayout(buttons)

        self.layout().activate()
        need = root.heightForWidth(self.width())
        self.setFixedHeight(max(need, root.sizeHint().height()))

        if countdown > 0:
            self._timer = QTimer(self)
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._tick)
            self.ok_btn.setEnabled(False)
            self._refresh_ok()
            self._timer.start()

    def _on_check(self, state):
        self._checked = state

    def checked(self):
        return self._checked

    def _refresh_ok(self):
        suffix = f" ({self._countdown})" if self._countdown > 0 else ""
        self.ok_btn.setText(tr(self._ok_key) + suffix)

    def _tick(self):
        self._countdown -= 1
        self._refresh_ok()
        if self._countdown <= 0:
            self._timer.stop()
            self.ok_btn.setEnabled(True)

    @staticmethod
    def ask(parent, glyph, title, text, ok_key, cancel_key=None, danger=False, countdown=0, check_key=None):
        dialog = Dialog(parent, glyph, title, text, ok_key, cancel_key, danger, countdown, check_key)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return accepted, dialog.checked()


class _Badge(QWidget):
    def __init__(self, glyph, color, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._color = color
        self.setFixedSize(48, 48)

    def paintEvent(self, event):
        p = QPainter(self)
        aa(p)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QRadialGradient(r.center(), r.width() * 0.8)
        g.setColorAt(0.0, with_alpha(self._color, 90))
        g.setColorAt(1.0, with_alpha(self._color, 28))
        p.setPen(QPen(with_alpha(self._color, 140), 1.2))
        p.setBrush(QBrush(g))
        p.drawEllipse(r)
        draw_glyph(p, self._glyph, r.adjusted(12, 12, -12, -12), mix(self._color, WHITE, 0.35), 2.2)
