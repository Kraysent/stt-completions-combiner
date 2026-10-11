import asyncio

import httpx
import pytest

from stt_completions_combiner import stt


def test_transcribe_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/audio/transcriptions")
        return httpx.Response(200, json={"text": "hello world"})

    transport = httpx.MockTransport(handler)

    async def run() -> str:
        async with httpx.AsyncClient(transport=transport) as client:
            return await stt.transcribe(
                client,
                base_url="http://stt.example/v1",
                model="whisper",
                audio_bytes=b"abc",
                audio_format="wav",
                authorization="Bearer test",
            )

    assert asyncio.run(run()) == "hello world"


def test_transcribe_non_2xx_maps_to_stt_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            await stt.transcribe(
                client,
                base_url="http://stt.example/v1",
                model="whisper",
                audio_bytes=b"abc",
                audio_format="wav",
                authorization=None,
            )

    with pytest.raises(stt.SttError) as exc_info:
        asyncio.run(run())
    assert "500" in exc_info.value.message
