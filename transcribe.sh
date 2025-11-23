#!/bin/bash
uv run whisper-ctranslate2 --live_transcribe True --language en --model turbo --live_volume_threshold 0.02 --vad_filter True --vad_min_speech_duration_ms 1500 --vad_min_silence_duration_ms 900 --vad_max_speech_duration_s 30 "$@"
