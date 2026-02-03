"""JavaScript for web UI."""

INDEX_SCRIPT = """
let serverInfo = {};
let availableModels = [];
let pendingModelId = null;
let currentTab = 'simple';

function getModelName(modelId) {
    if (!modelId) return 'Unknown';
    const model = availableModels.find(m => m.id === modelId);
    return model ? model.name : modelId;
}

function getCapabilitiesList(data) {
    const caps = [];
    if (data?.supports_custom_voice) caps.push('Simple');
    if (data?.supports_design) caps.push('Design');
    if (data?.supports_cloning) caps.push('Clone');
    return caps;
}

function updateStatusText() {
    const status = document.getElementById('status');
    const modelName = getModelName(serverInfo.model);
    const caps = getCapabilitiesList(serverInfo);
    const capText = caps.length ? caps.join(', ') : 'None';
    status.innerHTML = `<strong>Server OK</strong> | Engine: ${serverInfo.engine} | ` +
        `Model: ${modelName} | Caps: ${capText}`;
    status.title = `Model ID: ${serverInfo.model || 'Unknown'} | Device: ${serverInfo.device || 'Unknown'}`;
    document.title = `TTS Adapter - ${modelName} (${capText})`;
}

async function checkStatus() {
    const status = document.getElementById('status');
    try {
        const res = await fetch('/health');
        const data = await res.json();
        serverInfo = data;
        status.className = 'status ok';
        updateStatusText();
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
        serverInfo.model = data.current || serverInfo.model;
        const select = document.getElementById('model-select');
        select.innerHTML = '';
        data.available.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.name;
            if (m.id === data.current) opt.selected = true;
            select.appendChild(opt);
        });
        updateModelFeatures(serverInfo.model || data.current);
        updateStatusText();
        updateModelHelp();
    } catch (e) {
        console.error('Failed to load models:', e);
        updateModelHelp();
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
        features.title = caps.length ? `Capabilities: ${caps.join(', ')}` : 'Capabilities unavailable';
    } else {
        features.textContent = '';
        features.title = 'Capabilities unavailable';
    }
}

function updateModelHelp() {
    const container = document.getElementById('model-help-list');
    if (!container) return;
    container.innerHTML = '';
    if (!availableModels.length) {
        container.textContent = 'Model info unavailable.';
        return;
    }

    const intro = document.createElement('p');
    intro.textContent = `Current model: ${getModelName(serverInfo.model)}. ` +
        'Pick a model based on the feature you need:';
    container.appendChild(intro);

    const list = document.createElement('ul');
    list.className = 'model-help-items';

    availableModels.forEach(model => {
        const li = document.createElement('li');
        const name = document.createElement('strong');
        name.textContent = model.name;
        li.appendChild(name);

        const caps = [];
        if (model.supports_custom_voice) caps.push('Simple (style instruction)');
        if (model.supports_design) caps.push('Voice Design');
        if (model.supports_cloning) caps.push('Voice Clone');
        const capText = caps.length ? caps.join(', ') : 'Unknown';
        const lowVram = model.id && model.id.includes('0.6B') ? ' Low VRAM option.' : '';
        li.appendChild(document.createTextNode(` - Use for: ${capText}.${lowVram}`));

        list.appendChild(li);
    });

    container.appendChild(list);

    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'Switching models reloads the server and takes about 1-2 minutes.';
    container.appendChild(hint);
}

function openModelHelp() {
    updateModelHelp();
    document.getElementById('model-help-overlay').classList.add('active');
}

function closeModelHelp() {
    document.getElementById('model-help-overlay').classList.remove('active');
}

function getTabButton(tab) {
    return document.querySelector(`.tab[data-tab="${tab}"]`);
}

function isTabSupported(tab) {
    if (!serverInfo || Object.keys(serverInfo).length === 0) return true;
    if (tab === 'simple') return !!serverInfo.supports_custom_voice;
    if (tab === 'design') return !!serverInfo.supports_design;
    if (tab === 'clone') return !!serverInfo.supports_cloning;
    return false;
}

function onModelSelect(modelId) {
    if (modelId === serverInfo.model) return;
    pendingModelId = modelId;
    updateModelFeatures(modelId);
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
    updateModelFeatures(serverInfo.model);
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
        updateModelFeatures(serverInfo.model);
    } finally {
        document.getElementById('loading-overlay').classList.remove('active');
        pendingModelId = null;
    }
}

function updateTabAvailability(data) {
    const simpleTab = getTabButton('simple');
    const designTab = getTabButton('design');
    const cloneTab = getTabButton('clone');

    setTabState(simpleTab, data.supports_custom_voice, 'Requires CustomVoice model');
    setTabState(designTab, data.supports_design, 'Requires VoiceDesign model');
    setTabState(cloneTab, data.supports_cloning, 'Requires Base model');

    const availableTabs = [];
    if (data.supports_custom_voice) availableTabs.push('simple');
    if (data.supports_design) availableTabs.push('design');
    if (data.supports_cloning) availableTabs.push('clone');

    if (!availableTabs.includes(currentTab) && availableTabs.length) {
        switchTab(availableTabs[0]);
    }
}

function setTabState(tab, supported, disabledTitle) {
    if (!tab) return;
    const defaultTitle = tab.dataset.defaultTitle || '';
    tab.classList.toggle('tab-disabled', !supported);
    tab.setAttribute('aria-disabled', supported ? 'false' : 'true');
    tab.dataset.supported = supported ? 'true' : 'false';
    tab.title = supported ? defaultTitle : disabledTitle;
}

function switchTab(tab) {
    if (!isTabSupported(tab)) return;
    const tabButton = getTabButton(tab);
    if (!tabButton) return;
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    tabButton.classList.add('active');
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
"""
