"""HTML body for web UI."""


def _advanced_settings(prefix: str) -> str:
    """Generate collapsible advanced settings section for a tab."""
    return f"""
            <details class="advanced-settings">
                <summary><span class="advanced-arrow"></span> <span data-i18n="advanced.title">Advanced Settings</span>
                    <button type="button" class="param-help" onclick="event.preventDefault(); event.stopPropagation(); openAdvancedHelp()" data-i18n-title="advanced.guide" title="Parameter guide" aria-label="Parameter guide">?</button>
                </summary>
                <div class="advanced-grid">
                    <div>
                        <label for="{prefix}-temperature" data-i18n="param.temperature">Temperature</label>
                        <input type="number" id="{prefix}-temperature" value="0.9" min="0.01" max="2.0" step="0.05" data-i18n-title="param.temp_tip" title="Controls randomness. Default: 0.9">
                    </div>
                    <div>
                        <label for="{prefix}-top_k" data-i18n="param.top_k">Top-K</label>
                        <input type="number" id="{prefix}-top_k" value="50" min="1" max="200" step="1" data-i18n-title="param.topk_tip" title="Top-k sampling. Default: 50">
                    </div>
                    <div>
                        <label for="{prefix}-top_p" data-i18n="param.top_p">Top-P</label>
                        <input type="number" id="{prefix}-top_p" value="1.0" min="0.1" max="1.0" step="0.05" data-i18n-title="param.topp_tip" title="Nucleus sampling. Default: 1.0">
                    </div>
                    <div>
                        <label for="{prefix}-repetition_penalty" data-i18n="param.rep_penalty">Repetition Penalty</label>
                        <input type="number" id="{prefix}-repetition_penalty" value="1.05" min="1.0" max="2.0" step="0.05" data-i18n-title="param.rep_tip" title="Repetition penalty. Default: 1.05">
                    </div>
                    <div>
                        <label for="{prefix}-max_new_tokens" data-i18n="param.max_tokens">Max Tokens</label>
                        <input type="number" id="{prefix}-max_new_tokens" value="2048" min="256" max="4096" step="256" data-i18n-title="param.tokens_tip" title="Max codec tokens. Default: 2048">
                    </div>
                </div>
            </details>"""


INDEX_BODY = """
    <div class="title-row">
        <div>
            <h1 data-i18n="app.title">TTS Adapter</h1>
            <p class="subtitle" data-i18n="app.subtitle">Text-to-Speech Generation</p>
        </div>
        <div id="lang-switch" class="lang-switch" role="radiogroup" aria-label="Interface language">
            <button type="button" class="lang-btn lang-active" id="lang-btn-ru"
                onclick="switchUiLang('ru')">РУ</button>
            <button type="button" class="lang-btn" id="lang-btn-en"
                onclick="switchUiLang('en')">EN</button>
        </div>
    </div>

    <div id="status" class="status" data-i18n="status.checking">Checking server status...</div>

    <div class="model-selector">
        <label for="model-select" data-i18n="model.label">Model:</label>
        <select id="model-select" onchange="onModelSelect(this.value)" data-i18n-title="model.switch_title" title="Switch TTS model (reloads server)">
            <option value="" data-i18n="model.loading">Loading...</option>
        </select>
        <button type="button" class="model-help" onclick="openModelHelp()" data-i18n-title="model.guide" title="Model guide" aria-label="Model guide">?</button>
        <span id="model-features" title="Capabilities for selected model"></span>
    </div>

    <!-- Loading overlay -->
    <div id="loading-overlay" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text" data-i18n="loading.text">Switching model...</div>
        <div class="loading-hint" data-i18n="loading.hint">This can take up to 60 seconds. Please wait.</div>
    </div>

    <!-- Confirmation modal -->
    <div id="modal-overlay" class="modal-overlay">
        <div class="modal">
            <h3 data-i18n="modal.switch_title">Switch Model?</h3>
            <p id="modal-message" data-i18n="modal.switch_msg">This will reload the TTS model. Server unavailable for ~2 minutes.</p>
            <div class="modal-buttons">
                <button id="modal-cancel" class="btn-cancel" onclick="cancelSwitch()" data-i18n-title="modal.cancel_title" title="Cancel model switch" type="button" data-i18n="modal.cancel">Cancel</button>
                <button id="modal-confirm" class="btn-confirm" onclick="confirmSwitch()" data-i18n-title="modal.confirm_title" title="Confirm model switch" type="button" data-i18n="modal.confirm_switch">Switch Model</button>
            </div>
        </div>
    </div>

    <!-- Model help modal -->
    <div id="model-help-overlay" class="modal-overlay">
        <div class="modal">
            <h3 data-i18n="help.model_title">Model Guide</h3>
            <div id="model-help-list" data-i18n="help.model_loading">Loading model info...</div>
            <div class="modal-buttons">
                <button class="btn-confirm" onclick="closeModelHelp()" data-i18n-title="help.close_model" title="Close model guide" type="button" data-i18n="help.got_it">Got it</button>
            </div>
        </div>
    </div>

    <!-- Advanced settings help modal -->
    <div id="advanced-help-overlay" class="modal-overlay">
        <div class="modal">
            <h3 data-i18n="help.params_title">Generation Parameters</h3>
            <div id="advanced-help-content" class="advanced-help-content"></div>
            <div class="modal-buttons">
                <button class="btn-confirm" onclick="closeAdvancedHelp()" data-i18n-title="help.close_params" title="Close parameter guide" type="button" data-i18n="help.got_it">Got it</button>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="tabs">
            <button class="tab active" data-tab="simple" onclick="switchTab('simple')" title="Simple TTS (CustomVoice model)" data-default-title-key="tab.simple_title" type="button" data-i18n="tab.simple">Simple</button>
            <button class="tab" data-tab="design" onclick="switchTab('design')" title="Voice Design (VoiceDesign model)" data-default-title-key="tab.design_title" type="button" data-i18n="tab.design">Voice Design</button>
            <button class="tab" data-tab="clone" onclick="switchTab('clone')" title="Voice Clone (Base model)" data-default-title-key="tab.clone_title" type="button" data-i18n="tab.clone">Voice Clone</button>
        </div>

        <!-- Simple TTS Tab -->
        <div id="tab-simple" class="tab-content active">
            <label for="text" data-i18n="label.text">Text to speak</label>
            <textarea id="text" data-i18n-placeholder="ph.text" placeholder="Enter text here..." data-i18n-title="title.text" title="Required text to synthesize"></textarea>

            <div class="row">
                <div>
                    <label for="language" data-i18n="label.language">Language</label>
                    <!-- Options populated by populateLanguageDropdowns() from /health.supported_languages -->
                    <select id="language" data-i18n-title="title.language" title="Language for output speech"></select>
                </div>
                <div>
                    <label for="speaker" data-i18n="label.speaker">Speaker</label>
                    <select id="speaker" data-i18n-title="title.speaker" title="Preset speaker (CustomVoice model)">
                        <option value="Serena" data-i18n="speaker.serena">Serena (Female, warm)</option>
                        <option value="Sohee" data-i18n="speaker.sohee">Sohee (Female, emotional)</option>
                        <option value="Vivian" data-i18n="speaker.vivian">Vivian (Female, bright)</option>
                        <option value="Ono_Anna" data-i18n="speaker.ono_anna">Ono_Anna (Female, playful)</option>
                        <option value="Ryan" data-i18n="speaker.ryan">Ryan (Male, dynamic)</option>
                        <option value="Aiden" data-i18n="speaker.aiden">Aiden (Male, clear)</option>
                        <option value="Uncle_Fu" data-i18n="speaker.uncle_fu">Uncle_Fu (Male, mellow)</option>
                        <option value="Dylan" data-i18n="speaker.dylan">Dylan (Male, youthful)</option>
                        <option value="Eric" data-i18n="speaker.eric">Eric (Male, lively)</option>
                    </select>
                </div>
            </div>

            <label for="instruct" data-i18n="label.instruct">Style instruction (optional)</label>
            <input type="text" id="instruct" data-i18n-placeholder="ph.instruct" placeholder="e.g., Speak slowly and warmly" data-i18n-title="title.instruct" title="Optional style instruction (CustomVoice model)">
            <p class="hint" data-i18n="hint.instruct">Control tone, emotion, speed. Works with CustomVoice model only.</p>
""" + _advanced_settings("simple") + """

            <button onclick="generateSimple()" data-i18n-title="btn.generate_title" title="Generate speech with current settings" type="button" data-i18n="btn.generate">Generate Speech</button>
        </div>

        <!-- Voice Design Tab -->
        <div id="tab-design" class="tab-content">
            <label for="design-text" data-i18n="label.text">Text to speak</label>
            <textarea id="design-text" data-i18n-placeholder="ph.text" placeholder="Enter text here..." data-i18n-title="title.text" title="Required text to synthesize"></textarea>

            <label for="design-language" data-i18n="label.language">Language</label>
            <!-- Options populated by populateLanguageDropdowns() from /health.supported_languages -->
            <select id="design-language" data-i18n-title="title.language" title="Language for output speech"></select>

            <label for="design-instruct" data-i18n="label.design_instruct">Voice description (required)</label>
            <textarea id="design-instruct" data-i18n-placeholder="ph.design_instruct" placeholder="e.g., Adult female voice, contralto range, warm and confident, expressive" data-i18n-title="title.design_instruct" title="Required voice description (VoiceDesign model)"></textarea>
            <p class="hint" data-i18n="hint.design">Describe the voice: gender, age, pitch, timbre, emotion, pace. We trim trailing silence.</p>
""" + _advanced_settings("design") + """

            <button onclick="generateDesign()" data-i18n-title="btn.design_title" title="Generate speech with designed voice" type="button" data-i18n="btn.generate_design">Generate with Designed Voice</button>
        </div>

        <!-- Voice Clone Tab -->
        <div id="tab-clone" class="tab-content">
            <label for="clone-text" data-i18n="label.text">Text to speak</label>
            <textarea id="clone-text" data-i18n-placeholder="ph.text" placeholder="Enter text here..." data-i18n-title="title.text" title="Required text to synthesize"></textarea>

            <label for="clone-language" data-i18n="label.language">Language</label>
            <!-- Options populated by populateLanguageDropdowns() from /health.supported_languages -->
            <select id="clone-language" data-i18n-title="title.language" title="Language for output speech"></select>

            <label for="clone-audio" data-i18n="label.ref_audio">Reference audio (WAV, 3-10 sec)</label>
            <input type="file" id="clone-audio" accept=".wav,audio/wav" data-i18n-title="title.ref_audio" title="Required WAV file, 3-10 seconds">

            <label for="clone-ref-text" data-i18n="label.ref_text">Reference transcript (optional, improves quality)</label>
            <input type="text" id="clone-ref-text" data-i18n-placeholder="ph.ref_text" placeholder="What is said in the reference audio" data-i18n-title="title.ref_text" title="Optional transcript of the reference audio">

            <div id="emotion-controls" class="emotion-controls" hidden aria-hidden="true">
                <label for="clone-emotion-mode" data-i18n="label.emotion_mode">Emotion control</label>
                <select id="clone-emotion-mode" onchange="onEmotionModeChange()" data-i18n-title="title.emotion_mode" title="Optional emotion input for models that support emotional cloning">
                    <option value="none" data-i18n="emotion.none">None</option>
                    <option value="audio" data-i18n="emotion.audio">Emotion audio</option>
                    <option value="text" data-i18n="emotion.text">Emotion text</option>
                    <option value="vector" data-i18n="emotion.vector">Emotion vector</option>
                </select>

                <div id="clone-emotion-audio-panel" class="emotion-mode-panel" data-emotion-mode="audio" hidden>
                    <label for="clone-emotion-audio" data-i18n="label.emotion_audio">Emotion reference audio (WAV)</label>
                    <input type="file" id="clone-emotion-audio" accept=".wav,audio/wav" data-i18n-title="title.emotion_audio" title="Optional WAV file for emotion transfer">
                </div>

                <div id="clone-emotion-text-panel" class="emotion-mode-panel" data-emotion-mode="text" hidden>
                    <label for="clone-emotion-text" data-i18n="label.emotion_text">Emotion text</label>
                    <input type="text" id="clone-emotion-text" data-i18n-placeholder="ph.emotion_text" placeholder="e.g., excited and warm" data-i18n-title="title.emotion_text" title="Free-form emotion description">
                </div>

                <div id="clone-emotion-vector-panel" class="emotion-mode-panel" data-emotion-mode="vector" hidden>
                    <label data-i18n="label.emotion_vector">Emotion vector</label>
                    <div class="emotion-vector-grid">
                        <label><span data-i18n="emotion.happy">Happy</span><input type="number" id="clone-emotion-happy" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.angry">Angry</span><input type="number" id="clone-emotion-angry" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.sad">Sad</span><input type="number" id="clone-emotion-sad" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.afraid">Afraid</span><input type="number" id="clone-emotion-afraid" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.disgusted">Disgusted</span><input type="number" id="clone-emotion-disgusted" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.melancholic">Melancholic</span><input type="number" id="clone-emotion-melancholic" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.surprised">Surprised</span><input type="number" id="clone-emotion-surprised" value="0" min="0" max="1" step="0.1"></label>
                        <label><span data-i18n="emotion.calm">Calm</span><input type="number" id="clone-emotion-calm" value="0" min="0" max="1" step="0.1"></label>
                    </div>
                </div>

                <div id="clone-emotion-alpha-wrap" class="emotion-alpha-wrap emotion-disabled">
                    <label for="clone-emotion-alpha">
                        <span data-i18n="label.emotion_alpha">Emotion strength</span>
                        <span id="clone-emotion-alpha-value">0.60</span>
                    </label>
                    <input type="range" id="clone-emotion-alpha" value="0.6" min="0" max="1" step="0.05" oninput="updateEmotionAlphaValue()" data-i18n-title="title.emotion_alpha" title="Emotion blend strength">
                </div>
            </div>
""" + _advanced_settings("clone") + """

            <button onclick="generateClone()" data-i18n-title="btn.clone_title" title="Generate speech with cloned voice" type="button" data-i18n="btn.generate_clone">Generate with Cloned Voice</button>
        </div>

        <div id="gen-progress" class="progress" aria-live="polite">
            <div id="gen-progress-label" class="progress-label" data-i18n="progress.generating">Generating audio...</div>
            <div class="progress-bar"><div class="progress-bar-inner"></div></div>
            <div id="gen-progress-hint" class="progress-hint" data-i18n="progress.first_slow">First request after model load can be slower.</div>
        </div>

        <div id="result" class="result">
            <strong data-i18n="misc.result">Result:</strong>
            <audio id="audio" controls></audio>
            <br>
            <a id="download" class="download-btn" download="tts_output.wav" data-i18n-title="misc.download_title" title="Download generated WAV" data-i18n="misc.download">Download WAV</a>
        </div>
    </div>

    <p style="text-align: center; color: #999; font-size: 12px;">
        <a href="/docs" style="color: #666;" data-i18n="footer.api_docs">API Documentation</a> |
        <a href="/health" style="color: #666;" data-i18n="footer.health">Health Check</a>
    </p>
"""
