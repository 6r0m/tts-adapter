# API Reference

Base URL: `http://localhost:9880`

## Web UI

Access the web interface at **http://localhost:9880/** for easy TTS generation without coding.

### Features

- **Simple TTS** - Select speaker, language, enter text, generate speech
- **Voice Design** - Create custom voices from text descriptions
- **Voice Clone** - Clone voice from audio sample (requires Base model)
- **Audio Player** - Listen to results directly in browser
- **Download** - Save generated WAV files

### Screenshots

The UI has three tabs:

| Tab | Description | Model Required |
|-----|-------------|----------------|
| Simple | Preset speakers + style instructions | CustomVoice |
| Voice Design | Create voice from description | VoiceDesign |
| Voice Clone | Clone from audio sample | Base |

### Status Bar

Shows server info: engine, model, and supported features (cloning/design).

---

## API Endpoints

### GET /health

Health check with model info.

**Response:**
```json
{
  "ok": true,
  "engine": "qwen3",
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
  "device": "cuda:0",
  "supports_cloning": false,
  "supports_design": false
}
```

| Field | Description |
|-------|-------------|
| ok | Always true if server is healthy |
| engine | Engine name (e.g., "qwen3") |
| model | Loaded model ID |
| device | Device (e.g., "cuda:0", "cpu") |
| supports_cloning | Whether `/tts/clone` is available |
| supports_design | Whether `/tts/design` is available |

### POST /tts

Generate WAV audio from text.

**Request:**
```json
{
  "text": "Привет мир",
  "language": "Russian",
  "speaker": "Ryan",
  "instruct": "Calm, friendly"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| text | string | required | Text to synthesize |
| language | string | "Auto" | Language code or "Auto" |
| speaker | string | "default" | Speaker/voice name |
| instruct | string | "" | Style instruction |
| generation | object | {} | Optional generation parameters (see below) |

**Generation parameters** (all optional, `null` = library default):

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| temperature | float | 0.9 | 0.01-2.0 | Sampling randomness |
| top_k | int | 50 | 1-200 | Top-k sampling |
| top_p | float | 1.0 | 0.1-1.0 | Nucleus sampling |
| repetition_penalty | float | 1.05 | 1.0-2.0 | Repetition penalty |
| max_new_tokens | int | 2048 | 256-4096 | Max codec tokens |

See [Generation Parameters](engines/qwen3/params.md) for tuning tips.

**Response:** `audio/wav` binary

**Example:**
```bash
curl -X POST http://localhost:9880/tts \
  -H 'content-type: application/json' \
  -d '{"text":"Привет мир","language":"Russian","generation":{"temperature":0.7}}' \
  --output out.wav
```

### POST /tts/batch

Generate multiple WAV files as ZIP archive.

**Note:** All items must share the same `language`, `speaker`, and `instruct` params (batch params are global).

**Request:**
```json
{
  "items": [
    {"id": "001", "text": "First phrase", "language": "Russian"},
    {"id": "002", "text": "Second phrase", "language": "Russian"}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| items | array | List of TTS items (must be non-empty) |
| items[].id | string | Unique ID (used as filename, sanitized) |
| items[].text | string | Text to synthesize |
| items[].language | string | Language code (must match across items) |
| items[].speaker | string | Speaker name (must match across items) |
| items[].instruct | string | Style instruction (must match across items) |

**Response:** `application/zip` containing `{id}.wav` files

**Example:**
```bash
curl -X POST http://localhost:9880/tts/batch \
  -H 'content-type: application/json' \
  -d '{"items":[{"id":"001","text":"Привет"},{"id":"002","text":"Мир"}]}' \
  --output batch.zip

unzip batch.zip -d output/
```

### POST /tts/design

Generate speech with a custom voice created from text description.

**Requires:** VoiceDesign model (`TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`)

**Request:** `multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| text | string | required | Text to synthesize |
| instruct | string | required | Voice description (see [Voice Design Guide](engines/qwen3/README.md#voice-design)) |
| language | string | "Auto" | Language code |
| temperature | float | null | Sampling temperature (0.01-2.0) |
| top_k | int | null | Top-k sampling (1-200) |
| top_p | float | null | Nucleus sampling (0.1-1.0) |
| repetition_penalty | float | null | Repetition penalty (1.0-2.0) |
| max_new_tokens | int | null | Max codec tokens (256-4096) |

**Response:** `audio/wav` binary

**Example:**
```bash
curl -X POST http://localhost:9880/tts/design \
  -F 'text=Привет мир' \
  -F 'language=Russian' \
  -F 'instruct=Adult female voice, contralto range, warm and confident' \
  -F 'temperature=0.7' \
  --output designed.wav
```

### POST /tts/clone

Clone a voice from reference audio sample.

**Requires:** Base model (`TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base`)

**Request:** `multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| text | string | required | Text to synthesize |
| reference_audio | file | required | WAV file (3-10 seconds) |
| reference_text | string | "" | Transcript of reference audio (improves quality) |
| language | string | "Auto" | Language code |
| temperature | float | null | Sampling temperature (0.01-2.0) |
| top_k | int | null | Top-k sampling (1-200) |
| top_p | float | null | Nucleus sampling (0.1-1.0) |
| repetition_penalty | float | null | Repetition penalty (1.0-2.0) |
| max_new_tokens | int | null | Max codec tokens (256-4096) |

**Response:** `audio/wav` binary

**Example:**
```bash
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет мир' \
  -F 'language=Russian' \
  -F 'reference_audio=@voice_sample.wav' \
  -F 'reference_text=Hello world' \
  -F 'temperature=0.7' \
  --output cloned.wav
```

---

## Error Responses

Standard HTTP error codes with JSON body:

```json
{
  "detail": "Error message"
}
```

| Code | Description |
|------|-------------|
| 400 | Invalid request or unsupported feature |
| 422 | Validation error (missing/invalid fields or out-of-range generation params) |
| 500 | Internal server error |
