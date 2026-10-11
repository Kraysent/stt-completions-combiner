import json
from typing import cast

import httpx
from fastapi import FastAPI, Request, Response

from stt_completions_combiner import errors, proxy, rewrite, stt
from stt_completions_combiner.config import Settings


def register_routes(app: FastAPI) -> None:
    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/v1/chat/completions", chat_completions, methods=["POST"])
    app.add_api_route(
        "/{path:path}",
        passthrough,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )


async def healthz() -> dict[str, bool]:
    return {"ok": True}


async def chat_completions(request: Request) -> Response:
    settings = cast(Settings, request.app.state.settings)
    body = await _read_body(request, settings.max_body_bytes)
    if body is None:
        return errors.openai_error(
            message=f"Request body exceeds MAX_BODY_MB ({settings.max_body_mb})",
            error_type="invalid_request_error",
            code="invalid_request",
            status_code=413,
        )

    forward_body = body
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict) and rewrite.has_input_audio(parsed):
        try:
            audio_parts = rewrite.extract_audio_parts(parsed)
        except rewrite.InvalidAudioError as exc:
            return errors.openai_error(
                message=exc.message,
                error_type="invalid_request_error",
                code="invalid_audio",
                status_code=400,
            )

        stt_auth = _authorization_for_upstream(
            request,
            override=settings.stt_api_key,
        )
        transcripts: dict[int, str] = {}
        stt_client = cast(httpx.AsyncClient, request.app.state.stt_client)
        try:
            for index, audio_bytes, audio_format in audio_parts:
                transcripts[index] = await stt.transcribe(
                    stt_client,
                    base_url=settings.stt_base_url,
                    model=settings.stt_model,
                    audio_bytes=audio_bytes,
                    audio_format=audio_format,
                    authorization=stt_auth,
                )
        except stt.SttError as exc:
            return errors.openai_error(
                message=exc.message,
                error_type="api_error",
                code="stt_error",
                status_code=502,
            )

        rewritten = rewrite.apply_transcripts(
            parsed,
            transcripts,
            prefix=settings.transcript_prefix,
        )
        forward_body = json.dumps(rewritten).encode("utf-8")

    completions_headers = proxy.filter_request_headers(
        request.headers,
        authorization_override=_header_override(settings.completions_api_key),
    )
    completions_headers["Content-Type"] = "application/json"

    url = proxy.build_upstream_url(
        settings.completions_base_url,
        request.url.path,
        request.url.query,
    )
    completions_client = cast(httpx.AsyncClient, request.app.state.completions_client)
    try:
        return await proxy.forward(
            completions_client,
            method="POST",
            url=url,
            headers=completions_headers,
            content=forward_body,
        )
    except proxy.UpstreamError as exc:
        return errors.openai_error(
            message=exc.message,
            error_type="api_error",
            code="upstream_error",
            status_code=502,
        )


async def passthrough(request: Request, path: str) -> Response:
    settings = cast(Settings, request.app.state.settings)
    body = await _read_body(request, settings.max_body_bytes)
    if body is None:
        return errors.openai_error(
            message=f"Request body exceeds MAX_BODY_MB ({settings.max_body_mb})",
            error_type="invalid_request_error",
            code="invalid_request",
            status_code=413,
        )

    full_path = f"/{path}" if path else "/"
    if full_path.startswith("/v1/audio"):
        base_url = settings.stt_base_url
        upstream_path = full_path.removeprefix("/v1")
        auth_override = _header_override(settings.stt_api_key)
        client = cast(httpx.AsyncClient, request.app.state.stt_client)
    else:
        base_url = settings.completions_base_url
        upstream_path = full_path
        auth_override = _header_override(settings.completions_api_key)
        client = cast(httpx.AsyncClient, request.app.state.completions_client)

    headers = proxy.filter_request_headers(
        request.headers,
        authorization_override=auth_override,
    )
    url = proxy.build_upstream_url(base_url, upstream_path, request.url.query)
    try:
        return await proxy.forward(
            client,
            method=request.method,
            url=url,
            headers=headers,
            content=body if body else None,
        )
    except proxy.UpstreamError as exc:
        return errors.openai_error(
            message=exc.message,
            error_type="api_error",
            code="upstream_error",
            status_code=502,
        )


async def _read_body(request: Request, max_bytes: int) -> bytes | None:
    body = await request.body()
    if len(body) > max_bytes:
        return None
    return body


def _authorization_for_upstream(request: Request, *, override: str | None) -> str | None:
    if override:
        return f"Bearer {override}" if not override.lower().startswith("bearer ") else override
    return request.headers.get("authorization")


def _header_override(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if api_key.lower().startswith("bearer "):
        return api_key
    return f"Bearer {api_key}"
