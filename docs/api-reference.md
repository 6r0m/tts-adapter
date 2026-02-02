# API Reference

Base URL: `http://localhost:9880`

## Endpoints

### GET /health

Health check with model info.

**Response:**
```json
{
  "ok": true,
  "engine": "qwen3",
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
  "device": "cuda:0"
}
```

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

**Response:** `audio/wav` binary

**Example:**
```bash
curl -X POST http://localhost:9880/tts \
  -H 'content-type: application/json' \
  -d '{"text":"Привет мир","language":"Russian"}' \
  --output out.wav
```

### POST /tts/batch

Generate multiple WAV files as ZIP archive.

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
| items | array | List of TTS items |
| items[].id | string | Unique ID (used as filename) |
| items[].text | string | Text to synthesize |
| items[].language | string | Language code |
| items[].speaker | string | Speaker name |
| items[].instruct | string | Style instruction |

**Response:** `application/zip` containing `{id}.wav` files

**Example:**
```bash
curl -X POST http://localhost:9880/tts/batch \
  -H 'content-type: application/json' \
  -d '{"items":[{"id":"001","text":"Привет"},{"id":"002","text":"Мир"}]}' \
  --output batch.zip

unzip batch.zip -d output/
```

## Error Responses

Standard HTTP error codes with JSON body:

```json
{
  "detail": "Error message"
}
```

| Code | Description |
|------|-------------|
| 400 | Invalid request |
| 500 | Internal server error |
