"""Bot settings from the environment (.env.example). Everything external has a fake."""

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Env = Literal["local", "test", "production"]


class Settings(BaseSettings):
    """Values of .env.example; the bot starts without real secrets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Env = Field(default="local", alias="ENV")
    bot_token: str = Field(default="000:fake", alias="BOT_TOKEN")
    bot_mode: Literal["polling", "webhook"] = Field(default="polling", alias="BOT_MODE")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    webhook_secret: str = Field(default="change-me", alias="WEBHOOK_SECRET")
    bot_use_fake_api: bool = Field(default=True, alias="BOT_USE_FAKE_API")
    api_base_url: str = Field(default="http://api:8000/v1", alias="API_BASE_URL")
    internal_api_token: str = Field(default="change-me", alias="INTERNAL_API_TOKEN")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    # "1,2,3" in the env, not JSON
    admin_tg_ids: Annotated[frozenset[int], NoDecode] = Field(
        default=frozenset(), alias="ADMIN_TG_IDS"
    )
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    support_username: str = Field(default="svoi_support", alias="SUPPORT_USERNAME")

    # Caddy forwards https://<domain>/tg/webhook to bot:8080 (infra/Caddyfile)
    webhook_path: str = "/tg/webhook"
    webhook_port: int = 8080

    @field_validator("admin_tg_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(int(x) for x in value.replace(" ", "").split(",") if x)
        if isinstance(value, int):
            return frozenset({value})
        return value

    @property
    def dev_routes(self) -> bool:
        """/kitchen_sink and other dev screens."""
        return self.env in ("local", "test")
