# Web UI

Open **http://localhost:9880** in browser. Works on LAN — any device in same network can access.

## Language Switch

- RU/EN toggle in top-right corner (`[РУ] EN` pill)
- Default: Russian
- Persists via `localStorage` (`ui-lang` key)
- All UI text translated: labels, buttons, tooltips, modals, errors, progress

Implementation: [templates_i18n.py](../tts_adapter/web/templates_i18n.py) — single `TRANSLATIONS` dict, serialized as JSON into `<script>`. Uses `data-i18n` attributes for static text, `t(key)` helper for dynamic JS text.

## Tabs

| Tab | Model Required | Features |
|-----|----------------|----------|
| **Simple** | CustomVoice | Preset speakers + style instruction |
| **Voice Design** | VoiceDesign | Create voice from text description |
| **Voice Clone** | Base / Base+Emotion | Clone from audio sample; emotion controls appear when `/health.supports_emotional_cloning=true` |

Tabs auto-hide when model doesn't support them. Model can be switched via dropdown; the list comes from `GET /models` and labels include the engine prefix, for example `[qwen3] Base 1.7B` or `[indextts2] IndexTTS-2`.

Cross-engine switches unload the current engine and load the selected one. The UI disables the switch action and shows a spinner until `/model/switch` returns.

## Advanced Settings

Collapsible section above Generate button. 5 params (Temperature, Top-K, Top-P, Repetition Penalty, Max Tokens) — same for all tabs. Defaults work well; hover any field for use-case guidance.

Full reference with ranges and tuning tips: [params.md](engines/qwen3/params.md)

## Multi-Client Usage

Multiple browsers/PCs can use the same server. The UI polls `/health` every 3 seconds, so tabs and emotion controls follow model switches made by another client.

**LAN troubleshooting:**
- If Chrome doesn't connect but `curl` works — check proxy settings (Radmin VPN, corporate proxy)
- WSL2: needs port forwarding (`netsh interface portproxy`) + Windows Firewall inbound rule for port 9880

## Architecture

```
templates.py          — assembles HTML from parts
templates_i18n.py     — translations dict + JS i18n helpers (loaded first)
templates_script.py   — main UI logic (uses t() for all strings)
templates_body.py     — HTML structure (data-i18n attributes)
templates_style.py    — CSS
```

Boot order: `applyTranslations()` → `updateLangToggle()` → `checkStatus({ refreshModels: true })` → periodic `/health` polling — ensures correct language before async server calls and keeps model capabilities in sync.
