"""HTML templates for web UI."""

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Adapter</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; margin-bottom: 5px; }
        .subtitle { color: #666; margin-bottom: 20px; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        label { display: block; margin-bottom: 5px; font-weight: 500; color: #333; }
        textarea, input, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        textarea { min-height: 100px; resize: vertical; }
        .row { display: flex; gap: 15px; }
        .row > div { flex: 1; }
        button {
            background: #4CAF50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        button:hover { background: #45a049; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .result {
            margin-top: 20px;
            padding: 15px;
            background: #e8f5e9;
            border-radius: 4px;
            display: none;
        }
        .result.error { background: #ffebee; }
        audio { width: 100%; margin: 10px 0; }
        .download-btn {
            background: #2196F3;
            display: inline-block;
            padding: 8px 16px;
            text-decoration: none;
            color: white;
            border-radius: 4px;
            margin-top: 10px;
        }
        .status { padding: 10px; background: #e3f2fd; border-radius: 4px; margin-bottom: 15px; font-size: 13px; }
        .status.ok { background: #e8f5e9; }
        .status.error { background: #ffebee; }
        .hint { font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 15px; }
        .tabs { display: flex; gap: 5px; margin-bottom: 0; }
        .tab {
            padding: 10px 20px;
            background: #e0e0e0;
            border: 1px solid #ccc;
            border-bottom: none;
            border-radius: 4px 4px 0 0;
            cursor: pointer;
            font-weight: 500;
            color: #666;
        }
        .tab:hover { background: #f0f0f0; }
        .tab.active {
            background: white;
            color: #333;
            border-bottom: 1px solid white;
            margin-bottom: -1px;
            position: relative;
        }
        .tab-content { display: none; border-top: 1px solid #ccc; padding-top: 15px; }
        .tab-content.active { display: block; }
        /* Model selector */
        .model-selector {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
            padding: 10px;
            background: #fff3e0;
            border-radius: 4px;
            font-size: 13px;
        }
        .model-selector select {
            width: auto;
            margin: 0;
            padding: 5px 10px;
            font-size: 13px;
        }
        .model-selector label {
            margin: 0;
            font-weight: 600;
        }
        /* Modal dialog */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: white;
            border-radius: 8px;
            padding: 24px;
            max-width: 450px;
            width: 90%;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .modal h3 { margin-top: 0; color: #f57c00; }
        .modal p { color: #666; line-height: 1.5; }
        .modal-buttons { display: flex; gap: 10px; margin-top: 20px; }
        .modal-buttons button { flex: 1; }
        .btn-cancel { background: #9e9e9e; }
        .btn-cancel:hover { background: #757575; }
        .btn-confirm { background: #f57c00; }
        .btn-confirm:hover { background: #ef6c00; }
        /* Loading overlay */
        .loading-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.95);
            z-index: 2000;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .loading-overlay.active { display: flex; }
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #e0e0e0;
            border-top-color: #4CAF50;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text {
            margin-top: 20px;
            font-size: 18px;
            color: #333;
        }
        .loading-hint {
            margin-top: 10px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>TTS Adapter</h1>
    <p class="subtitle">Text-to-Speech Generation</p>

    <div id="status" class="status">Checking server status...</div>

    <div class="model-selector">
        <label>Model:</label>
        <select id="model-select" onchange="onModelSelect(this.value)">
            <option value="">Loading...</option>
        </select>
        <span id="model-features"></span>
    </div>

    <!-- Loading overlay -->
    <div id="loading-overlay" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">Switching model...</div>
        <div class="loading-hint">This may take 1-2 minutes. Please wait.</div>
    </div>

    <!-- Confirmation modal -->
    <div id="modal-overlay" class="modal-overlay">
        <div class="modal">
            <h3>Switch Model?</h3>
            <p id="modal-message">This will reload the TTS model. The server will be unavailable for ~2 minutes during reload.</p>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="cancelSwitch()">Cancel</button>
                <button class="btn-confirm" onclick="confirmSwitch()">Switch Model</button>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('simple')">Simple</button>
            <button class="tab" onclick="switchTab('design')">Voice Design</button>
            <button class="tab" onclick="switchTab('clone')">Voice Clone</button>
        </div>

        <!-- Simple TTS Tab -->
        <div id="tab-simple" class="tab-content active">
            <label for="text">Text to speak</label>
            <textarea id="text" placeholder="Enter text here..."></textarea>

            <div class="row">
                <div>
                    <label for="language">Language</label>
                    <select id="language">
                        <option value="Russian">Russian</option>
                        <option value="English">English</option>
                        <option value="Chinese">Chinese</option>
                        <option value="Japanese">Japanese</option>
                        <option value="Korean">Korean</option>
                        <option value="German">German</option>
                        <option value="French">French</option>
                        <option value="Spanish">Spanish</option>
                        <option value="Italian">Italian</option>
                        <option value="Portuguese">Portuguese</option>
                    </select>
                </div>
                <div>
                    <label for="speaker">Speaker</label>
                    <select id="speaker">
                        <option value="Serena">Serena (Female, warm)</option>
                        <option value="Sohee">Sohee (Female, emotional)</option>
                        <option value="Vivian">Vivian (Female, bright)</option>
                        <option value="Ono_Anna">Ono_Anna (Female, playful)</option>
                        <option value="Ryan">Ryan (Male, dynamic)</option>
                        <option value="Aiden">Aiden (Male, clear)</option>
                        <option value="Uncle_Fu">Uncle_Fu (Male, mellow)</option>
                        <option value="Dylan">Dylan (Male, youthful)</option>
                        <option value="Eric">Eric (Male, lively)</option>
                    </select>
                </div>
            </div>

            <label for="instruct">Style instruction (optional)</label>
            <input type="text" id="instruct" placeholder="e.g., Speak slowly and warmly">
            <p class="hint">Control tone, emotion, speed. Works with CustomVoice model only.</p>

            <button onclick="generateSimple()">Generate Speech</button>
        </div>

        <!-- Voice Design Tab -->
        <div id="tab-design" class="tab-content">
            <label for="design-text">Text to speak</label>
            <textarea id="design-text" placeholder="Enter text here..."></textarea>

            <label for="design-language">Language</label>
            <select id="design-language">
                <option value="Russian">Russian</option>
                <option value="English">English</option>
                <option value="Chinese">Chinese</option>
            </select>

            <label for="design-instruct">Voice description (required)</label>
            <textarea id="design-instruct" placeholder="e.g., Adult female voice, contralto range, warm and confident, expressive"></textarea>
            <p class="hint">Describe the voice: gender, age, pitch, timbre, emotion, pace.</p>

            <button onclick="generateDesign()">Generate with Designed Voice</button>
        </div>

        <!-- Voice Clone Tab -->
        <div id="tab-clone" class="tab-content">
            <label for="clone-text">Text to speak</label>
            <textarea id="clone-text" placeholder="Enter text here..."></textarea>

            <label for="clone-language">Language</label>
            <select id="clone-language">
                <option value="Russian">Russian</option>
                <option value="English">English</option>
                <option value="Chinese">Chinese</option>
            </select>

            <label for="clone-audio">Reference audio (WAV, 3-10 sec)</label>
            <input type="file" id="clone-audio" accept=".wav,audio/wav">

            <label for="clone-ref-text">Reference transcript (optional, improves quality)</label>
            <input type="text" id="clone-ref-text" placeholder="What is said in the reference audio">

            <button onclick="generateClone()">Generate with Cloned Voice</button>
        </div>

        <div id="result" class="result">
            <strong>Result:</strong>
            <audio id="audio" controls></audio>
            <br>
            <a id="download" class="download-btn" download="tts_output.wav">Download WAV</a>
        </div>
    </div>

    <p style="text-align: center; color: #999; font-size: 12px;">
        <a href="/docs" style="color: #666;">API Documentation</a> |
        <a href="/health" style="color: #666;">Health Check</a>
    </p>

<script>
let serverInfo = {};
let availableModels = [];
let pendingModelId = null;

async function checkStatus() {
    const status = document.getElementById('status');
    try {
        const res = await fetch('/health');
        const data = await res.json();
        serverInfo = data;
        status.className = 'status ok';
        status.innerHTML = `<strong>Server OK</strong> | Engine: ${data.engine} | ` +
            `Simple: ${data.supports_custom_voice ? 'Yes' : 'No'} | ` +
            `Design: ${data.supports_design ? 'Yes' : 'No'} | ` +
            `Clone: ${data.supports_cloning ? 'Yes' : 'No'}`;
        updateTabAvailability(data);
        await loadModels();
    } catch (e) {
        status.className = 'status error';
        status.textContent = 'Server not responding. Start with: make serve';
    }
}

async function loadModels() {
    try {
        const res = await fetch('/models');
        const data = await res.json();
        availableModels = data.available;
        const select = document.getElementById('model-select');
        select.innerHTML = '';
        data.available.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.name;
            if (m.id === data.current) opt.selected = true;
            select.appendChild(opt);
        });
        updateModelFeatures(data.current);
    } catch (e) {
        console.error('Failed to load models:', e);
    }
}

function updateModelFeatures(modelId) {
    const model = availableModels.find(m => m.id === modelId);
    const features = document.getElementById('model-features');
    if (model) {
        const caps = [];
        if (model.supports_custom_voice) caps.push('Simple');
        if (model.supports_design) caps.push('Design');
        if (model.supports_cloning) caps.push('Clone');
        features.textContent = caps.length ? `(${caps.join(', ')})` : '';
    }
}

function onModelSelect(modelId) {
    if (modelId === serverInfo.model) return;
    pendingModelId = modelId;
    const model = availableModels.find(m => m.id === modelId);
    document.getElementById('modal-message').innerHTML =
        `Switch to <strong>${model?.name || modelId}</strong>?<br><br>` +
        `This will reload the TTS model. Server unavailable for ~2 minutes.`;
    document.getElementById('modal-overlay').classList.add('active');
}

function cancelSwitch() {
    document.getElementById('modal-overlay').classList.remove('active');
    // Reset select to current model
    document.getElementById('model-select').value = serverInfo.model;
    pendingModelId = null;
}

async function confirmSwitch() {
    document.getElementById('modal-overlay').classList.remove('active');
    document.getElementById('loading-overlay').classList.add('active');

    try {
        const res = await fetch('/model/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: pendingModelId })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Switch failed');
        }

        const data = await res.json();
        // Update serverInfo with new capabilities
        serverInfo.model = data.model;
        serverInfo.supports_cloning = data.supports_cloning;
        serverInfo.supports_design = data.supports_design;
        serverInfo.supports_custom_voice = data.supports_custom_voice;

        // Update UI
        await checkStatus();

    } catch (e) {
        alert('Failed to switch model: ' + e.message);
        document.getElementById('model-select').value = serverInfo.model;
    } finally {
        document.getElementById('loading-overlay').classList.remove('active');
        pendingModelId = null;
    }
}

function updateTabAvailability(data) {
    const simpleTab = document.querySelector('[onclick="switchTab(\\'simple\\')"]');
    const designTab = document.querySelector('[onclick="switchTab(\\'design\\')"]');
    const cloneTab = document.querySelector('[onclick="switchTab(\\'clone\\')"]');

    // Style unavailable tabs as disabled
    if (!data.supports_custom_voice) {
        simpleTab.style.opacity = '0.5';
        simpleTab.title = 'Requires CustomVoice model';
    }
    if (!data.supports_design) {
        designTab.style.opacity = '0.5';
        designTab.title = 'Requires VoiceDesign model';
    }
    if (!data.supports_cloning) {
        cloneTab.style.opacity = '0.5';
        cloneTab.title = 'Requires Base model';
    }

    // Auto-switch to first available tab
    if (!data.supports_custom_voice) {
        if (data.supports_design) {
            switchTab('design');
        } else if (data.supports_cloning) {
            switchTab('clone');
        }
    }
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
    document.getElementById('result').style.display = 'none';
}

function showResult(blob) {
    const url = URL.createObjectURL(blob);
    document.getElementById('audio').src = url;
    document.getElementById('download').href = url;
    document.getElementById('result').className = 'result';
    document.getElementById('result').style.display = 'block';
}

function showError(msg) {
    document.getElementById('result').className = 'result error';
    document.getElementById('result').innerHTML = '<strong>Error:</strong> ' + msg;
    document.getElementById('result').style.display = 'block';
}

function parseErrorDetail(detail) {
    // Handle FastAPI validation errors (array format)
    if (Array.isArray(detail)) {
        return detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ');
    }
    // Handle string errors
    if (typeof detail === 'string') {
        return detail;
    }
    // Handle object errors
    if (detail && typeof detail === 'object') {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return 'Generation failed';
}

async function generateSimple() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const res = await fetch('/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: document.getElementById('text').value,
                language: document.getElementById('language').value,
                speaker: document.getElementById('speaker').value,
                instruct: document.getElementById('instruct').value
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(parseErrorDetail(err.detail));
        }

        showResult(await res.blob());
    } catch (e) {
        showError(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate Speech';
    }
}

async function generateDesign() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const form = new FormData();
        form.append('text', document.getElementById('design-text').value);
        form.append('language', document.getElementById('design-language').value);
        form.append('instruct', document.getElementById('design-instruct').value);

        const res = await fetch('/tts/design', { method: 'POST', body: form });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(parseErrorDetail(err.detail));
        }

        showResult(await res.blob());
    } catch (e) {
        showError(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate with Designed Voice';
    }
}

async function generateClone() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const audioFile = document.getElementById('clone-audio').files[0];
        if (!audioFile) throw new Error('Please select a reference audio file');

        const form = new FormData();
        form.append('text', document.getElementById('clone-text').value);
        form.append('language', document.getElementById('clone-language').value);
        form.append('reference_audio', audioFile);
        form.append('reference_text', document.getElementById('clone-ref-text').value);

        const res = await fetch('/tts/clone', { method: 'POST', body: form });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(parseErrorDetail(err.detail));
        }

        showResult(await res.blob());
    } catch (e) {
        showError(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate with Cloned Voice';
    }
}

checkStatus();
</script>
</body>
</html>
"""
