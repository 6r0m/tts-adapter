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
"""
