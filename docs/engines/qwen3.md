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
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | 1.7B | ~8GB | Preset speakers + instruct (default) |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | 1.7B | ~8GB | **Voice cloning** |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | 1.7B | ~8GB | **Create voices from description** |
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | 0.6B | ~4GB | Faster, lighter |
| `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | 0.6B | ~4GB | Voice cloning (lighter) |

For RTX 4070 (12GB), use 1.7B model with bf16.

### Model Capabilities

| Feature | CustomVoice | Base | VoiceDesign |
|---------|:-----------:|:----:|:-----------:|
| Preset speakers (Serena, Ryan, etc.) | ✅ | ❌ | ❌ |
| Emotion/style via `instruct` | ✅ | ❌ | ✅ (in description) |
| Voice cloning from audio | ❌ | ✅ | ❌ |
| Create voice from description | ❌ | ❌ | ✅ |
| Batch generation | ✅ | ✅ | ✅ |

**Limitation:** Cannot combine cloned voice with emotion control. Each model has separate capabilities:
- Want emotion control? → Use CustomVoice (preset speakers) or VoiceDesign (create new voice)
- Want specific person's voice? → Use Base (clone), but no emotion control

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

## Instruction Control (CustomVoice)

The `instruct` parameter controls tone, emotion, speed, and style. Works with **CustomVoice** model only.

### What `instruct` can control

| Aspect | Examples |
|--------|----------|
| **Emotion** | "angry", "happy", "sad", "excited", "calm" |
| **Tone** | "professional", "friendly", "serious", "playful" |
| **Speed** | "speak slowly", "fast pace", "deliberate" |
| **Style** | "whisper", "shout", "hesitant", "confident" |
| **Combined** | "Speak slowly and calmly with a warm tone" |

### Instruction Examples

| Instruction | Effect |
|-------------|--------|
| `"Calm, friendly"` | Neutral, approachable tone |
| `"Energetic, excited"` | Higher energy delivery |
| `"Slow, thoughtful"` | Slower pace with pauses |
| `"Professional, formal"` | Business-like tone |
| `"Speak angrily"` | Angry emotional delivery |
| `"Whisper softly"` | Quiet, intimate voice |
| `"用特别愤怒的语气说"` | Chinese: speak very angrily |

### CLI Usage

```bash
# With instruct parameter
PYTHONPATH=. uv run python scripts/qwen3/tts.py "Hello world" --instruct "Speak slowly and calmly"

# Via make (requires CustomVoice model)
make tts text="Hello" instruct="excited, happy"
```

### API Usage

```bash
curl -X POST http://localhost:9880/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world","speaker":"Serena","instruct":"Speak slowly and warmly"}'
```

**Note:** `instruct` only works with CustomVoice model. For Base model (cloning), voice characteristics come from reference audio.

## Voice Design

Create custom voices from natural language descriptions using the **VoiceDesign** model. No reference audio needed - describe the voice you want.

### Setup

Switch to VoiceDesign model in `.env`:
```bash
TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

### CLI Usage

```bash
# Create a voice from description
PYTHONPATH=. uv run python scripts/qwen3/tts_design.py "Hello world" \
  --instruct "Young female voice, warm and friendly, slight Russian accent"

# Via make
make tts-design text="Hello" instruct="Deep male voice, professional newsreader"
```

### API Usage

```bash
curl -X POST http://localhost:9880/tts/design \
  -F 'text=Привет мир' \
  -F 'language=Russian' \
  -F 'instruct=Young female voice, warm and expressive' \
  --output designed.wav
```

### Crafting Voice Descriptions

The `instruct` parameter accepts natural language descriptions. Include these elements:

| Element | Examples | Effect |
|---------|----------|--------|
| **Gender** | "female", "male", "woman", "man" | Base voice type |
| **Age** | "young", "mature", "in her 30s", "elderly" | Voice maturity |
| **Pitch** | "high-pitched", "low voice", "contralto", "bass" | Vocal range |
| **Timbre** | "warm", "husky", "bright", "rich", "throaty" | Voice texture |
| **Emotion** | "confident", "friendly", "sensual", "commanding" | Personality |
| **Dynamics** | "expressive", "dynamic intonation", "monotone" | Variation |
| **Pace** | "slow deliberate", "fast energetic", "natural rhythm" | Speed |

### Common Pitfalls

**Problem: Got male voice when wanting female**

The model interprets "deep", "low pitch", "husky" as male. Fix with musical terms:

```bash
# BAD - may produce male voice
--instruct "Deep husky voice, low pitch, commanding"

# GOOD - explicitly female with contralto (lowest female voice type)
--instruct "Adult female voice, contralto range, rich warm timbre, confident"
```

**Problem: Voice too childish/high**

Add maturity descriptors:

```bash
# BAD - may be too high
--instruct "Female voice, warm and friendly"

# GOOD - specify age and maturity
--instruct "Mature woman in her 30s, rich warm timbre, confident"
```

**Problem: Voice is monotone/flat**

Add expression descriptors:

```bash
# BAD - may be flat
--instruct "Female voice, professional"

# GOOD - add dynamics
--instruct "Female voice, professional, expressive with dynamic intonation, varied rhythm"
```

### Tested Voice Recipes

**Attractive mature female (Angelina Jolie style):**
```
Adult female voice, contralto range, rich and warm timbre, confident woman
in her 30s, slightly husky but distinctly feminine, emotionally expressive
with dynamic intonation, charismatic and engaging, sensual undertone
```

**Professional female narrator:**
```
Adult female voice, mezzo-soprano, clear and articulate, professional tone,
warm but authoritative, natural pace with good rhythm
```

**Energetic young female:**
```
Young woman in her 20s, bright voice, energetic and enthusiastic,
friendly and warm, natural expressiveness
```

**Deep authoritative male:**
```
Mature male voice, bass range, deep and resonant, authoritative and
commanding, professional newsreader style, clear articulation
```

**Warm storyteller:**
```
Adult female voice, warm rich timbre, charismatic storyteller energy,
emotionally engaging, varied rhythm with natural pauses, captivating presence
```

### Simple Examples

| Description | Result |
|-------------|--------|
| `"Young female, warm, friendly"` | Approachable female voice |
| `"Deep male, authoritative, newsreader"` | Professional male announcer |
| `"Elderly woman, gentle, grandmother-like"` | Warm elderly female |
| `"Teen male, energetic, gaming streamer"` | Youthful excited male |
| `"体现撒娇稚嫩的萝莉女声"` | Chinese: cute young girl voice |

### Voice Design Workflow

1. **Start simple** - begin with basic description
2. **Listen and iterate** - adjust based on what you hear
3. **Add specifics** - pitch, timbre, emotion, dynamics
4. **Save good results** - keep the WAV file
5. **Clone for consistency** - use saved WAV as reference with Base model

**Tip:** VoiceDesign creates unique voices each run. For consistent voice across texts, generate one you like, save it, then clone it with Base model.

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
- Set language explicitly (`Russian`), don't use `Auto`
- Use whisper-small instead of whisper-tiny for better transcription accuracy

### Generation Parameters

The `generate_voice_clone()` method accepts HuggingFace Transformers generation kwargs for fine-tuning output quality:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `temperature` | ~1.0 | Lower = more deterministic, try 0.7-0.8 |
| `top_p` | ~0.9 | Nucleus sampling threshold |
| `top_k` | - | Limit token choices |
| `repetition_penalty` | 1.0 | Higher reduces repetition artifacts, try 1.1 |

These parameters are not yet exposed via CLI/API - requires code changes to `synthesize_clone()`.

### Transcribing Reference Audio

To get the best cloning quality, transcribe your reference audio first. Use HuggingFace whisper via transformers (already installed as qwen-tts dependency):

```bash
# Quick transcription (tiny model, ~1GB VRAM)
uv run python -c "
from transformers import pipeline
asr = pipeline('automatic-speech-recognition', model='openai/whisper-tiny', device='cuda:0')
result = asr('voice_sample.wav', generate_kwargs={'language': 'russian'})
print(result['text'])
"

# Better quality (small model, ~2GB VRAM)
uv run python -c "
from transformers import pipeline
asr = pipeline('automatic-speech-recognition', model='openai/whisper-small', device='cuda:0')
result = asr('voice_sample.wav', generate_kwargs={'language': 'russian'})
print(result['text'])
"
```

Available models (trade-off between speed and accuracy):
| Model | VRAM | Use Case |
|-------|------|----------|
| `openai/whisper-tiny` | ~1GB | Quick transcription |
| `openai/whisper-small` | ~2GB | Good balance |
| `openai/whisper-medium` | ~5GB | Better accuracy |
| `openai/whisper-large-v3` | ~10GB | Best accuracy |

Models download automatically on first use to `~/.cache/huggingface/hub/`.

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
