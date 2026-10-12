"""
Render the Taalbrug app icon (files/taalbrug.ico + files/taalbrug.png) from the startup logo:
two tilted flash cards on the indigo background, joined by the bridge arc with the amber spark on top.
Run once after changing the design: python make_icon.py
"""
import math
import os
import sys
from PIL import Image
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath, QPen, QColor, QFont, QLinearGradient, QRadialGradient
from PyQt6.QtCore import Qt, QRectF, QPointF, QBuffer, QIODevice

import config

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
CARD_W, CARD_H = 80, 104  # in 256-unit design space


def card_top(center: QPointF, angle: float) -> QPointF:
    radians = math.radians(angle)
    dy = -CARD_H / 2 - 6
    return QPointF(center.x() - dy * math.sin(radians), center.y() + dy * math.cos(radians))


def draw_card(painter: QPainter, center: QPointF, angle: float, language: str, word: str, detailed: bool) -> None:
    painter.save()
    painter.translate(center)
    painter.rotate(angle)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 80))
    painter.drawRoundedRect(QRectF(-CARD_W / 2 + 3, -CARD_H / 2 + 7, CARD_W, CARD_H), 12, 12)  # shadow
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawRoundedRect(QRectF(-CARD_W / 2, -CARD_H / 2, CARD_W, CARD_H), 12, 12)
    if detailed:
        font = QFont("Segoe UI")
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#6366F1"))
        painter.drawText(QRectF(-CARD_W / 2 + 9, -CARD_H / 2 + 6, CARD_W - 18, 16), Qt.AlignmentFlag.AlignLeft, language)
        font.setPixelSize(19)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#111827"))
        painter.drawText(QRectF(-CARD_W / 2, -CARD_H / 2 + 8, CARD_W, CARD_H), Qt.AlignmentFlag.AlignCenter, word)
    else:
        # too small for text: an accent stripe stands in for the word
        painter.setBrush(QColor("#6366F1"))
        painter.drawRoundedRect(QRectF(-CARD_W / 2 + 16, -6, CARD_W - 32, 14), 7, 7)
    painter.restore()


def new_painter(image: QImage, scale: float) -> QPainter:
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.scale(scale, scale)
    return painter


def draw_background(painter: QPainter, radius: float) -> None:
    """Indigo tile with a soft glow behind the logo (radius 0 = full-bleed square)."""
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, 256, 256), radius, radius)
    background = QLinearGradient(0, 0, 256, 256)
    background.setColorAt(0, QColor("#1E1B4B"))
    background.setColorAt(1, QColor("#3730A3"))
    painter.fillPath(tile, background)
    glow = QRadialGradient(QPointF(128, 130), 130)
    glow.setColorAt(0, QColor(129, 140, 248, 110))
    glow.setColorAt(1, QColor(129, 140, 248, 0))
    painter.fillPath(tile, glow)


def draw_logo(painter: QPainter, detailed: bool) -> None:
    """The two cards, the bridge arc and the spark, in 256-unit design space."""
    left_center, left_angle = QPointF(76, 166), -9
    right_center, right_angle = QPointF(180, 166), 9
    draw_card(painter, left_center, left_angle, "NL", "brug", detailed)
    draw_card(painter, right_center, right_angle, "DE", "Brücke", detailed)

    # bridge arc between the card tops, thicker at small sizes so it stays visible
    start, end = card_top(left_center, left_angle), card_top(right_center, right_angle)
    arc = QPainterPath(start)
    arc.quadTo(QPointF(128, min(start.y(), end.y()) - 92), end)
    pen_width = 9 if detailed else 16
    painter.setPen(QPen(QColor("#A5B4FC"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(arc)

    # the spark at the top of the bridge
    apex = arc.pointAtPercent(0.5)
    spark_glow = QRadialGradient(apex, 30)
    spark_glow.setColorAt(0, QColor(251, 191, 36, 230))
    spark_glow.setColorAt(1, QColor(251, 191, 36, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(spark_glow)
    painter.drawEllipse(apex, 30, 30)
    painter.setBrush(QColor(255, 236, 179))
    painter.drawEllipse(apex, 9 if detailed else 14, 9 if detailed else 14)


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    painter = new_painter(image, size / 256)
    draw_background(painter, 56)
    draw_logo(painter, size >= 128)
    painter.end()
    return image


def write_android_icons(res_dir: str) -> None:
    """
    Adaptive launcher icon for the Android app: a full-bleed background layer and the logo as foreground.
    Layers are 108 dp; launchers mask them to ~66 dp (a circle on Pixel phones), so the logo sits in the
    middle 64 dp (256 of the 432 px at xxxhdpi).
    """
    for density, size in (("mdpi", 108), ("hdpi", 162), ("xhdpi", 216), ("xxhdpi", 324), ("xxxhdpi", 432)):
        folder = os.path.join(res_dir, f"mipmap-{density}")
        os.makedirs(folder, exist_ok=True)
        background = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        painter = new_painter(background, size / 256)
        draw_background(painter, 0)
        painter.end()
        background.save(os.path.join(folder, "ic_launcher_background.png"))
        foreground = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        painter = new_painter(foreground, size / 432)
        painter.translate(88, 88)
        draw_logo(painter, True)
        painter.end()
        foreground.save(os.path.join(folder, "ic_launcher_foreground.png"))
    # the rounded tile as an in-app image (main menu)
    folder = os.path.join(res_dir, "drawable-nodpi")
    os.makedirs(folder, exist_ok=True)
    render(384).save(os.path.join(folder, "taalbrug_logo.png"))


def to_pil(image: QImage) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    from io import BytesIO
    return Image.open(BytesIO(bytes(buffer.data())))


def main() -> None:
    app = QGuiApplication(sys.argv)
    out_dir = os.path.join(config.MAIN_PATH, config.FILES_PATH)
    images = {size: to_pil(render(size)) for size in SIZES}
    images[256].save(os.path.join(out_dir, "taalbrug.png"))
    # every size is drawn separately (small ones simplified) and bundled into one .ico
    images[256].save(os.path.join(out_dir, "taalbrug.ico"), sizes=[(s, s) for s in SIZES], append_images=[images[s] for s in SIZES[:-1]])
    print("written:", out_dir)
    android_res = os.path.join(config.MAIN_PATH, "android", "app", "src", "main", "res")
    if os.path.isdir(os.path.dirname(android_res)):
        write_android_icons(android_res)
        print("written:", android_res)


if __name__ == "__main__":
    main()
