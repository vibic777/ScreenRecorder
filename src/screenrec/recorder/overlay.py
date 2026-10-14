"""Render text literally with Qt, then use a fixed FFmpeg filter graph."""
from screenrec.localization import tr
from pathlib import Path
from screenrec.qt.QtCore import Qt, QRectF
from screenrec.qt.QtGui import QImage, QImageReader, QPainter, QColor, QFont
from screenrec.config.templates import validate
from screenrec.logger.logger import get_logger
log = get_logger(__name__)

def enabled(template):
    return any(layer["enabled"] for layer in validate(template).values())

def load_image(path):
    file = Path(path)
    if not file.is_file() or file.stat().st_size > 32 * 1024 * 1024:
        raise ValueError(tr("error.overlay_image_missing"))
    reader = QImageReader(str(file))
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg", b"bmp", b"webp"):
        raise ValueError(tr("error.overlay_image_type"))
    size = reader.size()
    if size.width() <= 0 or size.height() <= 0 or size.width()*size.height() > 32_000_000:
        raise ValueError(tr("error.overlay_image_pixels"))
    image = reader.read()
    if image.isNull():
        raise ValueError(tr("error.overlay_image_read"))
    return image

def render(template, width, height, image=None):
    template = validate(template)
    canvas = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for kind in ("image", "text"):
            layer = template[kind]
            if not layer["enabled"]:
                continue
            rect = QRectF(layer["x"]*width,layer["y"]*height,layer["w"]*width,layer["h"]*height)
            painter.save()
            painter.setClipRect(rect)
            painter.setOpacity(layer["opacity"])
            if kind == "image":
                picture = image if image is not None else load_image(layer["path"])
                size = picture.size().scaled(rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
                target = QRectF(rect.x()+(rect.width()-size.width())/2, rect.y()+(rect.height()-size.height())/2, size.width(),size.height())
                painter.drawImage(target,picture)
            else:
                font = QFont(layer["font"])
                font.setPixelSize(max(1,round(layer["size"]*height)))
                painter.setFont(font)
                color = QColor(layer["color"])
                painter.setPen(color if color.isValid() else QColor("white"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, layer["text"])
            painter.restore()
    finally:
        painter.end()
    return canvas

def prepare(template, width, height, destination, image=None):
    if not enabled(template):
        return None
    log.debug("Preparing overlay layer: width=%s height=%s",width,height)
    try:
        if not render(template,width,height,image).save(str(destination),"PNG"):
            raise RuntimeError(tr("error.overlay_layer_save"))
    except Exception:
        log.exception("Overlay preparation failed")
        raise
    return destination

def ffmpeg_options(options, overlay):
    if overlay is None:
        return [], options
    options = list(options)
    index = options.index("-vf")
    pad = options[index+1]
    del options[index:index+2]
    return ["-i",str(overlay)], ["-filter_complex",f"[0:v][1:v]overlay=0:0:eof_action=repeat,{pad}[composite]",
                               "-map","[composite]"] + options
