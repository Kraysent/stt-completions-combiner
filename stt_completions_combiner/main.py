from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from stt_completions_combiner import app as app_module
from stt_completions_combiner.config import Settings


def create_app(
    settings: Settings | None = None,
    *,
    stt_client: httpx.AsyncClient | None = None,
    completions_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
        owns_stt = stt_client is None
        owns_completions = completions_client is None
        fastapi_app.state.settings = resolved_settings
        fastapi_app.state.stt_client = stt_client or httpx.AsyncClient(
            timeout=httpx.Timeout(resolved_settings.stt_timeout_s)
        )
        fastapi_app.state.completions_client = completions_client or httpx.AsyncClient(
            timeout=httpx.Timeout(resolved_settings.completions_timeout_s)
        )
        try:
            yield
        finally:
            if owns_stt:
                await fastapi_app.state.stt_client.aclose()
            if owns_completions:
                await fastapi_app.state.completions_client.aclose()

    fastapi_app = FastAPI(title="stt-completions-combiner", lifespan=lifespan)
    app_module.register_routes(fastapi_app)
    return fastapi_app
