import click
import uvicorn

from stt_completions_combiner.config import Settings


@click.group()
def cli() -> None:
    pass


@cli.command("serve")
def serve() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "stt_completions_combiner.main:create_app",
        factory=True,
        host=settings.proxy_host,
        port=settings.proxy_port,
    )
