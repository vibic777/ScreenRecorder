import signal
import sys
import traceback
import multiprocessing
import platform
from pathlib import Path
from PySide6.QtCore import QLockFile
from screenrec.logger.logger import get_logger
log = get_logger(__name__)


def profile_path_from_args(argv):
    if "--profile" not in argv:
        return None
    index = argv.index("--profile")
    if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
        raise SystemExit("Параметр --profile требует путь к файлу профиля")
    return Path(argv[index + 1]).expanduser()

def qt_runtime_error(exc):
    return (f"ScreenRec cannot start because Qt/PySide6 could not be loaded.\\n"
            f"Windows: {platform.platform()} ({platform.machine()})\\n"
            f"Cause: {exc}\\n\\n"
            "Use the supported 64-bit Windows 10 1809+ or Windows 11 build, "
            "and install the Microsoft Visual C++ runtime if required.")

def show_runtime_error(message):
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "ScreenRec", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)

def main():
    multiprocessing.freeze_support()
    log.trace("Process entrypoint started")
    if not getattr(sys, "frozen", False) and sys.prefix == sys.base_prefix:
        raise SystemExit("Запустите ScreenRec внутри .venv: python -m screenrec.main")
    if "--profile" in sys.argv:
        index = sys.argv.index("--profile")
        if index + 1 >= len(sys.argv) or sys.argv[index + 1].startswith("--"):
            raise SystemExit("Параметр --profile требует путь к файлу профиля")
        profile_path = Path(sys.argv[index + 1]).expanduser()
    else:
        profile_path = None
    if "--self-test" in sys.argv:
        from .selftest import run
        return run(sys.argv[sys.argv.index("--self-test") + 1:])
    from PySide6.QtWidgets import QApplication
    from .app import ScreenRecApp

    application = QApplication(sys.argv)
    from .config.settings import Settings
    from .config.profiles import load_profile, load_default_profile
    startup_settings = load_profile(profile_path) if profile_path else (load_default_profile() or Settings.load())
    instance_lock = None
    log.debug("Startup settings loaded: language=%s single_instance=%s", startup_settings.language, not startup_settings.allow_multiple_instances)
    if not startup_settings.allow_multiple_instances:
        instance_lock = QLockFile(str(Settings.path().with_name("instance.lock")))
        instance_lock.setStaleLockTime(0)
        if not instance_lock.tryLock(100):
            log.warning("Second instance rejected by lock")
            show_runtime_error("ScreenRec уже запущен. Разрешите несколько копий в настройках, если это необходимо.")
            return 1
    log.debug("Instance lock acquired or multiple instances allowed")
    application.setApplicationName("ScreenRec")
    try:
        controller = ScreenRecApp(application, profile_path=profile_path)
    except Exception as exc:
        from .logger.logger import get_logger, shutdown as close_log
        from PySide6.QtWidgets import QMessageBox
        get_logger(__name__).fatal_error("Application startup failed",exc_info=True)
        close_log()
        QMessageBox.critical(None,"ScreenRec","Не удалось запустить приложение: " + str(exc))
        return 1

    def shutdown(*_):
        controller.request_exit(confirm=False)

    def exception_hook(kind, value, tb):
        from .logger.logger import get_logger
        get_logger(__name__).fatal_error("Unhandled application exception",exc_info=(kind,value,tb))
        traceback.print_exception(kind, value, tb)
        shutdown()

    sys.excepthook = exception_hook
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    controller.window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
