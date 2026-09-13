"""Exercise the real extension in an isolated Chromium profile on local fixture tabs."""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PySide6.QtWidgets import QApplication
from playwright.sync_api import sync_playwright
from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.settings import Settings
from screenrec.recorder.browser_tab import BrowserWorker


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/".test-output"/"browser"
    output.mkdir(parents=True,exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"]=str(root/".test-output"/"playwright")
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    qt=QApplication([])
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_GET(self):
            color="#20b060" if self.path=="/green" else "#e02020"
            data=(f'<title>ScreenRec {self.path}</title><body style="background:{color}">'
                  '<span id="clock"></span><script>setInterval(()=>clock.textContent=Date.now(),100)</script>').encode()
            self.send_response(200); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    server=ThreadingHTTPServer(("127.0.0.1",0),Fixture)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    worker=BrowserWorker(Settings(output_dir=str(output),fps=15))
    errors,saved=[],[]
    worker.failed.connect(errors.append); worker.recording_saved.connect(saved.append)
    worker.start()
    try:
        deadline=time.monotonic()+20
        while worker.session is None and time.monotonic()<deadline:
            qt.processEvents(); time.sleep(.02)
        assert worker.session
        with sync_playwright() as p:
            context=p.chromium.launch_persistent_context(str(output/"profile"),channel="chromium",headless=True,
                args=["--enable-unsafe-extension-debugging","--disable-background-timer-throttling"],ignore_default_args=["--disable-extensions"])
            try:
                cdp=context.browser.new_browser_cdp_session()
                extension=cdp.send("Extensions.loadUnpacked",{"path":str(root/"src/screenrec/browser_extension")})["id"]
                page=context.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/green")
                page.bring_to_front()
                targets=cdp.send("Target.getTargets",{"filter":[{"type":"tab"},{"exclude":True}]})["targetInfos"]
                target=next(t for t in targets if "/green" in t["url"])
                cdp.send("Extensions.triggerAction",{"id":extension,"targetId":target["targetId"]})
                deadline=time.monotonic()+10
                popup=None
                while time.monotonic()<deadline:
                    popup=next((x for x in context.pages if x.url.endswith("/popup.html")),None)
                    if popup: break
                    page.wait_for_timeout(100)
                if popup is None:
                    popup = context.new_page()
                    popup.goto(f"chrome-extension://{extension}/popup.html")
                    page.bring_to_front()
                popup.evaluate("(code) => { document.querySelector('#code').value=code; document.querySelector('#start').click(); }", worker.session.pairing_code)
                try:
                    from playwright.sync_api import expect
                    expect(popup.locator("#status")).to_contain_text("Запись началась",timeout=15000)
                except Exception:
                    print("Popup error:",popup.locator("#status").inner_text(),flush=True)
                    raise
                page.wait_for_timeout(1000)
                other=context.new_page()
                other.goto(f"http://127.0.0.1:{server.server_port}/red")
                other.bring_to_front()
                other.wait_for_timeout(1800)
                worker.stop()
                deadline=time.monotonic()+30
                while worker.isRunning() and time.monotonic()<deadline:
                    qt.processEvents(); other.wait_for_timeout(50)
                qt.processEvents()
                assert not worker.isRunning(),"Worker did not finish"
                assert not errors,errors
                assert saved,"No browser recording"
            finally:
                context.close()
        decoded=subprocess.run([get_ffmpeg_exe(),"-v","error","-i",saved[0],"-vf","select=eq(n\\,30)",
                                "-frames:v","1","-f","rawvideo","-pix_fmt","bgra","-"],capture_output=True,check=True)
        import numpy as np
        pixels=np.frombuffer(decoded.stdout,dtype=np.uint8).reshape(-1,4)
        assert len(pixels)
        green=((pixels[:,1]>120)&(pixels[:,1].astype(float)>pixels[:,2]*1.2)).mean()
        red=((pixels[:,2]>120)&(pixels[:,2].astype(float)>pixels[:,1]*1.2)).mean()
        assert green>.6 and red<.02, f"Tab switching changed source: green={green}, red={red}"
        (output/"report.json").write_text(json.dumps({"ok":True,"file":saved[0],"green_ratio":float(green),"extension":extension},indent=2))
        print("Real tabCapture passed: switching to another tab preserved the selected green tab.")
    finally:
        worker.stop()
        worker.wait(30000)
        server.shutdown(); server.server_close()


if __name__=="__main__":
    main()
