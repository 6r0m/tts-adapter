# Qwen3-TTS Generation Parameters

All generation methods (`generate_custom_voice`, `generate_voice_design`, `generate_voice_clone`) accept the same kwargs for controlling audio token sampling.

## Parameters

| Parameter | Type | Default | Range | Effect |
|---|---|---|---|---|
| `temperature` | float | 0.9 | 0.01 - 2.0 | Sampling randomness. Lower = more deterministic, consistent output. Higher = more varied but may reduce quality. |
| `top_k` | int | 50 | 1 - 200 | Limits sampling to top K most likely tokens per step. Lower = more focused. |
| `top_p` | float | 1.0 | 0.1 - 1.0 | Nucleus sampling threshold. Only tokens whose cumulative probability reaches P are considered. Lower = fewer choices. |
| `repetition_penalty` | float | 1.05 | 1.0 - 2.0 | Penalizes previously generated tokens. Increase if you hear repeated sounds or artifacts. Too high may distort speech. |
| `max_new_tokens` | int | 2048 | 256 - 4096 | Maximum number of audio codec tokens to generate. Increase for very long texts. ~256 tokens = ~5-10 seconds of audio. |

### Not applicable

The library also defines `subtalker_*` params (`subtalker_dosample`, `subtalker_top_k`, `subtalker_top_p`, `subtalker_temperature`) but these are only valid for `qwen3-tts-tokenizer-v2`. The 12Hz models use `qwen3_tts_tokenizer_12hz`, so subtalker params have no effect.

`do_sample` is always `True` (required for sampling to work). Not exposed in UI.

## API Usage

### JSON endpoint (POST /tts)

```json
{
    "text": "Hello world",
    "language": "Russian",
    "speaker": "Serena",
    "generation": {
        "temperature": 0.7,
        "top_k": 30,
        "top_p": 0.9,
        "repetition_penalty": 1.1,
        "max_new_tokens": 2048
    }
}
```

All fields in `generation` are optional. Omitted or `null` values use library defaults.

### FormData endpoints (POST /tts/design, POST /tts/clone)

```bash
curl -X POST http://localhost:9880/tts/design \
  -F 'text=Hello' \
  -F 'instruct=Adult female voice, warm' \
  -F 'language=Russian' \
  -F 'temperature=0.7' \
  -F 'top_k=30'
```

Generation params are passed as individual form fields alongside existing params.

## Tuning Tips

**For more consistent output** (e.g., narration, production):
- Lower temperature (0.5-0.7)
- Lower top_k (20-30)
- Lower top_p (0.8-0.9)

**For more varied/creative output** (e.g., expressive design):
- Higher temperature (0.9-1.2)
- Default top_k (50)
- Default top_p (1.0)

**For reducing repetition artifacts**:
- Increase repetition_penalty (1.1-1.3)
- Don't go above 1.5 as it may distort speech

**For longer texts**:
- Increase max_new_tokens (3072-4096)
- Default 2048 is fine for most sentences
