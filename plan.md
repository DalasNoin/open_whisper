# Open Whisper - Project Plan

## Overview
Open Whisper is a **local, real-time speech-to-text desktop application** built with Python. It provides live transcription with visual feedback, configurable settings, and the ability to paste transcribed text directly into other applications.

## Technology Stack

### Backend
- **Python 3.x** - Core runtime
- **FastAPI** - Web framework for REST API and WebSocket communication
- **Uvicorn** - ASGI server
- **whisper-ctranslate2** - Local speech recognition engine (OpenAI Whisper optimized)
- **sounddevice** - Audio input capture
- **numpy** - Audio processing
- **pywebview** - Desktop window wrapper
- **pyautogui** - Keyboard automation for "Paste to Cursor"
- **pyperclip** - Clipboard management

### Frontend
- **Static HTML/CSS/JavaScript** - No build step required
- **Lucide Icons** - Icon library (CDN)
- **WebSocket** - Real-time communication with backend

### Models
- **Whisper Turbo** (default) - Fast, high-quality transcription
- Supports: tiny, base, small, medium, large-v2, turbo

## Architecture

```
┌─────────────────────────────────────────┐
│         PyWebView Desktop Window        │
│  ┌───────────────────────────────────┐  │
│  │   Static HTML/CSS/JS Frontend     │  │
│  │   - WebSocket client              │  │
│  │   - Audio visualizer              │  │
│  │   - Settings UI                   │  │
│  └───────────────────────────────────┘  │
│              ↕ WebSocket                │
│  ┌───────────────────────────────────┐  │
│  │      FastAPI Backend              │  │
│  │   - REST API endpoints            │  │
│  │   - WebSocket server              │  │
│  │   - Config management             │  │
│  └───────────────────────────────────┘  │
│              ↕                          │
│  ┌───────────────────────────────────┐  │
│  │   TranscriptionService            │  │
│  │   - Audio capture thread          │  │
│  │   - Worker thread (transcription) │  │
│  │   - Queue management              │  │
│  └───────────────────────────────────┘  │
│              ↕                          │
│  ┌───────────────────────────────────┐  │
│  │   whisper-ctranslate2             │  │
│  │   - Model inference               │  │
│  │   - VAD (Voice Activity Detection)│  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Key Features

### Core Functionality
- **Real-time Transcription**: Live speech-to-text with minimal latency
- **Parallel Processing**: Separate threads for audio capture and transcription to prevent data loss
- **Queue Management**: Monitors backlog and drops old audio if system can't keep up
- **Voice Activity Detection**: Automatically detects speech and silence

### User Interface
- **Live Status Indicator**: Shows "Listening...", "Paused", or "Transcribing..."
- **Queue Monitor**: Displays pending transcription count with color-coded warnings
- **Audio Visualizer**: Real-time volume bar with threshold marker
- **Configurable Settings**:
  - Model selection (tiny → turbo)
  - Language
  - Volume threshold
  - Silence duration (pause detection)

### Output Options
- **Copy All**: Copy entire transcript to clipboard
- **Paste to Cursor**: Automatically paste transcript into active application
- **Save to JSONL**: Export transcript with timestamps to `transcripts/` directory

## Configuration

Default settings in `config.json`:
```json
{
  "model": "turbo",
  "language": "en",
  "live_volume_threshold": 0.02,
  "vad_filter": true,
  "vad_min_speech_duration_ms": 1500,
  "vad_min_silence_duration_ms": 900,
  "vad_max_speech_duration_s": 30,
  "live_transcribe": true,
  "silence_duration_ms": 1000
}
```

## Performance Optimizations

1. **Threaded Architecture**: Audio capture and transcription run in separate threads
2. **Queue-based Processing**: Audio buffers are queued for asynchronous processing
3. **Backlog Management**: Automatically drops old audio when queue exceeds 10 items
4. **Optimized VAD**: Tuned parameters for responsive speech detection
5. **No Throttling**: Volume updates sent immediately for instant visualizer feedback

## Requirements

### System Requirements
- **OS**: macOS (tested), Linux, Windows (should work)
- **Python**: 3.10+
- **Microphone**: Any audio input device
- **Permissions**: Microphone access, Accessibility (for "Paste to Cursor" on macOS)

### Python Dependencies
See `pyproject.toml` for full list. Key dependencies:
- fastapi
- uvicorn[standard]
- whisper-ctranslate2
- sounddevice
- numpy
- pywebview
- pyautogui
- pyperclip

## Installation & Usage

### Setup
```bash
# Install dependencies
uv sync

# Run the application
./start_app.sh
```

### Development Notes
- **ALWAYS use `uv` package manager** for all Python operations
- Run Python scripts: `uv run python script.py`
- Check syntax: `uv run python -m py_compile file.py`
- Install packages: `uv add package_name`

### First Run
1. Grant microphone permissions when prompted
2. Grant Accessibility permissions for "Paste to Cursor" (macOS)
3. Click the microphone icon to start listening
4. Speak naturally - transcription appears after brief pauses

## Project Structure

```
open_whisper/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── service.py          # TranscriptionService (core logic)
│   ├── config.py           # Configuration management
│   └── static/
│       ├── index.html      # Frontend UI
│       ├── app.js          # Frontend logic
│       └── style.css       # Styling
├── main.py                 # PyWebView entry point
├── start_app.sh            # Launch script
├── config.json             # User settings (auto-generated)
├── transcripts/            # Saved transcripts (auto-generated)
└── pyproject.toml          # Dependencies
```

## Known Limitations

1. **Model Performance**: Turbo model may be too slow for some hardware - switch to `base.en` for faster performance
2. **Continuous Speech**: Very long continuous speech may cause backlog - system will drop old audio to recover
3. **Paste to Cursor**: Requires Accessibility permissions on macOS
4. **Language Support**: Optimized for English, but supports multilingual models

## Future Enhancements

- [ ] Configurable keyboard shortcuts
- [ ] Real-time text editing/correction
- [ ] Speaker diarization
- [ ] Export to multiple formats (TXT, SRT, VTT)
- [ ] Custom model fine-tuning support
- [ ] GPU acceleration options
