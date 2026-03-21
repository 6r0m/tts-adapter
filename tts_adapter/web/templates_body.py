"""HTML body for web UI."""


def _advanced_settings(prefix: str) -> str:
    """Generate collapsible advanced settings section for a tab."""
    return f"""
            <details class="advanced-settings">
                <summary>Advanced Settings
                    <button type="button" class="param-help" onclick="openAdvancedHelp()" title="Parameter guide" aria-label="Parameter guide">?</button>
                </summary>
                <div class="advanced-grid">
                    <div>
                        <label for="{prefix}-temperature">Temperature</label>
                        <input type="number" id="{prefix}-temperature" value="0.9" min="0.01" max="2.0" step="0.05" title="Sampling temperature (default: 0.9)">
                    </div>
                    <div>
                        <label for="{prefix}-top_k">Top-K</label>
                        <input type="number" id="{prefix}-top_k" value="50" min="1" max="200" step="1" title="Top-k sampling (default: 50)">
                    </div>
                    <div>
                        <label for="{prefix}-top_p">Top-P</label>
                        <input type="number" id="{prefix}-top_p" value="1.0" min="0.1" max="1.0" step="0.05" title="Nucleus sampling (default: 1.0)">
                    </div>
                    <div>
                        <label for="{prefix}-repetition_penalty">Repetition Penalty</label>
                        <input type="number" id="{prefix}-repetition_penalty" value="1.05" min="1.0" max="2.0" step="0.05" title="Repetition penalty (default: 1.05)">
                    </div>
                    <div>
                        <label for="{prefix}-max_new_tokens">Max Tokens</label>
                        <input type="number" id="{prefix}-max_new_tokens" value="2048" min="256" max="4096" step="256" title="Max codec tokens (default: 2048)">
                    </div>
                </div>
            </details>"""


INDEX_BODY = """
    <h1>TTS Adapter</h1>
    <p class="subtitle">Text-to-Speech Generation</p>

    <div id="status" class="status">Checking server status...</div>

    <div class="model-selector">
        <label for="model-select">Model:</label>
        <select id="model-select" onchange="onModelSelect(this.value)" title="Switch TTS model (reloads server)">
            <option value="">Loading...</option>
        </select>
        <button type="button" class="model-help" onclick="openModelHelp()" title="Model guide" aria-label="Model guide">?</button>
        <span id="model-features" title="Capabilities for selected model"></span>
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
                <button class="btn-cancel" onclick="cancelSwitch()" title="Cancel model switch" type="button">Cancel</button>
                <button class="btn-confirm" onclick="confirmSwitch()" title="Confirm model switch" type="button">Switch Model</button>
            </div>
        </div>
    </div>

    <!-- Model help modal -->
    <div id="model-help-overlay" class="modal-overlay">
        <div class="modal">
            <h3>Model Guide</h3>
            <div id="model-help-list">Loading model info...</div>
            <div class="modal-buttons">
                <button class="btn-confirm" onclick="closeModelHelp()" title="Close model guide" type="button">Got it</button>
            </div>
        </div>
    </div>

    <!-- Advanced settings help modal -->
    <div id="advanced-help-overlay" class="modal-overlay">
        <div class="modal">
            <h3>Generation Parameters</h3>
            <div class="advanced-help-content">
                <p>These parameters control how the model generates audio tokens. Defaults work well for most cases.</p>
                <ul class="param-help-list">
                    <li><strong>Temperature</strong> (0.9) &mdash; Controls randomness. Lower values (0.3-0.7) produce more consistent, deterministic output. Higher values (1.0-1.5) add variety but may reduce quality.</li>
                    <li><strong>Top-K</strong> (50) &mdash; Limits sampling to the K most likely tokens at each step. Lower values (10-30) make output more focused. Higher values allow more diversity.</li>
                    <li><strong>Top-P</strong> (1.0) &mdash; Nucleus sampling: only considers tokens whose cumulative probability reaches P. Lower values (0.7-0.9) cut unlikely tokens. At 1.0 all tokens are considered.</li>
                    <li><strong>Repetition Penalty</strong> (1.05) &mdash; Penalizes tokens that already appeared. Increase (1.1-1.3) if you hear repeated sounds or artifacts. Too high may distort speech.</li>
                    <li><strong>Max Tokens</strong> (2048) &mdash; Maximum number of audio codec tokens to generate. Increase for very long texts. Each ~256 tokens is roughly 5-10 seconds of audio.</li>
                </ul>
            </div>
            <div class="modal-buttons">
                <button class="btn-confirm" onclick="closeAdvancedHelp()" title="Close parameter guide" type="button">Got it</button>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="tabs">
            <button class="tab active" data-tab="simple" onclick="switchTab('simple')" title="Simple TTS (CustomVoice model)" data-default-title="Simple TTS (CustomVoice model)" type="button">Simple</button>
            <button class="tab" data-tab="design" onclick="switchTab('design')" title="Voice Design (VoiceDesign model)" data-default-title="Voice Design (VoiceDesign model)" type="button">Voice Design</button>
            <button class="tab" data-tab="clone" onclick="switchTab('clone')" title="Voice Clone (Base model)" data-default-title="Voice Clone (Base model)" type="button">Voice Clone</button>
        </div>

        <!-- Simple TTS Tab -->
        <div id="tab-simple" class="tab-content active">
            <label for="text">Text to speak</label>
            <textarea id="text" placeholder="Enter text here..." title="Required text to synthesize"></textarea>

            <div class="row">
                <div>
                    <label for="language">Language</label>
                    <select id="language" title="Language for output speech">
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
                    <select id="speaker" title="Preset speaker (CustomVoice model)">
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
            <input type="text" id="instruct" placeholder="e.g., Speak slowly and warmly" title="Optional style instruction (CustomVoice model)">
            <p class="hint">Control tone, emotion, speed. Works with CustomVoice model only.</p>
""" + _advanced_settings("simple") + """

            <button onclick="generateSimple()" title="Generate speech with current settings" type="button">Generate Speech</button>
        </div>

        <!-- Voice Design Tab -->
        <div id="tab-design" class="tab-content">
            <label for="design-text">Text to speak</label>
            <textarea id="design-text" placeholder="Enter text here..." title="Required text to synthesize"></textarea>

            <label for="design-language">Language</label>
            <select id="design-language" title="Language for output speech">
                <option value="Russian">Russian</option>
                <option value="English">English</option>
                <option value="Chinese">Chinese</option>
            </select>

            <label for="design-instruct">Voice description (required)</label>
            <textarea id="design-instruct" placeholder="e.g., Adult female voice, contralto range, warm and confident, expressive" title="Required voice description (VoiceDesign model)"></textarea>
            <p class="hint">Describe the voice: gender, age, pitch, timbre, emotion, pace. We trim trailing silence.</p>
""" + _advanced_settings("design") + """

            <button onclick="generateDesign()" title="Generate speech with designed voice" type="button">Generate with Designed Voice</button>
        </div>

        <!-- Voice Clone Tab -->
        <div id="tab-clone" class="tab-content">
            <label for="clone-text">Text to speak</label>
            <textarea id="clone-text" placeholder="Enter text here..." title="Required text to synthesize"></textarea>

            <label for="clone-language">Language</label>
            <select id="clone-language" title="Language for output speech">
                <option value="Russian">Russian</option>
                <option value="English">English</option>
                <option value="Chinese">Chinese</option>
            </select>

            <label for="clone-audio">Reference audio (WAV, 3-10 sec)</label>
            <input type="file" id="clone-audio" accept=".wav,audio/wav" title="Required WAV file, 3-10 seconds">

            <label for="clone-ref-text">Reference transcript (optional, improves quality)</label>
            <input type="text" id="clone-ref-text" placeholder="What is said in the reference audio" title="Optional transcript of the reference audio">
""" + _advanced_settings("clone") + """

            <button onclick="generateClone()" title="Generate speech with cloned voice" type="button">Generate with Cloned Voice</button>
        </div>

        <div id="gen-progress" class="progress" aria-live="polite">
            <div id="gen-progress-label" class="progress-label">Generating audio...</div>
            <div class="progress-bar"><div class="progress-bar-inner"></div></div>
            <div id="gen-progress-hint" class="progress-hint">First request after model load can be slower.</div>
        </div>

        <div id="result" class="result">
            <strong>Result:</strong>
            <audio id="audio" controls></audio>
            <br>
            <a id="download" class="download-btn" download="tts_output.wav" title="Download generated WAV">Download WAV</a>
        </div>
    </div>

    <p style="text-align: center; color: #999; font-size: 12px;">
        <a href="/docs" style="color: #666;">API Documentation</a> |
        <a href="/health" style="color: #666;">Health Check</a>
    </p>
"""
