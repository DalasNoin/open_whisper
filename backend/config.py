import json
import os
from typing import Dict, Any

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "model": "turbo",
    "language": "en",
    "live_volume_threshold": 0.02,
    "vad_filter": True,
    "vad_min_speech_duration_ms": 1500,
    "vad_min_silence_duration_ms": 900,
    "vad_max_speech_duration_s": 30,
    "live_transcribe": True,
    "silence_duration_ms": 1000
}

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return DEFAULT_CONFIG

def save_config(config: Dict[str, Any]):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def update_config(key: str, value: Any):
    config = load_config()
    config[key] = value
    save_config(config)
