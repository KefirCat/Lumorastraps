import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen


def _poly(points, closed=False):
    path = QPainterPath()
    path.moveTo(QPointF(*points[0]))
    for pt in points[1:]:
        path.lineTo(QPointF(*pt))
    if closed:
        path.closeSubpath()
    return path


def _dot(p, x, y, r, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    p.drawEllipse(QPointF(x, y), r, r)


def draw_glyph(p: QPainter, name: str, rect: QRectF, color: QColor, weight: float = 2.0):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = min(rect.width(), rect.height())
    p.translate(rect.center().x() - size / 2, rect.center().y() - size / 2)
    p.scale(size / 24.0, size / 24.0)
    pen = QPen(color, weight)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if name == "play":
        p.setBrush(QBrush(color))
        p.drawPath(_poly([(8, 5.5), (19, 12), (8, 18.5)], True))
    elif name == "cube":
        p.drawPath(_poly([(12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5)], True))
        p.drawPath(_poly([(4, 7.5), (12, 12), (20, 7.5)]))
        p.drawLine(QPointF(12, 12), QPointF(12, 21))
    elif name == "gear":
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
        p.drawEllipse(QPointF(12, 12), 7.2, 7.2)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(
                QPointF(12 + math.cos(a) * 7.2, 12 + math.sin(a) * 7.2),
                QPointF(12 + math.cos(a) * 10, 12 + math.sin(a) * 10),
            )
    elif name == "close":
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
    elif name == "minimize":
        p.drawLine(QPointF(6, 12), QPointF(18, 12))
    elif name == "home":
        p.drawPath(_poly([(3.5, 11.5), (12, 4), (20.5, 11.5)]))
        p.drawPath(_poly([(6, 10), (6, 20), (18, 20), (18, 10)]))
    elif name == "palette":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        _dot(p, 8, 10, 1.3, color)
        _dot(p, 12, 7.5, 1.3, color)
        _dot(p, 16, 10, 1.3, color)
        _dot(p, 15.5, 15, 1.3, color)
    elif name == "bolt":
        p.drawPath(_poly([(13, 2.5), (5.5, 13), (11.5, 13), (10.5, 21.5), (18.5, 10.5), (12.5, 10.5)], True))
    elif name == "flag":
        p.drawLine(QPointF(6, 3), QPointF(6, 21))
        p.drawPath(_poly([(6, 4.5), (18, 4.5), (15, 9), (18, 13.5), (6, 13.5)]))
    elif name == "info":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawLine(QPointF(12, 11), QPointF(12, 17))
        _dot(p, 12, 7.6, 1.2, color)
    elif name == "warning":
        p.drawPath(_poly([(12, 3.5), (21.5, 20), (2.5, 20)], True))
        p.drawLine(QPointF(12, 10), QPointF(12, 14.5))
        _dot(p, 12, 17.3, 1.2, color)
    elif name == "download":
        p.drawLine(QPointF(12, 4), QPointF(12, 15))
        p.drawPath(_poly([(7, 10.5), (12, 15.5), (17, 10.5)]))
        p.drawLine(QPointF(5, 20), QPointF(19, 20))
    elif name == "check":
        p.drawPath(_poly([(5, 12.5), (10, 17.5), (19, 7)]))
    elif name == "folder":
        p.drawPath(_poly([(3, 6), (9.5, 6), (11.5, 8.5), (21, 8.5), (21, 19), (3, 19)], True))
    elif name == "trash":
        p.drawLine(QPointF(4, 7), QPointF(20, 7))
        p.drawPath(_poly([(6, 7), (7, 20), (17, 20), (18, 7)]))
        p.drawPath(_poly([(9.5, 7), (9.5, 4), (14.5, 4), (14.5, 7)]))
    elif name == "plus":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "globe":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawEllipse(QPointF(12, 12), 4, 9)
        p.drawLine(QPointF(3, 12), QPointF(21, 12))
    elif name == "refresh":
        p.drawArc(QRectF(4.5, 4.5, 15, 15), 40 * 16, 270 * 16)
        p.drawPath(_poly([(17.5, 2.8), (18.6, 7.4), (14, 8.2)]))
    elif name == "upload":
        p.drawLine(QPointF(12, 15), QPointF(12, 4))
        p.drawPath(_poly([(7, 8.5), (12, 3.5), (17, 8.5)]))
        p.drawLine(QPointF(5, 20), QPointF(19, 20))
    elif name == "copy":
        p.drawRoundedRect(QRectF(8.5, 8.5, 11, 11), 2, 2)
        p.drawPath(_poly([(15.5, 8.5), (15.5, 5.5), (5.5, 5.5), (5.5, 15.5), (8.5, 15.5)]))
    p.restore()
