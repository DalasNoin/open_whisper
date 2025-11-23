import webview
import threading
import uvicorn
import time
import rumps
import os
from backend.app import app as fastapi_app
from backend.service import service

def start_server():
    uvicorn.run(fastapi_app, port=8000, log_level="error")

class OpenWhisperApp(rumps.App):
    def __init__(self):
        # Use a simple emoji for the menu bar icon
        super(OpenWhisperApp, self).__init__("🎤", quit_button=None)

        self.window = None
        self.server_thread = None
        self.window_visible = False

        # Menu items
        self.menu = [
            rumps.MenuItem("Show Window", callback=self.toggle_window),
            rumps.separator,
            rumps.MenuItem("Paste Transcripts (⌘⇧V)", callback=self.paste_transcripts),
            rumps.separator,
            rumps.MenuItem("Quit Open Whisper", callback=self.quit_app)
        ]

    def start_backend(self):
        """Start FastAPI server in background thread"""
        self.server_thread = threading.Thread(target=start_server, daemon=True)
        self.server_thread.start()
        time.sleep(1)  # Wait for server to start

    def toggle_window(self, _):
        """Show or hide the main window"""
        if self.window is None:
            # Create window first time
            self.window = webview.create_window(
                'Open Whisper',
                'http://localhost:8000',
                width=800,
                height=600,
                hidden=False
            )
            # Start webview in a separate thread
            webview_thread = threading.Thread(target=webview.start, daemon=False)
            webview_thread.start()
            self.window_visible = True
            self.menu["Show Window"].title = "Hide Window"
        else:
            # Toggle visibility
            if self.window_visible:
                self.window.hide()
                self.window_visible = False
                self.menu["Show Window"].title = "Show Window"
            else:
                self.window.show()
                self.window_visible = True
                self.menu["Show Window"].title = "Hide Window"

    def paste_transcripts(self, _):
        """Manually trigger paste (same as Cmd+Shift+V)"""
        if service.transcripts:
            import pyperclip
            import pyautogui
            text = '\n'.join(service.transcripts)
            pyperclip.copy(text)
            time.sleep(0.1)
            pyautogui.hotkey('command', 'v')
        else:
            rumps.notification(
                title="Open Whisper",
                subtitle="No transcripts yet",
                message="Start speaking to create transcripts"
            )

    def quit_app(self, _):
        """Quit the application"""
        rumps.quit_application()

if __name__ == '__main__':
    app = OpenWhisperApp()
    app.start_backend()
    app.run()
