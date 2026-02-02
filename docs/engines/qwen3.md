# Qwen3-TTS Engine

## Overview

Qwen3-TTS is Alibaba's text-to-speech model with:
- Multi-language support (Russian, English, Chinese, etc.)
- Custom voice with speaker selection
- Instruction-based style control (tone, emotion, speed)
- Batch generation support

## Model Variants

| Model | Size | VRAM | Use Case |
|-------|------|------|----------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | 1.7B | ~8GB | Preset speakers (default) |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | 1.7B | ~8GB | **Voice cloning** |
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | 0.6B | ~4GB | Faster, lighter |
| `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | 0.6B | ~4GB | Voice cloning (lighter) |

For RTX 4070 (12GB), use 1.7B model with bf16.

## Configuration

Engine-specific env vars (namespaced with `TTS_QWEN3_`):

```bash
TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
TTS_QWEN3_DEVICE=cuda:0
TTS_QWEN3_DTYPE=bfloat16
```

Shared settings (all engines):
```bash
TTS_DEFAULT_SPEAKER=Serena
TTS_DEFAULT_LANGUAGE=Russian
```

## Offline Mode

The qwen-tts library (v0.0.5) pins transformers==4.57.3 which has a bug requiring network access on model load. To work fully offline:

1. Download model while online:
   ```bash
   make download-model
   ```

2. Set local path in `.env`:
   ```bash
   TTS_QWEN3_MODEL_PATH=~/.cache/tts-adapter/models/Qwen3-TTS-12Hz-1.7B-CustomVoice
   ```

3. Enable offline mode:
   ```bash
   HF_HUB_OFFLINE=1
   ```

When `TTS_QWEN3_MODEL_PATH` is set, the engine loads from that local directory instead of downloading from HuggingFace.

**Why needed:** transformers 4.57.3 has a bug where `_patch_mistral_regex()` makes a network call even for cached models. Fixed in 4.57.4+, but qwen-tts pins the older version.

## Speakers

9 built-in speakers for CustomVoice model (all support 10 languages including Russian):

| Speaker | Gender | Native | Description |
|---------|--------|--------|-------------|
| Vivian | Female | Chinese | Bright, slightly edgy |
| Serena | Female | Chinese | Warm, gentle |
| Ono_Anna | Female | Japanese | Playful, light |
| Sohee | Female | Korean | Warm, rich emotion |
| Ryan | Male | English | Dynamic, rhythmic |
| Aiden | Male | English | Sunny, clear midrange |
| Uncle_Fu | Male | Chinese | Seasoned, low mellow |
| Dylan | Male | Chinese | Youthful Beijing accent |
| Eric | Male | Chinese | Lively Sichuan accent |

**For Russian female voice**: Use `Serena` (neutral, best for narration) or `Sohee` (emotional, expressive).

**Supported languages**: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

## Instruction Examples

The `instruct` field controls speaking style:

| Instruction | Effect |
|-------------|--------|
| "Calm, friendly" | Neutral, approachable tone |
| "Energetic, excited" | Higher energy delivery |
| "Slow, thoughtful" | Slower pace with pauses |
| "Professional, formal" | Business-like tone |

## Voice Cloning

Qwen3-TTS supports voice cloning via the **Base** model. Clone any voice from a 3-10 second audio sample.

### Setup

Switch to Base model in `.env`:
```bash
TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base
```

### CLI Usage

```bash
# Without transcript (x_vector_only mode - lower quality)
make tts-clone text="Hello world" ref=voice_sample.wav

# With transcript (better quality)
PYTHONPATH=. uv run python scripts/qwen3/tts_clone.py "Hello world" \
  --ref voice_sample.wav \
  --ref-text "Original text from the reference audio"
```

### API Usage

```bash
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет мир' \
  -F 'language=Russian' \
  -F 'reference_audio=@voice_sample.wav' \
  -F 'reference_text=Текст из референсного аудио' \
  --output cloned.wav
```

### Requirements

- **Reference audio**: WAV format, 3-10 seconds, clear speech
- **Reference text** (optional): Transcript of reference audio - significantly improves quality
- **Model**: Must use Base model (CustomVoice doesn't support cloning)
- The `/health` endpoint shows `supports_cloning: true` when Base model is loaded

### Quality Tips

- Provide `reference_text` (transcript) for best quality
- Without transcript, uses `x_vector_only_mode` - faster but lower quality
- Reference audio should be clean, single speaker, no background noise

## Batching

Qwen3-TTS supports batch generation (multiple prompts per forward pass):

```python
texts = ["First phrase", "Second phrase", "Third phrase"]
wavs, sr = model.generate_custom_voice(text=texts, ...)
```

This is more efficient than single-prompt calls. CLI uses `--batch-size 8` by default.

**Note:** Batching = multiple prompts together, not splitting one long prompt.

## Performance Notes

- First request slower (model warmup)
- Flash Attention 2 used if available (faster)
- bf16 recommended for RTX 40xx series
- Single worker (`--workers 1`) for GPU serialization

## Troubleshooting

### OOM (Out of Memory)

Reduce batch size:
```bash
python scripts/tts_batch.py --batch-size 4
```

Or use smaller model:
```bash
TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
```

### Slow First Request

Normal - model loads on first call. Use lifespan warmup (enabled by default in FastAPI app).

### No Flash Attention

Install flash-attn for faster inference:
```bash
pip install flash-attn --no-build-isolation
```
