import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from stt_completions_combiner.config import Settings
from stt_completions_combiner.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def _settings() -> Settings:
    return Settings(
        completions_base_url="http://completions.example",
        stt_base_url="http://stt.example/v1",
        stt_model="whisper-test",
    )


def _client(transport: httpx.MockTransport) -> TestClient:
    stt_client = httpx.AsyncClient(transport=transport, base_url="http://stt.example")
    completions_client = httpx.AsyncClient(transport=transport, base_url="http://completions.example")
    app = create_app(
        _settings(),
        stt_client=stt_client,
        completions_client=completions_client,
    )
    return TestClient(app)


def test_healthz() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="should not be called")

    with _client(httpx.MockTransport(handler)) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_chat_with_audio_hits_stt_then_completions() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "from audio"})
        if request.url.path.endswith("/v1/chat/completions"):
            body = json.loads(request.content)
            assert body["messages"][0]["content"] == "from audio"
            return httpx.Response(200, json={"id": "chatcmpl-1", "choices": []})
        return httpx.Response(404, text="missing")

    payload = json.loads((FIXTURES / "chat_with_audio.json").read_text())
    with _client(httpx.MockTransport(handler)) as client:
        response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-1"
    assert calls == ["POST /v1/audio/transcriptions", "POST /v1/chat/completions"]


def test_chat_streaming_bytes_pass_through() -> None:
    stream_body = b'data: {"id":"1"}\n\ndata: [DONE]\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "stream me"})
        return httpx.Response(
            200,
            content=stream_body,
            headers={"content-type": "text/event-stream"},
        )

    payload = json.loads((FIXTURES / "chat_with_audio.json").read_text())
    payload["stream"] = True
    with _client(httpx.MockTransport(handler)) as client:
        with client.stream("POST", "/v1/chat/completions", json=payload) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.read() == stream_body


def test_text_only_never_calls_stt() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    payload = json.loads((FIXTURES / "chat_text_only.json").read_text())
    with _client(httpx.MockTransport(handler)) as client:
        response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    assert calls == ["/v1/chat/completions"]


def test_stt_failure_returns_stt_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"ok": True})

    payload = json.loads((FIXTURES / "chat_with_audio.json").read_text())
    with _client(httpx.MockTransport(handler)) as client:
        response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "stt_error"


def test_passthrough_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

    with _client(httpx.MockTransport(handler)) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_audio_passthrough_routes_to_stt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://stt.example/v1/audio/transcriptions"
        return httpx.Response(200, json={"text": "direct"})

    with _client(httpx.MockTransport(handler)) as client:
        response = client.post("/v1/audio/transcriptions", files={"file": ("a.wav", b"abc", "audio/wav")})

    assert response.status_code == 200
    assert response.json() == {"text": "direct"}
