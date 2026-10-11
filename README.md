# stt-completions-combiner

OpenAI-compatible gateway that accepts `input_audio` on `/v1/chat/completions`, transcribes it via an STT upstream, rewrites the message to text, and forwards to a completions upstream (streaming supported).

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `COMPLETIONS_BASE_URL` | yes | — | Completions upstream base (e.g. `http://localhost:8642`) |
| `STT_BASE_URL` | yes | — | STT upstream base including `/v1` (e.g. `http://localhost:8000/v1`) |
| `STT_MODEL` | yes | — | Model id sent to STT |
| `STT_API_KEY` | no | — | If unset, forwards client `Authorization` to STT |
| `COMPLETIONS_API_KEY` | no | — | If unset, forwards client `Authorization` to completions |
| `PROXY_HOST` | no | `0.0.0.0` | Bind host |
| `PROXY_PORT` | no | `8080` | Bind port |
| `MAX_BODY_MB` | no | `50` | Max request body size |
| `STT_TIMEOUT_S` | no | `120` | STT request timeout |
| `COMPLETIONS_TIMEOUT_S` | no | `600` | Completions request timeout |
| `TRANSCRIPT_PREFIX` | no | empty | Optional prefix before injected transcript text |

## Run

```bash
export COMPLETIONS_BASE_URL=http://localhost:8642
export STT_BASE_URL=http://localhost:8000/v1
export STT_MODEL=whisper-1

uv run stt-completions-combiner serve
# or
uv run python -m stt_completions_combiner
```

## Example

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "my-model",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_audio",
            "input_audio": {
              "data": "'"$(base64 -i audio.wav)"'",
              "format": "wav"
            }
          }
        ]
      }
    ]
  }'
```

`GET /healthz` returns `{"ok": true}`. Other paths are proxied to the completions upstream; `/v1/audio/*` is proxied to the STT upstream.
