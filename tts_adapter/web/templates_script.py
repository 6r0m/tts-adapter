"""JavaScript for web UI."""

INDEX_SCRIPT = """
let serverInfo = {};
let availableModels = [];
let pendingModelId = null;
let currentTab = 'simple';
let isSwitchingModel = false;
const HEALTH_POLL_MS = 3000;
const EMOTION_VECTOR_KEYS = ['happy', 'angry', 'sad', 'afraid', 'disgusted', 'melancholic', 'surprised', 'calm'];

// IDs of all language <select>s populated from /health.supported_languages.
// Site is the source of truth: dropdown contents always match what the
// active engine actually accepts.
const LANGUAGE_SELECT_IDS = ['language', 'design-language', 'clone-language'];

// Preferred default - matches TTS_DEFAULT_LANGUAGE in .env.example. The
// dropdown auto-selects this when the active engine supports it; otherwise
// falls back to the first supported language and shows an inline hint.
const PREFERRED_LANGUAGE = 'Russian';

function getModelEngine(modelOrId) {
    const id = typeof modelOrId === 'string' ? modelOrId : modelOrId?.id;
    if (!id) return 'unknown';
    if (id.startsWith('IndexTeam/') || id.includes('IndexTTS')) return 'indextts2';
    if (id.startsWith('openbmb/') || id.includes('VoxCPM')) return 'voxcpm2';
    if (id.startsWith('Qwen/')) return 'qwen3';
    return 'unknown';
}

function cleanModelName(name) {
    return (name || '')
        .replace(' (Clone, Low VRAM)', ' Low VRAM')
        .replace(' (Clone)', '');
}

function getModelLabel(modelOrId) {
    const model = typeof modelOrId === 'string'
        ? availableModels.find(m => m.id === modelOrId)
        : modelOrId;
    const id = typeof modelOrId === 'string' ? modelOrId : modelOrId?.id;
    const label = cleanModelName(model?.name || id || 'Unknown');
    return `[${getModelEngine(model || id)}] ${label}`;
}

function getModelName(modelId) {
    if (!modelId) return 'Unknown';
    const model = availableModels.find(m => m.id === modelId);
    return model ? getModelLabel(model) : modelId;
}

function getCapabilitiesList(data) {
    const caps = [];
    if (data?.supports_custom_voice) caps.push(t('cap.simple'));
    if (data?.supports_design) caps.push(t('cap.design'));
    if (data?.supports_cloning) caps.push(t('cap.clone'));
    if (data?.supports_emotional_cloning) caps.push(t('cap.emotion'));
    return caps;
}

function updateStatusText() {
    const status = document.getElementById('status');
    const modelName = getModelName(serverInfo.model);
    const caps = getCapabilitiesList(serverInfo);
    const capText = caps.length ? caps.join(', ') : '—';
    status.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = t('status.ok');
    status.appendChild(strong);
    status.appendChild(document.createTextNode(
        ` | ${t('status.engine')}: ${serverInfo.engine} | ${t('status.model')}: ${modelName} | ${t('status.caps')}: ${capText}`
    ));
    status.title = `Model ID: ${serverInfo.model || '?'} | Device: ${serverInfo.device || '?'}`;
    document.title = `${t('app.title')} — ${modelName} (${capText})`;
}

// Pick the language to auto-select when populating dropdowns.
// Priority:
//   1. Keep user's previous selection if still supported AND engine didn't change.
//   2. Else PREFERRED_LANGUAGE ('Russian') if supported.
//   3. Else 'English' if supported (sensible Western fallback for non-Russian users).
//   4. Else the first supported language (last resort - keeps the dropdown valid).
function chooseLanguage(supportedLanguages, previousValue, engineChanged) {
    if (previousValue && supportedLanguages.includes(previousValue) && !engineChanged) {
        return previousValue;
    }
    if (supportedLanguages.includes(PREFERRED_LANGUAGE)) {
        return PREFERRED_LANGUAGE;
    }
    if (supportedLanguages.includes('English')) {
        return 'English';
    }
    return supportedLanguages[0];
}

// SOT for language options is the server. Each /health poll re-syncs all
// three language <select>s with engine.supported_languages.
function populateLanguageDropdowns(supportedLanguages, previousEngine) {
    if (!supportedLanguages || !supportedLanguages.length) return;

    const engineChanged = previousEngine && previousEngine !== serverInfo.engine;

    LANGUAGE_SELECT_IDS.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;

        const previousValue = select.value;
        select.replaceChildren();
        supportedLanguages.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            select.appendChild(opt);
        });

        select.value = chooseLanguage(supportedLanguages, previousValue, engineChanged);
    });

    // Inline hint when the preferred language isn't available on the
    // active engine. Discoverable, not silent.
    updateLanguageFallbackHint(supportedLanguages);
}

function updateLanguageFallbackHint(supportedLanguages) {
    let banner = document.getElementById('language-fallback-hint');
    const showHint = !supportedLanguages.includes(PREFERRED_LANGUAGE);

    if (!showHint) {
        if (banner) banner.remove();
        return;
    }

    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'language-fallback-hint';
        banner.className = 'status warning';
        const status = document.getElementById('status');
        if (status && status.parentNode) {
            status.parentNode.insertBefore(banner, status.nextSibling);
        }
    }
    // Read the actual currently-selected language from the main dropdown so
    // the hint reflects whatever the user is about to send (not just the
    // first supported language). Falls back to chooseLanguage() if the
    // dropdown isn't populated yet.
    const select = document.getElementById('language');
    const currentlySelected = (select && select.value)
        || chooseLanguage(supportedLanguages, '', false);
    banner.textContent = t('lang.unsupported_hint')
        .replace('{engine}', serverInfo.engine || '?')
        .replace('{lang}', currentlySelected)
        .replace('{preferred}', PREFERRED_LANGUAGE);
}

async function checkStatus(options = {}) {
    if (isSwitchingModel && !options.refreshModels) return;

    const status = document.getElementById('status');
    try {
        const previousModel = serverInfo.model;
        const previousEngine = serverInfo.engine;
        const res = await fetch('/health');
        const data = await res.json();
        serverInfo = data;
        status.className = 'status ok';
        updateStatusText();
        updateTabAvailability(data);
        populateLanguageDropdowns(data.supported_languages || [], previousEngine);

        const shouldRefreshModels = options.refreshModels
            || availableModels.length === 0
            || previousModel !== data.model
            || previousEngine !== data.engine;
        if (shouldRefreshModels) {
            await loadModels();
        } else {
            syncModelSelect(data.model);
            updateModelHelp();
        }
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
            opt.textContent = getModelLabel(m);
            if (m.id === data.current) opt.selected = true;
            select.appendChild(opt);
        });
        select.disabled = isSwitchingModel;
        updateModelFeatures(serverInfo.model || data.current);
        updateStatusText();
        updateModelHelp();
    } catch (e) {
        console.error('Failed to load models:', e);
        updateModelHelp();
    }
}

function syncModelSelect(modelId) {
    const select = document.getElementById('model-select');
    if (!select) return;
    if ([...select.options].some(opt => opt.value === modelId)) {
        select.value = modelId;
    }
    select.disabled = isSwitchingModel;
    updateModelFeatures(modelId);
}

function updateModelFeatures(modelId) {
    const model = availableModels.find(m => m.id === modelId);
    const features = document.getElementById('model-features');
    if (model) {
        const caps = [];
        if (model.supports_custom_voice) caps.push(t('cap.simple'));
        if (model.supports_design) caps.push(t('cap.design'));
        if (model.supports_cloning) caps.push(t('cap.clone'));
        if (model.supports_emotional_cloning) caps.push(t('cap.emotion'));
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
        name.textContent = getModelLabel(model);
        li.appendChild(name);

        const caps = [];
        if (model.supports_custom_voice) caps.push(t('cap.simple_full'));
        if (model.supports_design) caps.push(t('cap.design_full'));
        if (model.supports_cloning) caps.push(t('cap.clone_full'));
        if (model.supports_emotional_cloning) caps.push(t('cap.emotion_full'));
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

function isCrossEngineSwitch(modelId) {
    const targetEngine = getModelEngine(modelId);
    return !!serverInfo.engine && targetEngine !== 'unknown' && targetEngine !== serverInfo.engine;
}

function onModelSelect(modelId) {
    if (!modelId || modelId === serverInfo.model) return;
    pendingModelId = modelId;
    updateModelFeatures(modelId);
    const model = availableModels.find(m => m.id === modelId);
    const warning = isCrossEngineSwitch(modelId) ? t('modal.switch_warn_engine') : t('modal.switch_warn');
    document.getElementById('modal-message').textContent =
        `${t('modal.switch_to')} ${model ? getModelLabel(model) : modelId}? ${warning}`;
    document.getElementById('modal-overlay').classList.add('active');
}

function cancelSwitch() {
    if (isSwitchingModel) return;
    document.getElementById('modal-overlay').classList.remove('active');
    document.getElementById('model-select').value = serverInfo.model;
    updateModelFeatures(serverInfo.model);
    pendingModelId = null;
}

function setModelSwitchBusy(busy) {
    const confirm = document.getElementById('modal-confirm');
    const cancel = document.getElementById('modal-cancel');
    const select = document.getElementById('model-select');
    if (select) select.disabled = busy;
    if (cancel) cancel.disabled = busy;
    if (confirm) {
        confirm.disabled = busy;
        confirm.classList.toggle('btn-busy', busy);
        confirm.textContent = busy ? t('btn.switching') : t('modal.confirm_switch');
    }
}

async function confirmSwitch() {
    if (!pendingModelId || isSwitchingModel) return;
    isSwitchingModel = true;
    setModelSwitchBusy(true);

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
        serverInfo.supports_emotional_cloning = data.supports_emotional_cloning;
        serverInfo.emotion_modes = data.emotion_modes || [];
        serverInfo.supports_emotion_strength = !!data.supports_emotion_strength;
        serverInfo.supports_cyrillic_text = data.supports_cyrillic_text !== false;

        await checkStatus({ refreshModels: true });
        document.getElementById('modal-overlay').classList.remove('active');

    } catch (e) {
        document.getElementById('modal-overlay').classList.remove('active');
        alert(`${t('error.switch_failed')}: ${e.message}`);
        document.getElementById('model-select').value = serverInfo.model;
        updateModelFeatures(serverInfo.model);
    } finally {
        isSwitchingModel = false;
        setModelSwitchBusy(false);
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
    updateEmotionControls(data);

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
    const titleKey = tab.dataset.defaultTitleKey || '';
    tab.classList.toggle('tab-disabled', !supported);
    tab.setAttribute('aria-disabled', supported ? 'false' : 'true');
    tab.dataset.supported = supported ? 'true' : 'false';
    tab.title = supported ? t(titleKey) : disabledTitle;
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

function updateEmotionControls(data = serverInfo) {
    const controls = document.getElementById('emotion-controls');
    if (!controls) return;
    const supported = !!data?.supports_emotional_cloning;
    controls.hidden = !supported;
    controls.setAttribute('aria-hidden', supported ? 'false' : 'true');
    if (!supported) {
        const mode = document.getElementById('clone-emotion-mode');
        if (mode) mode.value = 'none';
    }
    // Filter the per-mode <option>s based on which modes the engine actually
    // supports. VoxCPM2 (text-only) hides "audio" and "vector" so the user
    // can't pick a mode the API would reject with 400.
    filterEmotionModeOptions(data?.emotion_modes || []);
    updateEmotionModePanels();
}

function filterEmotionModeOptions(supportedModes) {
    const select = document.getElementById('clone-emotion-mode');
    if (!select) return;
    const allowed = new Set(supportedModes);
    let visibleCount = 0;
    let firstVisible = null;
    [...select.options].forEach(opt => {
        if (opt.value === 'none') {
            opt.hidden = false;
            return;
        }
        const supported = allowed.has(opt.value);
        opt.hidden = !supported;
        if (supported) {
            visibleCount += 1;
            if (firstVisible === null) firstVisible = opt.value;
        }
    });
    // If the currently-selected mode is no longer supported, fall back to
    // 'none'. This avoids leaving the dropdown in a state the engine rejects.
    if (select.value !== 'none' && !allowed.has(select.value)) {
        select.value = visibleCount > 0 ? firstVisible : 'none';
    }
}

function onEmotionModeChange() {
    updateEmotionModePanels();
}

function updateEmotionModePanels() {
    const mode = document.getElementById('clone-emotion-mode')?.value || 'none';
    const controls = document.getElementById('emotion-controls');
    const active = !controls?.hidden && mode !== 'none';
    document.querySelectorAll('.emotion-mode-panel').forEach(panel => {
        panel.hidden = panel.dataset.emotionMode !== mode;
    });
    // emotion_alpha is meaningful only on engines that expose intensity
    // (supports_emotion_strength). Otherwise hide the slider entirely so
    // the user doesn't think it does something.
    const alphaSupported = !!serverInfo?.supports_emotion_strength;
    const alpha = document.getElementById('clone-emotion-alpha');
    const alphaWrap = document.getElementById('clone-emotion-alpha-wrap');
    if (alphaWrap) {
        alphaWrap.hidden = !alphaSupported;
    }
    if (alpha) alpha.disabled = !(active && alphaSupported);
    if (alphaWrap) alphaWrap.classList.toggle('emotion-disabled', !(active && alphaSupported));
    updateEmotionAlphaValue();
}

function updateEmotionAlphaValue() {
    const alpha = document.getElementById('clone-emotion-alpha');
    const value = document.getElementById('clone-emotion-alpha-value');
    if (!alpha || !value) return;
    const num = Number.parseFloat(alpha.value);
    value.textContent = Number.isFinite(num) ? num.toFixed(2) : '0.00';
}

function getEmotionVectorValue() {
    return EMOTION_VECTOR_KEYS.map(key => {
        const field = document.getElementById(`clone-emotion-${key}`);
        const value = Number.parseFloat(field?.value || '0');
        return Number.isFinite(value) ? value : 0;
    }).join(',');
}

function appendEmotionFormData(form) {
    if (!serverInfo.supports_emotional_cloning) return;
    const mode = document.getElementById('clone-emotion-mode')?.value || 'none';
    if (mode === 'none') return;

    // Only send emotion_alpha if the active engine actually exposes intensity.
    // Otherwise the API would 400 (it rejects non-default emotion_alpha when
    // supports_emotion_strength=False). Default 1.0 means "no override".
    if (serverInfo.supports_emotion_strength) {
        form.append('emotion_alpha', document.getElementById('clone-emotion-alpha')?.value || '1.0');
    }
    if (mode === 'audio') {
        const audioFile = document.getElementById('clone-emotion-audio')?.files[0];
        if (!audioFile) throw new Error(t('error.no_emotion_audio'));
        form.append('emotion_audio', audioFile);
    } else if (mode === 'text') {
        const emotionText = document.getElementById('clone-emotion-text')?.value.trim() || '';
        if (!emotionText) throw new Error(t('error.no_emotion_text'));
        form.append('emotion_text', emotionText);
    } else if (mode === 'vector') {
        form.append('emotion_vector', getEmotionVectorValue());
    }
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
    result.style.display = 'block';
    result.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = `${t('error.prefix')}:`;
    result.appendChild(strong);
    result.appendChild(document.createTextNode(` ${msg}`));
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
        appendEmotionFormData(form);

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

function rerenderDynamicTexts() {
    if (serverInfo?.model) {
        updateStatusText();
        updateModelFeatures(document.getElementById('model-select')?.value || serverInfo.model);
        updateTabAvailability(serverInfo);
    }
    setModelSwitchBusy(isSwitchingModel);
    updateEmotionModePanels();
    if (document.getElementById('model-help-overlay')?.classList.contains('active')) {
        updateModelHelp();
    }
}

// Boot: apply translations first, then load status
applyTranslations();
updateLangToggle();
checkStatus({ refreshModels: true });
setInterval(() => checkStatus(), HEALTH_POLL_MS);
"""
