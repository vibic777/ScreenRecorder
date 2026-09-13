import signal
import sys
import traceback
import multiprocessing


def main():
    multiprocessing.freeze_support()
    if not getattr(sys, "frozen", False) and sys.prefix == sys.base_prefix:
        raise SystemExit("Запустите ScreenRec внутри .venv: python -m screenrec.main")
    if "--self-test" in sys.argv:
        from .selftest import run
        return run(sys.argv[sys.argv.index("--self-test") + 1:])
    from PySide6.QtWidgets import QApplication
    from .app import ScreenRecApp

    application = QApplication(sys.argv)
    application.setApplicationName("ScreenRec")
    try:
        controller = ScreenRecApp(application)
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
