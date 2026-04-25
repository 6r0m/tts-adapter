# Multi-Client Model Sync

> **Backlog** - low priority, only matters when multiple clients use the server simultaneously

## Problem
When two clients (PCs) use the same TTS server, one can switch the model (e.g. to VoiceDesign),
and the other client's UI stays stale — showing old model state. If the second client switches
back, the first client gets 400 errors on `/tts/design`.

## Minimal Fix (recommended)
- [x] Add periodic health polling (~3-5s interval) in `templates_script.py`
  - `setInterval(checkStatus, 3000)` — keeps all clients in sync with actual server model
  - Tabs auto-update when model changes, new mode appears within seconds
  - Cheapest fix, covers 90% of the problem

## Nice-to-Have (if needed later)
- [ ] Store preferred model + active tab in `localStorage`
  - On page load: if stored model ≠ server model, prompt user or auto-switch
- [ ] Pre-request model validation in `generateDesign`/`generateClone`
  - Before sending TTS request, `GET /health` to verify model still matches
  - Show clear error: "Model was switched by another client" instead of generic 400
