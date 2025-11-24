import webview
import threading
import uvicorn
import time
from backend.app import app

def start_server():
    uvicorn.run(app, port=8000, log_level="error")

if __name__ == '__main__':
    # Start FastAPI backend in a separate thread
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()

    # Wait for server to start
    time.sleep(1)

    # Create desktop window with PyWebView
    webview.create_window(
        'Open Whisper',
        'http://localhost:8000',
        width=800,
        height=600
    )
    webview.start()
