import threading
import queue
import time
import numpy as np
import sounddevice as sd
import sys
import site
import os
from datetime import datetime
from collections import deque
from pynput import keyboard
import pyperclip
import pyautogui

# Workaround for broken whisper-ctranslate2 package structure
# It installs into site-packages/src/whisper_ctranslate2 instead of site-packages/whisper_ctranslate2
for site_package in site.getsitepackages():
    src_path = os.path.join(site_package, "src")
    if os.path.exists(os.path.join(src_path, "whisper_ctranslate2")):
        sys.path.append(src_path)
        break

from whisper_ctranslate2.transcribe import Transcribe, TranscriptionOptions
from .config import load_config

# Constants from live.py
BlockSize = 30
Vocals = [50, 1000]
# EndBlocks is now dynamic based on config
FlushBlocks = 33 * 10

class TranscriptionService:
    def __init__(self):
        self.config = load_config()
        self.running = False
        self.listening = False # Default to not recording
        self.queue = queue.Queue() # WebSocket queue (high priority: text, status)
        self.volume_queue = queue.Queue(maxsize=5) # Low priority: volume updates (drop if full)
        self.audio_queue = queue.Queue() # Audio buffer queue
        self.thread = None
        self.worker_thread = None
        self.transcribe_model = None
        self.hotkey_listener = None

        # State for voice detection
        self.waiting = 0
        self.prevblock = self.buffer = np.zeros((0, 1))
        self.speaking = False
        self.blocks_speaking = 0

        # Queue metadata tracking
        self.queue_item_counter = 0
        self.queue_items = {}  # {item_id: {timestamp, buffer_size, status}}
        self.processing_stats = {
            'total_processed': 0,
            'total_processing_time': 0.0,
            'items_dropped': 0
        }
        self.processing_history = deque(maxlen=50)  # Last 50 processing events

        # Transcripts for hotkey paste
        self.transcripts = []
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.config = load_config() # Reload config on start

        # Start audio capture thread
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.start()

        # Start transcription worker thread
        self.worker_thread = threading.Thread(target=self._transcription_worker)
        self.worker_thread.start()

        # Start global hotkey listener (Cmd+Shift+V on macOS, Ctrl+Shift+V on others)
        self._start_hotkey_listener()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.worker_thread:
            self.worker_thread.join()
        if self.hotkey_listener:
            self.hotkey_listener.stop()

    def _start_hotkey_listener(self):
        """Start global hotkey listener for Cmd+Shift+V (macOS) or Ctrl+Shift+V"""
        def on_activate():
            """Paste transcripts when hotkey is pressed"""
            if self.transcripts:
                text = '\n'.join(self.transcripts)
                pyperclip.copy(text)
                time.sleep(0.1)
                # Cmd+V on macOS
                pyautogui.hotkey('command', 'v')

        # Use Cmd+Shift+V on macOS
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<cmd>+<shift>+v'),
            on_activate
        )

        def for_canonical(f):
            return lambda k: f(hotkey_listener.canonical(k))

        hotkey_listener = keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        )

        hotkey_listener.start()
        self.hotkey_listener = hotkey_listener
        print("Global hotkey Cmd+Shift+V registered for paste")
            
    def _is_there_voice(self, indata, frames, sample_rate):
        freq = (
            np.argmax(np.abs(np.fft.rfft(indata[:, 0])))
            * sample_rate
            / frames
        )
        volume = np.sqrt(np.mean(indata**2))
        return volume > self.config.get("live_volume_threshold", 0.02) and Vocals[0] <= freq <= Vocals[1]

    def _save_to_process(self):
        buffer_copy = self.buffer.copy()
        item_id = self.queue_item_counter
        self.queue_item_counter += 1

        # Track queue item metadata
        self.queue_items[item_id] = {
            'id': item_id,
            'timestamp': datetime.now().isoformat(),
            'buffer_size': len(buffer_copy),
            'duration_seconds': len(buffer_copy) / 16000,  # 16kHz sample rate
            'status': 'queued'
        }

        self.audio_queue.put((item_id, buffer_copy))
        self.buffer = np.zeros((0, 1))
        self.speaking = False

        # Notify queue size increase and send detailed queue info
        self._send_queue_update()

    def _callback(self, indata, frames, _time, status):
        if not self.listening:
            return

        if not any(indata):
            return

        sample_rate = 16000 # Default for whisper
        volume = np.sqrt(np.mean(indata**2))

        # Send volume update to low-priority queue (drop if full to avoid backlog)
        try:
            self.volume_queue.put_nowait({"volume": float(volume)})
        except queue.Full:
            pass  # Drop volume update if queue is full

        voice = self._is_there_voice(indata, frames, sample_rate)

        if not voice and not self.speaking:
            return

        if voice:
            if self.waiting < 1:
                self.buffer = self.prevblock.copy()

            self.buffer = np.concatenate((self.buffer, indata))
            
            # Calculate EndBlocks dynamically based on config
            silence_ms = self.config.get("silence_duration_ms", 1000)
            self.waiting = int(silence_ms / BlockSize)

            if not self.speaking:
                self.blocks_speaking = FlushBlocks

            self.speaking = True
        else:
            self.waiting -= 1
            if self.waiting < 1:
                self._save_to_process()
                return
            else:
                self.buffer = np.concatenate((self.buffer, indata))

        self.blocks_speaking -= 1
        if self.blocks_speaking < 1:
            self._save_to_process()

    def _send_queue_update(self):
        """Send detailed queue status update via WebSocket"""
        queued_items = [item for item in self.queue_items.values() if item['status'] == 'queued']
        processing_items = [item for item in self.queue_items.values() if item['status'] == 'processing']

        avg_processing_time = 0
        if self.processing_stats['total_processed'] > 0:
            avg_processing_time = self.processing_stats['total_processing_time'] / self.processing_stats['total_processed']

        self.queue.put({
            'queue_size': len(queued_items),
            'queue_details': {
                'queued_items': queued_items,
                'processing_items': processing_items,
                'stats': {
                    'total_processed': self.processing_stats['total_processed'],
                    'avg_processing_time': round(avg_processing_time, 2),
                    'items_dropped': self.processing_stats['items_dropped']
                },
                'processing_history': list(self.processing_history)
            }
        })

    def get_queue_status(self):
        """Get current queue status for API endpoint"""
        queued_items = [item for item in self.queue_items.values() if item['status'] == 'queued']
        processing_items = [item for item in self.queue_items.values() if item['status'] == 'processing']

        avg_processing_time = 0
        if self.processing_stats['total_processed'] > 0:
            avg_processing_time = self.processing_stats['total_processing_time'] / self.processing_stats['total_processed']

        return {
            'queue_size': len(queued_items),
            'queued_items': queued_items,
            'processing_items': processing_items,
            'stats': {
                'total_processed': self.processing_stats['total_processed'],
                'avg_processing_time': round(avg_processing_time, 2),
                'items_dropped': self.processing_stats['items_dropped']
            },
            'processing_history': list(self.processing_history)
        }

    def _transcription_worker(self):
        while self.running:
            item_id = None
            try:
                # Check queue size to prevent infinite backlog
                qsize = self.audio_queue.qsize()
                if qsize > 5:
                    print(f"Warning: Transcription queue backlog: {qsize} items")

                if qsize > 10:
                    print("Error: Queue too large, dropping old items to catch up")
                    # Drop items until we have 5 left to avoid clearing everything
                    items_to_drop = qsize - 5
                    for _ in range(items_to_drop):
                        try:
                            dropped_item_id, _ = self.audio_queue.get_nowait()
                            if dropped_item_id in self.queue_items:
                                self.queue_items[dropped_item_id]['status'] = 'dropped'
                                self.processing_stats['items_dropped'] += 1
                        except queue.Empty:
                            break
                    self._send_queue_update()

                # Wait for audio buffer with timeout to check self.running
                item_id, _buffer = self.audio_queue.get(timeout=1)

                # Update item status to processing
                if item_id in self.queue_items:
                    self.queue_items[item_id]['status'] = 'processing'
                    self.queue_items[item_id]['processing_start'] = datetime.now().isoformat()

                # Notify frontend of status and send queue update
                self.queue.put({"status": "Transcribing..."})
                self._send_queue_update()

            except queue.Empty:
                continue
            
            if not self.transcribe_model:
                # Initialize model
                self.transcribe_model = Transcribe(
                    model_path=self.config.get("model", "turbo"),
                    device="auto",
                    device_index=0,
                    compute_type="int8",
                    threads=4,
                    cache_directory=None,
                    local_files_only=False,
                    batched=False
                )

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
                prepend_punctuations="\"'“¿([{-",
                append_punctuations="\"'.。,，!！?？:：”)]}、",
                temperature=0.0,
                hotwords=None,
                print_colors=False,
                hallucination_silence_threshold=None,
                vad_threshold=None,
                multilingual=False,
                vad_filter=self.config.get("vad_filter", True),
                vad_min_speech_duration_ms=self.config.get("vad_min_speech_duration_ms", 1500),
                vad_max_speech_duration_s=self.config.get("vad_max_speech_duration_s", 30),
                vad_min_silence_duration_ms=self.config.get("vad_min_silence_duration_ms", 500),
            )

            # Track processing time
            processing_start_time = time.time()

            try:
                result = self.transcribe_model.inference(
                    audio=_buffer.flatten().astype("float32"),
                    task="transcribe",
                    language=self.config.get("language", "en"),
                    verbose=False,
                    live=False, # Changed to False to force immediate transcription
                    options=options,
                )

                processing_time = time.time() - processing_start_time

                # Update processing stats
                if item_id is not None and item_id in self.queue_items:
                    self.queue_items[item_id]['status'] = 'completed'
                    self.queue_items[item_id]['processing_time'] = round(processing_time, 2)
                    self.queue_items[item_id]['processing_end'] = datetime.now().isoformat()

                    # Add to processing history
                    self.processing_history.append({
                        'id': item_id,
                        'timestamp': self.queue_items[item_id]['timestamp'],
                        'processing_time': round(processing_time, 2),
                        'text_length': len(result['text'].strip()) if result['text'].strip() else 0
                    })

                    # Update stats
                    self.processing_stats['total_processed'] += 1
                    self.processing_stats['total_processing_time'] += processing_time

                    # Clean up old completed items (keep last 100)
                    if len(self.queue_items) > 100:
                        completed_ids = [k for k, v in self.queue_items.items() if v['status'] == 'completed']
                        completed_ids.sort()
                        for old_id in completed_ids[:-50]:  # Keep last 50 completed items
                            del self.queue_items[old_id]

                if result['text'].strip():
                    text = result['text'].strip()
                    self.queue.put({"text": text})
                    # Add to transcripts for hotkey paste
                    self.transcripts.append(text)

                # Send queue update after completion
                self._send_queue_update()

            except Exception as e:
                print(f"Error during transcription: {e}")
                if item_id is not None and item_id in self.queue_items:
                    self.queue_items[item_id]['status'] = 'error'
                    self.queue_items[item_id]['error'] = str(e)
                    self._send_queue_update()

    def _run_loop(self):
        sample_rate = 16000
        block_size = int(sample_rate * BlockSize / 1000)
        
        with sd.InputStream(
            channels=1,
            callback=self._callback,
            blocksize=block_size,
            samplerate=sample_rate,
        ):
            while self.running:
                time.sleep(0.1)
