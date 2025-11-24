from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import pyautogui
import pyperclip
import time
import os
import tempfile
import numpy as np
from datetime import datetime
from .service import TranscriptionService
from .config import load_config, save_config, update_config

app = FastAPI()

class PasteRequest(BaseModel):
    text: str

@app.post("/paste")
async def paste_to_cursor(request: PasteRequest):
    # Copy to clipboard
    pyperclip.copy(request.text)
    
    # Give focus back to the previous window (heuristic: wait a bit)
    # In a real desktop app scenario, the window manager handles focus.
    # With pywebview, we might need to minimize or hide, but for now let's just paste.
    # The user will likely have the target window active if we use a global shortcut,
    # but here we are clicking a button in the app.
    # So the user has to click the button, then quickly switch? 
    # No, the request is "Paste to Cursor". Ideally the app is a floating window or side panel.
    # Or, we hide the app window momentarily?
    # Let's just simulate the paste command.
    
    # Wait a tiny bit to ensure clipboard is ready
    time.sleep(0.1)
    
    # Simulate Cmd+V (Mac) or Ctrl+V (Windows/Linux)
    # Since user is on Mac (from system info):
    pyautogui.hotkey('command', 'v')
    
    return {"status": "pasted"}

@app.post("/toggle_listening")
async def toggle_listening():
    service.listening = not service.listening
    return {"listening": service.listening}

class SaveRequest(BaseModel):
    transcripts: list

@app.post("/save_transcript")
async def save_transcript(request: SaveRequest):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"transcript-{timestamp}.jsonl"
    
    # Create transcripts directory if it doesn't exist
    save_dir = os.path.join(os.getcwd(), "transcripts")
    os.makedirs(save_dir, exist_ok=True)
    
    filepath = os.path.join(save_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        for t in request.transcripts:
            f.write(json.dumps(t) + "\n")
            
    return {"path": filepath}

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("backend/static/index.html")

service = TranscriptionService()

class ConfigUpdate(BaseModel):
    key: str
    value: str | int | float | bool

@app.on_event("startup")
async def startup_event():
    service.start()

@app.on_event("shutdown")
async def shutdown_event():
    service.stop()

@app.get("/config")
async def get_config():
    return load_config()

@app.post("/config")
async def set_config(update: ConfigUpdate):
    update_config(update.key, update.value)
    # Restart service to apply changes
    service.stop()
    service.start()
    return {"status": "updated"}

@app.get("/queue_status")
async def get_queue_status():
    return service.get_queue_status()

@app.post("/transcribe_file")
async def transcribe_file(file: UploadFile = File(...)):
    """Transcribe an uploaded audio file"""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Use the transcription model to transcribe the file
        if not service.transcribe_model:
            from whisper_ctranslate2.transcribe import Transcribe, TranscriptionOptions
            service.transcribe_model = Transcribe(
                model_path=service.config.get("model", "turbo"),
                device="auto",
                device_index=0,
                compute_type="int8",
                threads=4,
                cache_directory=None,
                local_files_only=False,
                batched=False
            )

        from whisper_ctranslate2.transcribe import TranscriptionOptions
        options = TranscriptionOptions(
            beam_size=5,
            best_of=5,
            patience=1,
            length_penalty=1,
            repetition_penalty=1,
            no_repeat_ngram_size=0,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            condition_on_previous_text=True,
            prompt_reset_on_temperature=0.5,
            initial_prompt=None,
            prefix=None,
            suppress_blank=True,
            suppress_tokens=[-1],
            word_timestamps=False,
            prepend_punctuations="\"'"¿([{-",
            append_punctuations="\"'.。,，!！?？:：")]}、",
            temperature=0.0,
            hotwords=None,
            print_colors=False,
            hallucination_silence_threshold=None,
            vad_threshold=None,
            multilingual=False,
            vad_filter=service.config.get("vad_filter", True),
            vad_min_speech_duration_ms=service.config.get("vad_min_speech_duration_ms", 1500),
            vad_max_speech_duration_s=service.config.get("vad_max_speech_duration_s", 30),
            vad_min_silence_duration_ms=service.config.get("vad_min_silence_duration_ms", 500),
        )

        # Transcribe the file
        result = service.transcribe_model.inference(
            audio=tmp_path,
            task="transcribe",
            language=service.config.get("language", "en"),
            verbose=False,
            live=False,
            options=options,
        )

        # Clean up temp file
        os.unlink(tmp_path)

        return {"text": result['text'].strip(), "filename": file.filename}

    except Exception as e:
        # Clean up temp file if it exists
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        raise Exception(f"Error transcribing file: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Priority 1: Check high-priority queue (text, status, queue updates)
            if not service.queue.empty():
                data = service.queue.get()
                await websocket.send_json(data)
            # Priority 2: Check volume queue only if main queue is empty
            elif not service.volume_queue.empty():
                data = service.volume_queue.get()
                await websocket.send_json(data)
            else:
                await asyncio.sleep(0.01)  # Reduced sleep time for better responsiveness
    except WebSocketDisconnect:
        pass
