const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

let transcripts = [];
let isListening = false; // Default to false
let config = {};
let ws = null;

// Initialize Lucide icons
lucide.createIcons();

// DOM Elements
const micBtn = document.getElementById('mic-btn');
const copyBtn = document.getElementById('copy-btn');
const pasteBtn = document.getElementById('paste-btn');
const saveBtn = document.getElementById('save-btn');
const settingsBtn = document.getElementById('settings-btn');
const transcriptView = document.getElementById('transcript-view');
const settingsPanel = document.getElementById('settings-panel');
const modelSelect = document.getElementById('model-select');
const languageInput = document.getElementById('language-input');
const volumeInput = document.getElementById('volume-input');
const statusIndicator = document.getElementById('status');
const queueStatusIndicator = document.getElementById('queue-status');

updateStatus();

// Event Listeners
micBtn.addEventListener('click', toggleListening);
copyBtn.addEventListener('click', copyToClipboard);
pasteBtn.addEventListener('click', pasteToCursor);
saveBtn.addEventListener('click', saveTranscript);
settingsBtn.addEventListener('click', toggleSettings);
modelSelect.addEventListener('change', (e) => updateConfig('model', e.target.value));
languageInput.addEventListener('change', (e) => updateConfig('language', e.target.value));
volumeInput.addEventListener('change', (e) => {
    const val = parseFloat(e.target.value);
    updateConfig('live_volume_threshold', val);
    updateThresholdMarker(val);
});
const silenceInput = document.getElementById('silence-input');
silenceInput.addEventListener('change', (e) => updateConfig('silence_duration_ms', parseInt(e.target.value)));

// Initialization
fetchConfig();
connectWebSocket();
updateMicButton(); // Set initial button state

async function fetchConfig() {
    try {
        const response = await fetch(`${API_URL}/config`);
        config = await response.json();
        renderConfig();
    } catch (error) {
        console.error('Failed to fetch config', error);
    }
}

function renderConfig() {
    if (config.model) modelSelect.value = config.model;
    if (config.language) languageInput.value = config.language;
    if (config.live_volume_threshold) {
        volumeInput.value = config.live_volume_threshold;
        updateThresholdMarker(config.live_volume_threshold);
    }
    if (config.silence_duration_ms) silenceInput.value = config.silence_duration_ms;
}

function updateThresholdMarker(threshold) {
    const marker = document.getElementById('visualizer-threshold');
    // Scale threshold to width percentage (same scale as visualizer: volume * 500)
    // Threshold is typically 0.01 - 0.1
    let left = Math.min(threshold * 500, 100);
    marker.style.left = `${left}%`;
}

function connectWebSocket() {
    ws = new WebSocket(WS_URL);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.text) {
            addTranscript(data.text);
            updateStatus("Transcribing...");
            setTimeout(() => updateStatus(), 2000); // Reset status after 2s
        } else if (data.volume !== undefined) {
            updateVisualizer(data.volume);
        } else if (data.status) {
            updateStatus(data.status);
        }

        if (data.queue_size !== undefined) {
            updateQueueStatus(data.queue_size);
        }

        if (data.queue_details) {
            updateQueueSidebar(data.queue_details);
        }
    };
    ws.onclose = () => {
        setTimeout(connectWebSocket, 1000);
    };
}

function addTranscript(text) {
    const timestamp = new Date();
    const transcript = { text, timestamp };
    transcripts.push(transcript);

    const item = document.createElement('div');
    item.className = 'transcript-item';
    item.innerHTML = `
        <span class="timestamp">${timestamp.toLocaleTimeString()}</span>
        <p>${text}</p>
    `;
    transcriptView.appendChild(item);
    item.scrollIntoView({ behavior: 'smooth' });
}

async function toggleListening() {
    try {
        const response = await fetch(`${API_URL}/toggle_listening`, { method: 'POST' });
        const data = await response.json();
        isListening = data.listening;
        updateMicButton();
        updateStatus();
    } catch (error) {
        console.error('Failed to toggle listening', error);
    }
}

function updateMicButton() {
    const icon = isListening ? 'mic' : 'mic-off';
    micBtn.innerHTML = `<i data-lucide="${icon}"></i>`;
    micBtn.title = isListening ? "Stop Listening" : "Start Listening";
    micBtn.style.color = isListening ? '#ff4444' : 'inherit'; // Red when recording
    lucide.createIcons();
}

function updateStatus(text) {
    if (text) statusIndicator.textContent = text;
    else statusIndicator.textContent = isListening ? 'Listening...' : 'Paused';

    statusIndicator.style.color = text === 'Transcribing...' ? '#646cff' : '#888';
}

function updateQueueStatus(size) {
    queueStatusIndicator.textContent = `Queue: ${size}`;

    if (size > 0) {
        queueStatusIndicator.style.display = 'block';
        if (size > 5) queueStatusIndicator.style.color = '#ff4444'; // Red
        else if (size > 2) queueStatusIndicator.style.color = '#ffaa00'; // Yellow
        else queueStatusIndicator.style.color = '#888'; // Grey
    } else {
        queueStatusIndicator.style.display = 'none';
    }
}

function updateVisualizer(volume) {
    const bar = document.getElementById('visualizer-bar');
    // Normalize volume (heuristic)
    // Volume usually ranges 0.0 to 1.0, but speech is often low (0.01 - 0.2)
    // Let's scale it up for visibility
    let width = Math.min(volume * 500, 100);
    bar.style.width = `${width}%`;

    // Change color based on threshold
    const threshold = config.live_volume_threshold || 0.02;
    if (volume > threshold) {
        bar.style.backgroundColor = '#44ff44'; // Green when speaking
    } else {
        bar.style.backgroundColor = '#646cff'; // Blue when silent/noise
    }
}

function copyToClipboard() {
    const text = transcripts.map(t => t.text).join('\n');
    navigator.clipboard.writeText(text);
}

async function pasteToCursor() {
    const text = transcripts.map(t => t.text).join('\n');
    try {
        await fetch(`${API_URL}/paste`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
    } catch (error) {
        console.error('Failed to paste', error);
    }
}

async function saveTranscript() {
    try {
        const response = await fetch(`${API_URL}/save_transcript`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcripts })
        });
        const data = await response.json();
        alert(`Transcript saved to:\n${data.path}`);
    } catch (error) {
        console.error('Failed to save transcript', error);
        alert('Failed to save transcript');
    }
}

function toggleSettings() {
    const isHidden = settingsPanel.style.display === 'none';
    settingsPanel.style.display = isHidden ? 'block' : 'none';
}

async function updateConfig(key, value) {
    try {
        await fetch(`${API_URL}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, value })
        });
        config[key] = value;
    } catch (error) {
        console.error('Failed to update config', error);
    }
}

function updateQueueSidebar(queueDetails) {
    // Update stats
    if (queueDetails.stats) {
        document.getElementById('stat-total-processed').textContent = queueDetails.stats.total_processed;
        document.getElementById('stat-avg-time').textContent = `${queueDetails.stats.avg_processing_time}s`;
        document.getElementById('stat-dropped').textContent = queueDetails.stats.items_dropped;
    }

    // Update queue size badge
    const queueSize = queueDetails.queued_items ? queueDetails.queued_items.length : 0;
    const badge = document.getElementById('queue-size-badge');
    badge.textContent = queueSize;
    if (queueSize > 5) {
        badge.style.backgroundColor = '#ff4444';
    } else if (queueSize > 2) {
        badge.style.backgroundColor = '#ffaa00';
    } else {
        badge.style.backgroundColor = 'var(--accent-color)';
    }

    // Update processing items
    const processingContainer = document.getElementById('processing-items');
    if (queueDetails.processing_items && queueDetails.processing_items.length > 0) {
        processingContainer.innerHTML = queueDetails.processing_items.map(item =>
            createQueueItemHTML(item, 'processing')
        ).join('');
    } else {
        processingContainer.innerHTML = '<div class="empty-state">No items processing</div>';
    }

    // Update queued items
    const queuedContainer = document.getElementById('queued-items');
    if (queueDetails.queued_items && queueDetails.queued_items.length > 0) {
        queuedContainer.innerHTML = queueDetails.queued_items.map(item =>
            createQueueItemHTML(item, 'queued')
        ).join('');
    } else {
        queuedContainer.innerHTML = '<div class="empty-state">No items in queue</div>';
    }

    // Update history
    if (queueDetails.processing_history && queueDetails.processing_history.length > 0) {
        const historyContainer = document.getElementById('history-items');
        historyContainer.innerHTML = queueDetails.processing_history.slice(-10).reverse().map(item => {
            const timestamp = new Date(item.timestamp);
            return `
                <div class="queue-item completed">
                    <div class="queue-item-header">
                        <span class="queue-item-id">#${item.id}</span>
                        <span class="queue-item-time">${timestamp.toLocaleTimeString()}</span>
                    </div>
                    <div class="queue-item-info">${item.processing_time}s • ${item.text_length} chars</div>
                </div>
            `;
        }).join('');
    }
}

function createQueueItemHTML(item, type) {
    const timestamp = new Date(item.timestamp);
    const timeStr = timestamp.toLocaleTimeString();
    const durationStr = item.duration_seconds ? `${item.duration_seconds.toFixed(1)}s` : '';
    const processingTimeStr = item.processing_time ? `${item.processing_time}s` : '';

    let info = '';
    if (type === 'processing' && processingTimeStr) {
        info = `Processing: ${processingTimeStr}`;
    } else if (durationStr) {
        info = `Duration: ${durationStr}`;
    }

    return `
        <div class="queue-item ${type}">
            <div class="queue-item-header">
                <span class="queue-item-id">#${item.id}</span>
                <span class="queue-item-time">${timeStr}</span>
            </div>
            ${info ? `<div class="queue-item-info">${info}</div>` : ''}
        </div>
    `;
}

// Fetch initial queue status
async function fetchQueueStatus() {
    try {
        const response = await fetch(`${API_URL}/queue_status`);
        const queueStatus = await response.json();
        updateQueueSidebar({
            queued_items: queueStatus.queued_items,
            processing_items: queueStatus.processing_items,
            stats: queueStatus.stats
        });

        // Update history
        if (queueStatus.processing_history && queueStatus.processing_history.length > 0) {
            const historyContainer = document.getElementById('history-items');
            historyContainer.innerHTML = queueStatus.processing_history.slice(-10).reverse().map(item => {
                const timestamp = new Date(item.timestamp);
                return `
                    <div class="queue-item completed">
                        <div class="queue-item-header">
                            <span class="queue-item-id">#${item.id}</span>
                            <span class="queue-item-time">${timestamp.toLocaleTimeString()}</span>
                        </div>
                        <div class="queue-item-info">${item.processing_time}s • ${item.text_length} chars</div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('Failed to fetch queue status', error);
    }
}

// Fetch queue status on load and periodically
fetchQueueStatus();
setInterval(fetchQueueStatus, 5000); // Update every 5 seconds

// Drag and Drop File Transcription
const dropZone = document.getElementById('drop-zone');
const transcriptView = document.getElementById('transcript-view');

// Show drop zone when dragging files over the window
['dragenter', 'dragover'].forEach(eventName => {
    document.body.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.types.includes('Files')) {
            dropZone.classList.add('active');
        }
    });
});

['dragleave', 'drop'].forEach(eventName => {
    document.body.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('active', 'drag-over');
    });
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();

    const files = Array.from(e.dataTransfer.files);
    const audioFiles = files.filter(file =>
        file.type.startsWith('audio/') ||
        /\.(mp3|wav|m4a|ogg|flac|aac|wma)$/i.test(file.name)
    );

    if (audioFiles.length === 0) {
        alert('Please drop audio files (MP3, WAV, M4A, OGG, FLAC)');
        return;
    }

    for (const file of audioFiles) {
        await transcribeFile(file);
    }
});

async function transcribeFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Show progress
    const progressItem = document.createElement('div');
    progressItem.className = 'transcript-item';
    progressItem.innerHTML = `
        <span class="timestamp">${new Date().toLocaleTimeString()}</span>
        <p style="color: #888;">Transcribing ${file.name}...</p>
    `;
    transcriptView.appendChild(progressItem);
    progressItem.scrollIntoView({ behavior: 'smooth' });

    try {
        const response = await fetch(`${API_URL}/transcribe_file`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Remove progress indicator
        progressItem.remove();

        // Add transcript
        if (data.text) {
            addTranscript(`[${file.name}] ${data.text}`);
        }
    } catch (error) {
        console.error('Error transcribing file:', error);
        progressItem.querySelector('p').textContent = `Error transcribing ${file.name}: ${error.message}`;
        progressItem.querySelector('p').style.color = '#ff4444';
    }
}
