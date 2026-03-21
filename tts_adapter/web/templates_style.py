"""CSS for web UI."""

INDEX_STYLE = """
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
.title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
}
.lang-toggle {
    background: none;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    color: #666;
    width: auto;
    margin-top: 5px;
}
.lang-toggle:hover { background: #f0f0f0; border-color: #999; color: #333; }
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
.status {
    padding: 10px;
    background: #e3f2fd;
    border-radius: 4px;
    margin-bottom: 15px;
    font-size: 13px;
}
.status.ok { background: #e8f5e9; }
.status.error { background: #ffebee; }
.hint { font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 15px; }
.progress {
    display: none;
    margin-top: 15px;
    padding: 12px;
    background: #fff3e0;
    border-radius: 4px;
}
.progress.active { display: block; }
.progress-label { font-weight: 600; color: #6d4c41; margin-bottom: 8px; }
.progress-hint { font-size: 12px; color: #6d4c41; margin-top: 8px; }
.progress-bar {
    position: relative;
    height: 6px;
    background: #ffe0b2;
    border-radius: 4px;
    overflow: hidden;
}
.progress-bar-inner {
    position: absolute;
    left: -40%;
    width: 40%;
    height: 100%;
    background: #4CAF50;
    animation: progress-slide 1.2s ease-in-out infinite;
}
@keyframes progress-slide {
    0% { transform: translateX(0); }
    100% { transform: translateX(350%); }
}
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
.tab.tab-disabled {
    opacity: 0.45;
    cursor: not-allowed;
}
.tab.tab-disabled:hover { background: #e0e0e0; }
.tab.tab-hidden { display: none; }
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
.model-help {
    width: 24px;
    height: 24px;
    padding: 0;
    border-radius: 50%;
    border: 1px solid #f57c00;
    background: #fff8e1;
    color: #f57c00;
    font-weight: 700;
    font-size: 13px;
    line-height: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}
.model-help:hover, .model-help:focus { background: #ffe0b2; }
#model-help-list { color: #555; }
.model-help-items { margin: 10px 0 0 0; padding-left: 18px; }
.model-help-items li { margin-bottom: 6px; }
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
/* Advanced settings */
.advanced-settings {
    margin: 10px 0 15px 0;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 0;
}
.advanced-settings summary {
    padding: 10px 12px;
    cursor: pointer;
    font-weight: 500;
    color: #666;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    user-select: none;
    list-style: none;
    background: #fafafa;
    border-radius: 4px;
}
.advanced-settings summary::-webkit-details-marker { display: none; }
.advanced-settings summary:hover { color: #333; background: #f0f0f0; }
.advanced-settings[open] summary {
    border-bottom: 1px solid #e0e0e0;
    border-radius: 4px 4px 0 0;
}
.advanced-arrow {
    display: inline-block;
    width: 0;
    height: 0;
    border-left: 5px solid #999;
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    transition: transform 0.2s;
}
.advanced-settings[open] .advanced-arrow {
    transform: rotate(90deg);
}
.advanced-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    padding: 12px;
}
.advanced-grid label { font-size: 12px; color: #666; margin-bottom: 3px; }
.advanced-grid input {
    width: 100%;
    padding: 6px 8px;
    font-size: 13px;
    margin-bottom: 0;
}
.param-help {
    width: 20px;
    height: 20px;
    padding: 0;
    border-radius: 50%;
    border: 1px solid #f57c00;
    background: #fff8e1;
    color: #f57c00;
    font-weight: 700;
    font-size: 11px;
    line-height: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    margin-left: auto;
}
.param-help:hover { background: #ffe0b2; }
.advanced-help-content { color: #555; font-size: 13px; line-height: 1.5; }
.param-help-list { margin: 10px 0; padding-left: 18px; }
.param-help-list li { margin-bottom: 8px; }
"""
