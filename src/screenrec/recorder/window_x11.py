"""XComposite window pixmap capture on X11; no desktop substitution."""
import os
from contextlib import closing
from .screen import check_platform


def windows():
    check_platform()
    from Xlib import display
    with closing(display.Display()) as connection:
        root = connection.screen().root
        prop = root.get_full_property(connection.intern_atom("_NET_CLIENT_LIST"), 0)
        result = []
        for identifier in prop.value if prop else []:
            try:
                window = connection.create_resource_object("window", int(identifier))
                name = window.get_full_property(connection.intern_atom("_NET_WM_NAME"), 0)
                title = name.value.decode("utf-8", errors="replace") if name else window.get_wm_name()
                pid = window.get_full_property(connection.intern_atom("_NET_WM_PID"), 0)
                pid = int(pid.value[0]) if pid else 0
                geometry = window.get_geometry()
                if title and pid != os.getpid():
                    result.append({"kind":"window", "hwnd":int(identifier), "pid":pid, "title":title,
                                   "width":geometry.width, "height":geometry.height})
            except Exception:
                continue
        return sorted(result, key=lambda item: item["title"].casefold())


class WindowSource:
    def __init__(self, target):
        self.target = target
        self.connection = None
        self.pixmap = None

    def __enter__(self):
        check_platform()
        from Xlib import display
        from Xlib.ext import composite
        self.connection = display.Display()
        try:
            if not self.connection.has_extension("Composite"):
                raise RuntimeError("XComposite недоступен; захват отдельного окна невозможен.")
            self.window = self.connection.create_resource_object("window", self.target["hwnd"])
            self.pixmap = self.window.composite_name_window_pixmap()
            geometry = self.pixmap.get_geometry()
            self.width, self.height = geometry.width, geometry.height
            return self
        except Exception:
            self.__exit__()
            raise RuntimeError("Окно X11 недоступно. Нужны развёрнутое окно и работающий композитор XComposite.")

    def grab(self):
        from Xlib import X
        attrs = self.window.get_attributes()
        geometry = self.window.get_geometry()
        if attrs.map_state != X.IsViewable:
            raise RuntimeError("X11 не предоставляет изображение свёрнутого окна.")
        if (geometry.width, geometry.height) != (self.width, self.height):
            raise RuntimeError("Размер окна X11 изменился. Запустите запись заново.")
        image = self.pixmap.get_image(0, 0, self.width, self.height, X.ZPixmap, 0xffffffff)
        if len(image.data) != self.width * self.height * 4:
            raise RuntimeError("Неподдерживаемый формат пикселей X11 (требуется BGRA32).")
        return image.data

    def __exit__(self, *_):
        if self.pixmap:
            self.pixmap.free()
        if self.connection:
            self.connection.close()
        self.connection = None
