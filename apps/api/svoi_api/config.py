"""API settings from the environment (.env.example). Everything external has a fake."""

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Env = Literal["local", "test", "production"]


class Settings(BaseSettings):
    """Values of .env.example; the API starts without real secrets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Env = Field(default="local", alias="ENV")
    bot_token: str = Field(default="000:fake", alias="BOT_TOKEN")
    internal_api_token: str = Field(default="change-me", alias="INTERNAL_API_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://svoi:svoi@postgres:5432/svoi", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    # "1,2,3" in the env, not JSON
    admin_tg_ids: Annotated[frozenset[int], NoDecode] = Field(
        default=frozenset(), alias="ADMIN_TG_IDS"
    )
    use_fake_clients: bool = Field(default=True, alias="USE_FAKE_CLIENTS")
    nsfw_url: str = Field(default="http://nsfw:8080", alias="NSFW_URL")
    new_account_tg_id_min: int = Field(default=0, alias="NEW_ACCOUNT_TG_ID_MIN")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    @field_validator("admin_tg_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(int(x) for x in value.replace(" ", "").split(",") if x)
        if isinstance(value, int):
            return frozenset({value})
        return value
