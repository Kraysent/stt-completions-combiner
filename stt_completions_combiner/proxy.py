from collections.abc import AsyncIterator, Mapping

import httpx
from fastapi import responses
from starlette.datastructures import Headers

HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)


def build_upstream_url(base_url: str, path: str, query: str = "") -> str:
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        return f"{url}?{query}"
    return url


def filter_request_headers(
    headers: Headers | Mapping[str, str],
    *,
    authorization_override: str | None = None,
) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS:
            continue
        if lower == "authorization":
            continue
        if lower.startswith("x-") or lower in {"content-type", "accept", "openai-organization", "openai-project"}:
            filtered[key] = value

    if authorization_override:
        filtered["Authorization"] = authorization_override
    else:
        auth = headers.get("authorization")
        if auth:
            filtered["Authorization"] = auth
    return filtered


def filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}


async def forward(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    headers: Mapping[str, str],
    content: bytes | None = None,
) -> responses.StreamingResponse:
    request = client.build_request(method, url, headers=dict(headers), content=content)
    try:
        upstream = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"Completions upstream unreachable: {exc}") from exc

    status_code = upstream.status_code
    response_headers = filter_response_headers(upstream.headers)

    async def body_iter() -> AsyncIterator[bytes]:
        try:
            if upstream.is_stream_consumed:
                yield upstream.content
            else:
                async for chunk in upstream.aiter_raw():
                    yield chunk
        finally:
            await upstream.aclose()

    return responses.StreamingResponse(
        body_iter(),
        status_code=status_code,
        headers=response_headers,
    )


class UpstreamError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
