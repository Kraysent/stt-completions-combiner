import base64
import binascii

SUPPORTED_AUDIO_FORMATS = frozenset({"wav", "mp3", "webm", "ogg", "m4a", "flac"})
IMAGE_PART_TYPES = frozenset({"image_url", "input_image"})


class InvalidAudioError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def has_input_audio(body: dict[str, object]) -> bool:
    message = _last_user_message_with_list_content(body)
    if message is None:
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(_is_input_audio_part(part) for part in content)


def extract_audio_parts(body: dict[str, object]) -> list[tuple[int, bytes, str]]:
    message = _last_user_message_with_list_content(body)
    if message is None:
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []

    extracted: list[tuple[int, bytes, str]] = []
    for index, part in enumerate(content):
        if not isinstance(part, dict) or part.get("type") != "input_audio":
            continue
        audio = part.get("input_audio")
        if not isinstance(audio, dict):
            raise InvalidAudioError("input_audio part is missing input_audio object")
        raw_data = audio.get("data")
        audio_format = audio.get("format")
        if not isinstance(raw_data, str) or not raw_data:
            raise InvalidAudioError("input_audio.data must be a non-empty base64 string")
        if not isinstance(audio_format, str) or audio_format not in SUPPORTED_AUDIO_FORMATS:
            raise InvalidAudioError(
                f"unsupported or missing input_audio.format; expected one of {sorted(SUPPORTED_AUDIO_FORMATS)}"
            )
        try:
            decoded = base64.b64decode(raw_data, validate=True)
        except binascii.Error as exc:
            raise InvalidAudioError("input_audio.data is not valid base64") from exc
        if not decoded:
            raise InvalidAudioError("input_audio.data decoded to empty bytes")
        extracted.append((index, decoded, audio_format))
    return extracted


def apply_transcripts(
    body: dict[str, object],
    transcripts_by_index: dict[int, str],
    *,
    prefix: str = "",
) -> dict[str, object]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    message_index = _last_user_message_index_with_list_content(messages)
    if message_index is None:
        return body

    message = messages[message_index]
    if not isinstance(message, dict):
        return body
    content = message.get("content")
    if not isinstance(content, list):
        return body

    new_content: list[object] = []
    for index, part in enumerate(content):
        if index in transcripts_by_index:
            new_content.append({"type": "text", "text": f"{prefix}{transcripts_by_index[index]}"})
            continue
        new_content.append(part)

    updated_message = dict(message)
    updated_message["content"] = _maybe_flatten_content(new_content)
    updated_messages = list(messages)
    updated_messages[message_index] = updated_message

    updated_body = dict(body)
    updated_body["messages"] = updated_messages
    return updated_body


def _maybe_flatten_content(content: list[object]) -> list[object] | str:
    if any(_is_image_part(part) for part in content):
        return content
    if len(content) != 1:
        return content
    only = content[0]
    if not isinstance(only, dict) or only.get("type") != "text":
        return content
    text = only.get("text")
    if not isinstance(text, str):
        return content
    return text


def _last_user_message_with_list_content(body: dict[str, object]) -> dict[str, object] | None:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return None
    index = _last_user_message_index_with_list_content(messages)
    if index is None:
        return None
    message = messages[index]
    if not isinstance(message, dict):
        return None
    return message


def _last_user_message_index_with_list_content(messages: list[object]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        if isinstance(message.get("content"), list):
            return index
    return None


def _is_input_audio_part(part: object) -> bool:
    return isinstance(part, dict) and part.get("type") == "input_audio"


def _is_image_part(part: object) -> bool:
    return isinstance(part, dict) and part.get("type") in IMAGE_PART_TYPES
