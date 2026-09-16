"""One registry controls application styling and both runtime icons."""
from pathlib import Path
from PySide6.QtGui import QIcon, QPalette, QColor

ROOT = Path(__file__).resolve().parent
THEMES = {
    key: {"label": label, "qss_path": ROOT / f"{key}.qss",
          "tray_icon_path": ROOT.parents[1] / "assets" / "icons" / f"icon_{key}.svg",
          "window_icon_path": ROOT.parents[1] / "assets" / "icons" / f"icon_{key}.svg",
          "background": background, "foreground": foreground, "accent": accent}
    for key, label, background, foreground, accent in (
        ("green", "Green", "#edf6f0", "#172d22", "#237a49"),
        ("blue", "Blue", "#eef4fc", "#182c46", "#2469b0"),
        ("gray", "Gray", "#eceef1", "#242830", "#555e6c"),
        ("black", "Black", "#15171b", "#f0f2f6", "#7c99bc"),
    )
}

def apply_theme(application, window, tray, name):
    theme = THEMES.get(name, THEMES["gray"])
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, theme["background"]),
        (QPalette.ColorRole.WindowText, theme["foreground"]),
        (QPalette.ColorRole.Base, theme["background"]),
        (QPalette.ColorRole.AlternateBase, theme["background"]),
        (QPalette.ColorRole.Text, theme["foreground"]),
        (QPalette.ColorRole.Button, theme["background"]),
        (QPalette.ColorRole.ButtonText, theme["foreground"]),
        (QPalette.ColorRole.Highlight, theme["accent"]),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
        (QPalette.ColorRole.ToolTipBase, theme["background"]),
        (QPalette.ColorRole.ToolTipText, theme["foreground"]),
    ):
        palette.setColor(role, QColor(color))
    application.setPalette(palette)
    application.setStyleSheet(theme["qss_path"].read_text(encoding="utf-8"))
    icon = QIcon(str(theme["window_icon_path"]))
    application.setWindowIcon(icon)
    window.setWindowIcon(icon)
    tray.setIcon(QIcon(str(theme["tray_icon_path"])))
    return icon
