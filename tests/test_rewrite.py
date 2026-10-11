import base64

import pytest

from stt_completions_combiner import rewrite


def test_text_only_unchanged() -> None:
    body: dict[str, object] = {
        "messages": [{"role": "user", "content": "hello"}],
    }
    assert rewrite.has_input_audio(body) is False
    assert rewrite.extract_audio_parts(body) == []
    assert rewrite.apply_transcripts(body, {}) == body


def test_audio_to_text_and_flatten() -> None:
    audio_b64 = base64.b64encode(b"abc").decode("ascii")
    body: dict[str, object] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_b64, "format": "wav"},
                    }
                ],
            }
        ],
    }
    assert rewrite.has_input_audio(body) is True
    parts = rewrite.extract_audio_parts(body)
    assert parts == [(0, b"abc", "wav")]
    rewritten = rewrite.apply_transcripts(body, {0: "transcribed"}, prefix="Heard: ")
    messages = rewritten["messages"]
    assert isinstance(messages, list)
    message = messages[0]
    assert isinstance(message, dict)
    assert message["content"] == "Heard: transcribed"


def test_mixed_text_image_audio() -> None:
    audio_b64 = base64.b64encode(b"xyz").decode("ascii")
    body: dict[str, object] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look"},
                    {"type": "image_url", "image_url": {"url": "http://example.com/a.png"}},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_b64, "format": "mp3"},
                    },
                ],
            }
        ],
    }
    rewritten = rewrite.apply_transcripts(body, {2: "said hi"})
    messages = rewritten["messages"]
    assert isinstance(messages, list)
    message = messages[0]
    assert isinstance(message, dict)
    assert message["content"] == [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "http://example.com/a.png"}},
        {"type": "text", "text": "said hi"},
    ]


def test_multiple_audio_parts() -> None:
    body: dict[str, object] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(b"one").decode("ascii"),
                            "format": "wav",
                        },
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(b"two").decode("ascii"),
                            "format": "ogg",
                        },
                    },
                ],
            }
        ],
    }
    parts = rewrite.extract_audio_parts(body)
    assert [item[0] for item in parts] == [0, 1]
    rewritten = rewrite.apply_transcripts(body, {0: "first", 1: "second"})
    messages = rewritten["messages"]
    assert isinstance(messages, list)
    message = messages[0]
    assert isinstance(message, dict)
    assert message["content"] == [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
    ]


def test_invalid_base64() -> None:
    body: dict[str, object] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": "%%%", "format": "wav"},
                    }
                ],
            }
        ],
    }
    with pytest.raises(rewrite.InvalidAudioError):
        rewrite.extract_audio_parts(body)


def test_unsupported_format() -> None:
    body: dict[str, object] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(b"x").decode("ascii"),
                            "format": "aac",
                        },
                    }
                ],
            }
        ],
    }
    with pytest.raises(rewrite.InvalidAudioError):
        rewrite.extract_audio_parts(body)
