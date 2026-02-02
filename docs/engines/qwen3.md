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
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | 1.7B | ~8GB | Best quality |
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | 0.6B | ~4GB | Faster, lighter |

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
TTS_DEFAULT_SPEAKER=Sohee
TTS_DEFAULT_LANGUAGE=Russian
```

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

**For Russian female voice**: Use `Sohee` (warm tone) or `Serena` (gentle tone).

**Supported languages**: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

## Instruction Examples

The `instruct` field controls speaking style:

| Instruction | Effect |
|-------------|--------|
| "Calm, friendly" | Neutral, approachable tone |
| "Energetic, excited" | Higher energy delivery |
| "Slow, thoughtful" | Slower pace with pauses |
| "Professional, formal" | Business-like tone |

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
