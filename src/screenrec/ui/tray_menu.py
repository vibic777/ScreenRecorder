from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def create_tray(parent, icon, start_action, stop_action, show_action, exit_action):
    tray = QSystemTrayIcon(icon, parent)
    tray.setToolTip(parent.translator.tr("tray.ready"))
    menu = QMenu()
    menu.addAction(start_action)
    menu.addAction(stop_action)
    menu.addSeparator()
    menu.addAction(show_action)
    menu.addAction(exit_action)
    tray.setContextMenu(menu)
    return tray, menu
