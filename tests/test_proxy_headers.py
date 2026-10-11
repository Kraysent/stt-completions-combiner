import httpx
from fastapi.testclient import TestClient

from stt_completions_combiner import proxy
from stt_completions_combiner.config import Settings
from stt_completions_combiner.main import create_app


def test_filter_response_headers_strips_date_server_and_normalizes() -> None:
    headers = httpx.Headers(
        {
            "Content-Type": "application/json; charset=utf-8",
            "Date": "Sun, 11 Oct 2026 12:00:00 GMT",
            "Server": "Python/3.13 aiohttp/3.14.3",
            "X-Hermes-Session-Id": "api-abc",
            "Transfer-Encoding": "chunked",
        }
    )

    filtered = proxy.filter_response_headers(headers)

    assert filtered == {
        "content-type": "application/json; charset=utf-8",
        "x-hermes-session-id": "api-abc",
    }


def test_filter_request_headers_normalizes_content_type() -> None:
    headers = httpx.Headers({"Content-Type": "application/json", "Authorization": "Bearer x"})
    filtered = proxy.filter_request_headers(headers)
    filtered["content-type"] = "application/json"

    assert list(filtered) == ["content-type", "authorization"]
    assert filtered["content-type"] == "application/json"


def test_chat_with_upstream_managed_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "chatcmpl-1", "choices": []},
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Date": "Sun, 11 Oct 2026 12:00:00 GMT",
                "Server": "Python/3.13 aiohttp/3.14.3",
                "X-Hermes-Session-Id": "api-abc",
            },
        )

    transport = httpx.MockTransport(handler)
    settings = Settings(
        completions_base_url="http://completions.example",
        stt_base_url="http://stt.example/v1",
        stt_model="whisper-test",
    )
    stt_client = httpx.AsyncClient(transport=transport, base_url="http://stt.example")
    completions_client = httpx.AsyncClient(transport=transport, base_url="http://completions.example")
    app = create_app(settings, stt_client=stt_client, completions_client=completions_client)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-1"
    assert response.headers["x-hermes-session-id"] == "api-abc"
    assert response.headers["content-type"].startswith("application/json")
