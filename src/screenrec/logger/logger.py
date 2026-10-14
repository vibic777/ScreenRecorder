"""Process-wide, runtime-switchable logging with exact level selection."""
from screenrec.localization import tr
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

LEVELS = {"TRACE":5,"DEBUG":10,"INFO":20,"WARNING":30,"ERROR":40,"CRITICAL":50,"FATAL":60}
DEFAULT_LEVELS = ["INFO","WARNING","ERROR","CRITICAL","FATAL"]
logging.addLevelName(5,"TRACE")
logging.addLevelName(60,"FATAL")

def get_default_log_path():
    if getattr(sys,"frozen",False):
        return Path(sys.executable).resolve().parent / "screenrec.log"
    return Path(__file__).resolve().parents[1] / "screenrec.log"

class FileHandler(RotatingFileHandler):
    def handleError(self,record):
        # Let the hub disable file output and notify the GUI, never crash recording.
        raise OSError("Unable to write or rotate log file")

class Formatter(logging.Formatter):
    def format(self,record):
        # Keep untrusted error messages from forging additional log lines.
        copy = logging.makeLogRecord(record.__dict__)
        copy.msg = record.getMessage().replace("\r","\\r").replace("\n","\\n")
        copy.args = ()
        return super().format(copy)

class Hub(logging.Handler):
    def __init__(self):
        super().__init__(5)
        self.file = None
        self.selected = set()
        self.actual_path = None
        self.problem = None
    def stop(self):
        if self.file:
            try:
                self.file.flush()
                self.file.close()
            except OSError:
                pass
        self.file = None
    def emit(self,record):
        if self.file is None or record.levelno not in self.selected:
            return
        try:
            self.file.emit(record)
        except Exception:
            self.stop()
            self.problem = tr("error.log_write_disabled")
    def configure(self,enabled,path,levels):
        with self.lock:
            self.stop()
            self.selected = {LEVELS[key] for key in levels if key in LEVELS}
            self.actual_path = None
            self.problem = None
            if not enabled:
                return None, None
            try:
                requested = Path(path).expanduser().resolve() if path else get_default_log_path()
            except (OSError,ValueError,RuntimeError):
                requested = None
            candidates = [requested] if requested is not None else []
            if requested != get_default_log_path():
                candidates.append(get_default_log_path())
            for candidate in candidates:
                try:
                    # Do not silently create a mistyped directory.
                    self.file = FileHandler(candidate, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
                    self.file.setFormatter(Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s",datefmt="%Y-%m-%d %H:%M:%S"))
                    self.actual_path = candidate
                    warning = None if candidate == requested else tr("error.log_fallback_path", path=candidate)
                    return candidate, warning
                except (OSError,ValueError):
                    self.stop()
            return None, tr("error.log_unavailable")
    def take_problem(self):
        with self.lock:
            problem,self.problem = self.problem,None
            return problem

hub = Hub()
root = logging.getLogger("screenrec")
root.setLevel(5)
root.propagate = False
root.addHandler(hub)

class Logger:
    def __init__(self,name):
        self.logger = logging.getLogger(name if name.startswith("screenrec") else "screenrec."+name)
    def trace(self,message,*args,**kwargs):
        self.logger.log(5,message,*args,**kwargs)
    def fatal_error(self,message,*args,**kwargs):
        self.logger.log(60,message,*args,**kwargs)
    def __getattr__(self,name):
        return getattr(self.logger,name)

def get_logger(name):
    return Logger(name)

def configure(enabled=False,path="",levels=None):
    return hub.configure(enabled,path,DEFAULT_LEVELS if levels is None else levels)

def shutdown():
    with hub.lock:
        hub.stop()
