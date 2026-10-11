import httpx

MIME_TYPES: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "flac": "audio/flac",
}


class SttError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def transcribe(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    model: str,
    audio_bytes: bytes,
    audio_format: str,
    authorization: str | None,
) -> str:
    url = f"{base_url.rstrip('/')}/audio/transcriptions"
    headers: dict[str, str] = {}
    if authorization:
        headers["Authorization"] = authorization

    mime = MIME_TYPES.get(audio_format, "application/octet-stream")
    files = {"file": (f"audio.{audio_format}", audio_bytes, mime)}
    data = {"model": model}

    try:
        response = await client.post(url, headers=headers, files=files, data=data)
    except httpx.HTTPError as exc:
        raise SttError(f"STT upstream unreachable: {exc}") from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = response.text[:500]
        raise SttError(f"STT upstream returned {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise SttError("STT upstream returned non-JSON response") from exc

    if not isinstance(payload, dict):
        raise SttError("STT upstream returned unexpected JSON payload")
    text = payload.get("text")
    if not isinstance(text, str):
        raise SttError("STT upstream response missing text field")
    return text
