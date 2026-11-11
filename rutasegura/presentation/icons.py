"""Íconos dibujados con código (sin archivos ni descargas).

Los íconos de las herramientas usan los mismos colores que los elementos del plano, así la
barra de herramientas y las capas sirven también de leyenda.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

from rutasegura.application.progress import StepState
from rutasegura.domain.enums import ElementType
from rutasegura.presentation import theme
from rutasegura.presentation.editor.scene import (
    DOOR_COLOR,
    EXIT_COLOR,
    OBSTACLE_COLOR,
    SAFE_ZONE_COLOR,
    STAIR_COLOR,
    WALL_COLOR,
)

_SCALE = 3  # se dibuja a 3× para que se vea nítido en pantallas de alta densidad
Painter = Callable[[QPainter, float], None]


def _icon(paint: Painter, size: int = 20) -> QIcon:
    pixmap = QPixmap(size * _SCALE, size * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(_SCALE)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint(painter, float(size))
    painter.end()
    return QIcon(pixmap)


def _pen(color: QColor | str, width: float) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _wall(p: QPainter, s: float) -> None:
    p.setPen(_pen(WALL_COLOR, s * 0.2))
    p.drawLine(QPointF(s * 0.15, s * 0.5), QPointF(s * 0.85, s * 0.5))


def _door(p: QPainter, s: float) -> None:
    p.setPen(_pen(WALL_COLOR, s * 0.14))
    p.drawLine(QPointF(s * 0.08, s * 0.8), QPointF(s * 0.25, s * 0.8))
    p.drawLine(QPointF(s * 0.75, s * 0.8), QPointF(s * 0.92, s * 0.8))
    p.setPen(_pen(DOOR_COLOR, s * 0.12))
    p.drawLine(QPointF(s * 0.25, s * 0.8), QPointF(s * 0.25, s * 0.28))
    arc = QPen(DOOR_COLOR, s * 0.06, Qt.PenStyle.DashLine)
    p.setPen(arc)
    p.drawArc(QRectF(s * -0.27, s * 0.28, s * 1.04, s * 1.04), 0, 90 * 16)


def _exit(p: QPainter, s: float) -> None:
    p.setPen(_pen(EXIT_COLOR, s * 0.16))
    p.drawLine(QPointF(s * 0.82, s * 0.12), QPointF(s * 0.82, s * 0.88))
    p.setPen(_pen(EXIT_COLOR, s * 0.12))
    p.drawLine(QPointF(s * 0.12, s * 0.5), QPointF(s * 0.62, s * 0.5))
    p.drawLine(QPointF(s * 0.44, s * 0.3), QPointF(s * 0.64, s * 0.5))
    p.drawLine(QPointF(s * 0.44, s * 0.7), QPointF(s * 0.64, s * 0.5))


def _stair(p: QPainter, s: float) -> None:
    path = QPainterPath(QPointF(s * 0.1, s * 0.85))
    for i in range(3):
        x0 = s * (0.1 + 0.26 * i)
        y0 = s * (0.85 - 0.25 * i)
        path.lineTo(x0, y0 - s * 0.25)
        path.lineTo(x0 + s * 0.26, y0 - s * 0.25)
    p.setPen(_pen(STAIR_COLOR, s * 0.11))
    p.drawPath(path)


def _area(color: QColor, alpha: int) -> Painter:
    def paint(p: QPainter, s: float) -> None:
        fill = QColor(color)
        fill.setAlpha(alpha)
        p.setPen(_pen(color, s * 0.08))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(s * 0.15, s * 0.2, s * 0.7, s * 0.6), s * 0.08, s * 0.08)

    return paint


def _background(p: QPainter, s: float) -> None:
    p.setPen(_pen("#7a8696", s * 0.07))
    p.setBrush(QBrush(QColor("#eef2f7")))
    p.drawRoundedRect(QRectF(s * 0.1, s * 0.18, s * 0.8, s * 0.64), s * 0.06, s * 0.06)
    p.setPen(_pen("#7a8696", s * 0.07))
    p.drawLine(QPointF(s * 0.1, s * 0.5), QPointF(s * 0.55, s * 0.5))
    p.drawLine(QPointF(s * 0.55, s * 0.18), QPointF(s * 0.55, s * 0.82))


def _select(p: QPainter, s: float) -> None:
    path = QPainterPath(QPointF(s * 0.25, s * 0.1))
    path.lineTo(s * 0.25, s * 0.82)
    path.lineTo(s * 0.43, s * 0.64)
    path.lineTo(s * 0.57, s * 0.92)
    path.lineTo(s * 0.68, s * 0.86)
    path.lineTo(s * 0.55, s * 0.59)
    path.lineTo(s * 0.8, s * 0.58)
    path.closeSubpath()
    p.setPen(_pen(theme.TEXT, s * 0.06))
    p.setBrush(QBrush(QColor("#ffffff")))
    p.drawPath(path)


_ELEMENT_PAINTERS: dict[ElementType | None, Painter] = {
    None: _background,
    ElementType.WALL: _wall,
    ElementType.DOOR: _door,
    ElementType.EXIT: _exit,
    ElementType.STAIR: _stair,
    ElementType.OBSTACLE: _area(OBSTACLE_COLOR, 160),
    ElementType.SAFE_ZONE: _area(SAFE_ZONE_COLOR, 90),
}


def element_icon(kind: ElementType | None, size: int = 20) -> QIcon:
    """Ícono de un tipo de elemento (``None`` = plano de fondo)."""
    return _icon(_ELEMENT_PAINTERS[kind], size)


def select_icon(size: int = 20) -> QIcon:
    """Ícono de la herramienta Seleccionar (flecha)."""
    return _icon(_select, size)


def step_icon(state: StepState, number: int, enabled: bool = True, size: int = 22) -> QIcon:
    """Círculo del paso: ✓ verde si está completo, ! ámbar si hay que revisar, número si no."""

    def paint(p: QPainter, s: float) -> None:
        rect = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(round(s * 0.55))
        p.setFont(font)
        if state is StepState.DONE and enabled:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#43a047")))
            p.drawEllipse(rect)
            p.setPen(_pen("#ffffff", s * 0.11))
            check = [(0.28, 0.52), (0.44, 0.68), (0.73, 0.35)]
            p.drawPolyline([QPointF(s * x, s * y) for x, y in check])
        elif state is StepState.WARNING and enabled:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#f0a020")))
            p.drawEllipse(rect)
            p.setPen(QColor("#ffffff"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "!")
        else:
            color = QColor("#9fb3cc" if enabled else "#5c7290")
            p.setPen(_pen(color, s * 0.07))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)
            p.setPen(color)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(number))

    return _icon(paint, size)
