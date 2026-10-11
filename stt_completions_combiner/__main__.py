import uvicorn

from stt_completions_combiner.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "stt_completions_combiner.main:create_app",
        factory=True,
        host=settings.proxy_host,
        port=settings.proxy_port,
    )


if __name__ == "__main__":
    main()
