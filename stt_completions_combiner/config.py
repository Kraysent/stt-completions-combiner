from typing import Self

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    completions_base_url: str
    stt_base_url: str
    stt_model: str
    stt_api_key: str | None = None
    completions_api_key: str | None = None
    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8080
    max_body_mb: int = 50
    stt_timeout_s: float = 120
    completions_timeout_s: float = 600
    transcript_prefix: str = ""

    @property
    def max_body_bytes(self) -> int:
        return self.max_body_mb * 1024 * 1024

    @classmethod
    def from_env(cls) -> Self:
        return cls.model_validate({})
