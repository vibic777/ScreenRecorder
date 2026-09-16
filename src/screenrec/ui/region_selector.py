from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog
from screenrec.localization import Translator


def physical_region(rect, logical_width, logical_height, monitor, language="en"):
    sx, sy = monitor["width"] / logical_width, monitor["height"] / logical_height
    left = max(0, min(monitor["width"], round(rect.x() * sx)))
    top = max(0, min(monitor["height"], round(rect.y() * sy)))
    right = max(left, min(monitor["width"], round((rect.x()+rect.width()) * sx)))
    bottom = max(top, min(monitor["height"], round((rect.y()+rect.height()) * sy)))
    if right-left < 2 or bottom-top < 2:
        raise ValueError(Translator(language).tr("region.too_small"))
    return {"kind":"region", "left":monitor["left"]+left, "top":monitor["top"]+top,
            "width":right-left, "height":bottom-top}


class RegionSelector(QDialog):
    def __init__(self, screen, monitor, saved=None, language="en"):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.monitor = monitor
        self.language = language
        self.translator = Translator(language)
        self.setGeometry(screen.geometry())
        self.background = screen.grabWindow(0)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.selection = QRect()
        if saved and saved.get("width", 0) > 0:
            sx, sy = self.width()/monitor["width"], self.height()/monitor["height"]
            self.selection = QRect(round((saved["left"]-monitor["left"])*sx), round((saved["top"]-monitor["top"])*sy),
                                   round(saved["width"]*sx), round(saved["height"]*sy)).intersected(self.rect())
        self.anchor = None
        self.drag_mode = None
        self.original = QRect()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        if not self.selection.isEmpty():
            painter.save()
            painter.setClipRect(self.selection)
            painter.drawPixmap(self.rect(), self.background)
            painter.restore()
            painter.setPen(QPen(QColor("#49a7ff"), 2))
            painter.drawRect(self.selection)
            painter.fillRect(QRect(self.selection.bottomRight()-QPoint(6,6), self.selection.bottomRight()+QPoint(6,6)), QColor("#49a7ff"))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(20, 30, self.translator.tr("region.instructions"))
        painter.drawText(20, 55, self.translator.tr("region.keys"))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.anchor = event.position().toPoint()
        self.original = QRect(self.selection)
        if (self.anchor-self.selection.bottomRight()).manhattanLength() < 20:
            self.drag_mode = "resize"
        elif self.selection.contains(self.anchor):
            self.drag_mode = "move"
        else:
            self.drag_mode = "new"
            self.selection = QRect(self.anchor, self.anchor)
        self.update()

    def mouseMoveEvent(self, event):
        if self.anchor is None:
            return
        point = event.position().toPoint()
        point.setX(max(0, min(self.width()-1, point.x())))
        point.setY(max(0, min(self.height()-1, point.y())))
        if self.drag_mode == "move":
            rect = self.original.translated(point-self.anchor)
            rect.moveLeft(max(0, min(self.width()-rect.width(), rect.left())))
            rect.moveTop(max(0, min(self.height()-rect.height(), rect.top())))
            self.selection = rect
        elif self.drag_mode == "resize":
            self.selection = QRect(self.original.topLeft(), point).normalized()
        else:
            self.selection = QRect(self.anchor, point).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        self.anchor = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.selection.width() >= 2 and self.selection.height() >= 2:
            self.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()

    def selected_region(self):
        return physical_region(self.selection, self.width(), self.height(), self.monitor, self.language)

def screen_for_monitor(monitor, index):
    import platform
    from PySide6.QtGui import QGuiApplication
    screens = QGuiApplication.screens()
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes as wt
        class Info(ctypes.Structure):
            _fields_ = [("size",wt.DWORD), ("monitor",wt.RECT), ("work",wt.RECT),
                        ("flags",wt.DWORD), ("device",wt.WCHAR*32)]
        found = []
        callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HANDLE, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
        user32 = ctypes.WinDLL("user32")
        user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(Info)]
        @callback_type
        def visit(handle, dc, rect, data):
            info = Info()
            info.size = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.monitor
                if (r.left,r.top,r.right-r.left,r.bottom-r.top) == (monitor["left"],monitor["top"],monitor["width"],monitor["height"]):
                    found.append(info.device)
            return True
        user32.EnumDisplayMonitors(None,None,visit,0)
        for screen in screens:
            if screen.name() in found:
                return screen
    if len(screens) == 1:
        return screens[0]
    for screen in screens:
        geometry = screen.geometry()
        if (geometry.x(),geometry.y(),round(geometry.width()*screen.devicePixelRatio()),round(geometry.height()*screen.devicePixelRatio())) == (monitor["left"],monitor["top"],monitor["width"],monitor["height"]):
            return screen
    raise RuntimeError("Не удалось сопоставить монитор с экраном Qt. Обновите список мониторов.")
