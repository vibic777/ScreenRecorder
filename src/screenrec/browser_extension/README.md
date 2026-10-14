# ScreenRec browser extension

Local Chrome/Edge extension for recording the current browser tab with ScreenRec. Chrome/Edge 116 or newer is required. The extension is not published anywhere.

1. Open chrome://extensions or edge://extensions.
2. Enable Developer mode, choose **Load unpacked**, and select this folder.
3. In ScreenRec, choose **Browser tab** and **Start recording**. Copy the connection code.
4. Open the desired tab, click the extension icon, enter the code, and choose **Connect and record this tab**.
5. Stop recording from ScreenRec or the extension. Wait for video processing to finish.

Tab switching is allowed; capture remains attached to the original tab. Closing the original tab ends capture. Protected video and browser internal pages may be unavailable.

Audio settings are controlled in ScreenRec. The extension communicates only with 127.0.0.1 using a random per-session code. The code is valid only while the ScreenRec tab session is open.