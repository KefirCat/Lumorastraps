import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

BRAND_A = QColor("#7c5cff")
BRAND_B = QColor("#22d3ee")
BRAND_C = QColor("#f43f8e")


_custom_cache = {}


def asset_dir() -> Path:
    from .constants import project_root

    return project_root() / "assets"


def _load_custom():
    if "pix" in _custom_cache:
        return _custom_cache["pix"]
    pix = None
    folder = asset_dir()
    png = folder / "lumora.png"
    ico = folder / "lumora.ico"
    if png.is_file():
        loaded = QPixmap(str(png))
        if not loaded.isNull():
            pix = loaded
    if pix is None and ico.is_file():
        loaded = QPixmap(str(ico))
        if loaded.isNull():
            try:
                from PIL import Image
                from PyQt6.QtGui import QImage

                img = Image.open(ico)
                img.size = max(img.info.get("sizes", {img.size}))
                img = img.convert("RGBA")
                qimg = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format.Format_RGBA8888).copy()
                loaded = QPixmap.fromImage(qimg)
            except Exception:
                loaded = QPixmap()
        if not loaded.isNull():
            pix = loaded
    _custom_cache["pix"] = pix
    return pix


def render_icon(size: int = 256) -> QPixmap:
    custom = _load_custom()
    if custom is not None:
        return custom.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return render_generated(size)


def render_generated(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    body = QRectF(s * 0.05, s * 0.05, s * 0.9, s * 0.9)
    shape = QPainterPath()
    shape.addRoundedRect(body, s * 0.26, s * 0.26)

    grad = QLinearGradient(body.topLeft(), body.bottomRight())
    grad.setColorAt(0.0, BRAND_A)
    grad.setColorAt(0.55, QColor("#5b8cff"))
    grad.setColorAt(1.0, BRAND_B)
    p.fillPath(shape, QBrush(grad))

    p.save()
    p.setClipPath(shape)
    glow = QRadialGradient(QPointF(s * 0.82, s * 0.14), s * 0.55)
    glow.setColorAt(0.0, QColor(255, 255, 255, 120))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(body, QBrush(glow))
    shade = QRadialGradient(QPointF(s * 0.2, s * 0.95), s * 0.7)
    shade.setColorAt(0.0, QColor(BRAND_C.red(), BRAND_C.green(), BRAND_C.blue(), 150))
    shade.setColorAt(1.0, QColor(BRAND_C.red(), BRAND_C.green(), BRAND_C.blue(), 0))
    p.fillRect(body, QBrush(shade))
    gloss = QLinearGradient(QPointF(0, body.top()), QPointF(0, body.top() + body.height() * 0.5))
    gloss.setColorAt(0.0, QColor(255, 255, 255, 70))
    gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(body.left(), body.top(), body.width(), body.height() * 0.5), QBrush(gloss))
    p.restore()

    ring = QPen(QColor(255, 255, 255, 150), s * 0.032)
    ring.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(ring)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), 40 * 16, 230 * 16)

    tri = QPainterPath()
    tri.moveTo(s * 0.41, s * 0.3)
    tri.lineTo(s * 0.72, s * 0.5)
    tri.lineTo(s * 0.41, s * 0.7)
    tri.closeSubpath()
    soft = QPen(QColor(255, 255, 255), s * 0.07)
    soft.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(soft)
    p.setBrush(QBrush(QColor(255, 255, 255)))
    p.drawPath(tri)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255, 235)))
    p.drawEllipse(QPointF(s * 0.745, s * 0.255), s * 0.034, s * 0.034)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render_icon(size))
    return icon


def save_icon_files(target: Path):
    target.mkdir(parents=True, exist_ok=True)
    if (target / "lumora.ico").is_file() or (target / "lumora.png").is_file():
        return
    png = target / "lumora.png"
    render_generated(512).save(str(png), "PNG")
    try:
        from PIL import Image

        img = Image.open(png).convert("RGBA")
        img.save(target / "lumora.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except Exception:
        pass


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    _app = QApplication(sys.argv)
    save_icon_files(Path(__file__).resolve().parent.parent / "assets")
