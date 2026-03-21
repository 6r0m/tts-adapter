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
| **Voice Clone** | Base | Clone from audio sample |

Tabs auto-hide when model doesn't support them. Model can be switched via dropdown (takes ~2 min to reload).

## Advanced Settings

Collapsible section above Generate button. 5 params (Temperature, Top-K, Top-P, Repetition Penalty, Max Tokens) — same for all tabs. Defaults work well; hover any field for use-case guidance.

Full reference with ranges and tuning tips: [params.md](engines/qwen3/params.md)

## Multi-Client Usage

Multiple browsers/PCs can use the same server. Known limitation: model switching is global — if one client switches model, all clients are affected. See [todo/multi_client_sync.md](../todo/multi_client_sync.md) for planned improvements (polling, localStorage sync).

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

Boot order: `applyTranslations()` → `updateLangToggle()` → `checkStatus()` — ensures correct language before async server calls.
