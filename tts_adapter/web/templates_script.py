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
    if (data?.supports_custom_voice) caps.push(t('cap.simple'));
    if (data?.supports_design) caps.push(t('cap.design'));
    if (data?.supports_cloning) caps.push(t('cap.clone'));
    return caps;
}

function updateStatusText() {
    const status = document.getElementById('status');
    const modelName = getModelName(serverInfo.model);
    const caps = getCapabilitiesList(serverInfo);
    const capText = caps.length ? caps.join(', ') : 'None';
    status.innerHTML = `<strong>${t('status.ok')}</strong> | ${t('status.engine')}: ${serverInfo.engine} | ` +
        `${t('status.model')}: ${modelName} | ${t('status.caps')}: ${capText}`;
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
        status.textContent = t('status.error');
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
        if (model.supports_custom_voice) caps.push(t('cap.simple'));
        if (model.supports_design) caps.push(t('cap.design'));
        if (model.supports_cloning) caps.push(t('cap.clone'));
        if (caps.length === 1) {
            features.textContent = `${t('cap.mode')}: ${caps[0]}`;
        } else if (caps.length > 1) {
            features.textContent = `${t('cap.modes')}: ${caps.join(', ')}`;
        } else {
            features.textContent = '';
        }
        features.title = caps.length ? `${t('cap.caps')}: ${caps.join(', ')}` : t('cap.unavailable');
    } else {
        features.textContent = '';
        features.title = t('cap.unavailable');
    }
}

function updateModelHelp() {
    const container = document.getElementById('model-help-list');
    if (!container) return;
    container.innerHTML = '';
    if (!availableModels.length) {
        container.textContent = t('error.model_info');
        return;
    }

    const intro = document.createElement('p');
    intro.textContent = `${t('help.current_model')}: ${getModelName(serverInfo.model)}. ${t('help.pick_model')}`;
    container.appendChild(intro);

    const list = document.createElement('ul');
    list.className = 'model-help-items';

    availableModels.forEach(model => {
        const li = document.createElement('li');
        const name = document.createElement('strong');
        name.textContent = model.name;
        li.appendChild(name);

        const caps = [];
        if (model.supports_custom_voice) caps.push(t('cap.simple_full'));
        if (model.supports_design) caps.push(t('cap.design_full'));
        if (model.supports_cloning) caps.push(t('cap.clone_full'));
        const capText = caps.length ? caps.join(', ') : 'Unknown';
        const lowVram = model.id && model.id.includes('0.6B') ? ` ${t('help.low_vram')}` : '';
        li.appendChild(document.createTextNode(` - ${t('help.use_for')} ${capText}.${lowVram}`));

        list.appendChild(li);
    });

    container.appendChild(list);

    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = t('help.switch_hint');
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
    document.getElementById('modal-message').textContent =
        `${t('modal.switch_to')} ${model?.name || modelId}? ${t('modal.switch_warn')}`;
    document.getElementById('modal-overlay').classList.add('active');
}

function cancelSwitch() {
    document.getElementById('modal-overlay').classList.remove('active');
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
            throw new Error(err.detail || t('error.switch_failed'));
        }

        const data = await res.json();
        serverInfo.model = data.model;
        serverInfo.supports_cloning = data.supports_cloning;
        serverInfo.supports_design = data.supports_design;
        serverInfo.supports_custom_voice = data.supports_custom_voice;

        await checkStatus();

    } catch (e) {
        alert(`${t('error.switch_failed')}: ${e.message}`);
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

    setTabState(simpleTab, data.supports_custom_voice, t('tab.requires_customvoice'));
    setTabState(designTab, data.supports_design, t('tab.requires_design'));
    setTabState(cloneTab, data.supports_cloning, t('tab.requires_base'));
    setTabVisibility(simpleTab, data.supports_custom_voice);
    setTabVisibility(designTab, data.supports_design);
    setTabVisibility(cloneTab, data.supports_cloning);

    const availableTabs = [];
    if (data.supports_custom_voice) availableTabs.push('simple');
    if (data.supports_design) availableTabs.push('design');
    if (data.supports_cloning) availableTabs.push('clone');

    const tabsContainer = document.querySelector('.tabs');
    if (tabsContainer) {
        tabsContainer.style.display = availableTabs.length > 1 ? 'flex' : 'none';
    }

    if (!availableTabs.includes(currentTab) && availableTabs.length) {
        switchTab(availableTabs[0]);
    }
}

function setTabState(tab, supported, disabledTitle) {
    if (!tab) return;
    const defaultTitleKey = tab.dataset.defaultTitle || '';
    tab.classList.toggle('tab-disabled', !supported);
    tab.setAttribute('aria-disabled', supported ? 'false' : 'true');
    tab.dataset.supported = supported ? 'true' : 'false';
    tab.title = supported ? t(defaultTitleKey) : disabledTitle;
}

function setTabVisibility(tab, supported) {
    if (!tab) return;
    tab.classList.toggle('tab-hidden', !supported);
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
    const result = document.getElementById('result');
    if (!document.getElementById('audio')) {
        result.innerHTML = `<strong>${t('misc.result')}</strong>` +
            '<audio id="audio" controls></audio><br>' +
            `<a id="download" class="download-btn" download="tts_output.wav" title="${t('misc.download_title')}">${t('misc.download')}</a>`;
    }
    document.getElementById('audio').src = url;
    document.getElementById('download').href = url;
    result.className = 'result';
    result.style.display = 'block';
}

function showError(msg) {
    const result = document.getElementById('result');
    result.className = 'result error';
    result.innerHTML = `<strong>${t('error.prefix')}:</strong> ` + msg;
    result.style.display = 'block';
}

function setProgressVisible(visible, labelText, hintText) {
    const progress = document.getElementById('gen-progress');
    if (!progress) return;
    progress.classList.toggle('active', visible);
    if (labelText) {
        document.getElementById('gen-progress-label').textContent = labelText;
    }
    if (hintText) {
        document.getElementById('gen-progress-hint').textContent = hintText;
    }
}

function parseErrorDetail(detail) {
    if (Array.isArray(detail)) {
        return detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ');
    }
    if (typeof detail === 'string') {
        return detail;
    }
    if (detail && typeof detail === 'object') {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return t('error.generation_failed');
}

async function generateSimple() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = t('btn.generating');
    setProgressVisible(true, t('progress.generating'), t('progress.first_slow'));

    try {
        const res = await fetch('/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: document.getElementById('text').value,
                language: document.getElementById('language').value,
                speaker: document.getElementById('speaker').value,
                instruct: document.getElementById('instruct').value,
                generation: getAdvancedSettings('simple')
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
        btn.textContent = t('btn.generate');
        setProgressVisible(false);
    }
}

async function generateDesign() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = t('btn.generating');
    setProgressVisible(true, t('progress.designing'), t('progress.first_slow'));

    try {
        const form = new FormData();
        form.append('text', document.getElementById('design-text').value);
        form.append('language', document.getElementById('design-language').value);
        form.append('instruct', document.getElementById('design-instruct').value);
        const designSettings = getAdvancedSettings('design');
        Object.entries(designSettings).forEach(([k, v]) => form.append(k, v));

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
        btn.textContent = t('btn.generate_design');
        setProgressVisible(false);
    }
}

async function generateClone() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = t('btn.generating');
    setProgressVisible(true, t('progress.cloning'), t('progress.first_slow'));

    try {
        const audioFile = document.getElementById('clone-audio').files[0];
        if (!audioFile) throw new Error(t('error.no_ref_audio'));

        const form = new FormData();
        form.append('text', document.getElementById('clone-text').value);
        form.append('language', document.getElementById('clone-language').value);
        form.append('reference_audio', audioFile);
        form.append('reference_text', document.getElementById('clone-ref-text').value);
        const cloneSettings = getAdvancedSettings('clone');
        Object.entries(cloneSettings).forEach(([k, v]) => form.append(k, v));

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
        btn.textContent = t('btn.generate_clone');
        setProgressVisible(false);
    }
}

function getAdvancedSettings(prefix) {
    const fields = {
        temperature: 'float',
        top_k: 'int',
        top_p: 'float',
        repetition_penalty: 'float',
        max_new_tokens: 'int',
    };
    const out = {};
    for (const [key, type] of Object.entries(fields)) {
        const val = document.getElementById(prefix + '-' + key).value;
        if (val === '') continue;
        const num = type === 'int' ? parseInt(val, 10) : parseFloat(val);
        if (Number.isFinite(num)) out[key] = num;
    }
    return out;
}

function openAdvancedHelp() {
    const container = document.getElementById('advanced-help-content');
    container.innerHTML = '';
    const intro = document.createElement('p');
    intro.textContent = t('help.params_intro');
    container.appendChild(intro);

    const ul = document.createElement('ul');
    ul.className = 'param-help-list';
    const params = [
        ['param.temperature', '0.9', 'help.temp_desc'],
        ['param.top_k', '50', 'help.topk_desc'],
        ['param.top_p', '1.0', 'help.topp_desc'],
        ['param.rep_penalty', '1.05', 'help.rep_desc'],
        ['param.max_tokens', '2048', 'help.tokens_desc'],
    ];
    params.forEach(([nameKey, def, descKey]) => {
        const li = document.createElement('li');
        const strong = document.createElement('strong');
        strong.textContent = t(nameKey);
        li.appendChild(strong);
        li.appendChild(document.createTextNode(` (${def}) — ${t(descKey)}`));
        ul.appendChild(li);
    });
    container.appendChild(ul);

    document.getElementById('advanced-help-overlay').classList.add('active');
}

function closeAdvancedHelp() {
    document.getElementById('advanced-help-overlay').classList.remove('active');
}

// Boot: apply translations first, then load status
applyTranslations();
updateLangToggle();
checkStatus();
"""
