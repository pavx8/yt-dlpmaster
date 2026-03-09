from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QStyle, QWidget


def tinted_theme_icon(
    widget: QWidget,
    name: str,
    fallback: QStyle.StandardPixmap,
    size: QSize = QSize(16, 16),
) -> QIcon:
    base_icon = QIcon.fromTheme(name)
    if base_icon.isNull():
        base_icon = widget.style().standardIcon(fallback)
    if base_icon.isNull():
        return base_icon

    app = QApplication.instance()
    palette = app.palette() if app is not None else widget.palette()
    button_bg = palette.color(QPalette.ColorRole.Button)
    button_text = palette.color(QPalette.ColorRole.ButtonText)
    alt_text = palette.color(QPalette.ColorRole.Text)

    def _luma(color) -> float:
        return 0.2126 * color.redF() + 0.7152 * color.greenF() + 0.0722 * color.blueF()

    color_normal = button_text
    if abs(_luma(button_text) - _luma(button_bg)) < abs(_luma(alt_text) - _luma(button_bg)):
        color_normal = alt_text
    color_disabled = palette.color(QPalette.ColorRole.Mid)

    icon = QIcon()
    states = [
        (QIcon.Mode.Normal, color_normal),
        (QIcon.Mode.Active, color_normal),
        (QIcon.Mode.Selected, color_normal),
        (QIcon.Mode.Disabled, color_disabled),
    ]
    for mode, tint in states:
        source = base_icon.pixmap(size, mode)
        if source.isNull():
            continue
        result = QPixmap(source.size())
        result.setDevicePixelRatio(source.devicePixelRatio())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(result.rect(), tint)
        painter.end()
        icon.addPixmap(result, mode, QIcon.State.Off)
    return icon if not icon.isNull() else base_icon
