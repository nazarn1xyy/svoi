"""K8 acceptance: config, middlewares and dispatcher assembly; the bot starts on FakeApiClient."""

from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, User, UserProfilePhotos
from svoi_bot.api_client import ApiException, FakeApiClient
from svoi_bot.commands import COMMANDS, commands
from svoi_bot.config import Settings
from svoi_bot.main import build_dispatcher, make_api
from svoi_bot.middlewares import I18nMiddleware, ThrottleMiddleware, UserContextMiddleware
from svoi_bot.ui.i18n import get_locale
from svoi_contracts.cards import UserState
from svoi_contracts.enums import Lang

USER = User(id=500, is_bot=False, first_name="Ira", username="ira", language_code="ru")


class _Bot:
    async def get_user_profile_photos(self, user_id: int, limit: int) -> UserProfilePhotos:
        return UserProfilePhotos(total_count=1, photos=[])


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=500, type="private"),
        from_user=USER,
        text=text,
    )


def _data(state: FSMContext) -> dict[str, Any]:
    return {"event_from_user": USER, "state": state, "bot": _Bot()}


def _state() -> FSMContext:
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=500, user_id=500))


async def _ok(event: object, data: dict[str, Any]) -> str:
    return "handled"


def test_settings_parse_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_TG_IDS", "1, 2,3")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("BOT_USE_FAKE_API", "false")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings kwarg
    assert settings.admin_tg_ids == frozenset({1, 2, 3})
    assert not settings.dev_routes
    assert not settings.bot_use_fake_api


def test_defaults_start_on_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENV", "BOT_USE_FAKE_API", "ADMIN_TG_IDS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings kwarg
    assert isinstance(make_api(settings), FakeApiClient)
    assert settings.dev_routes


@pytest.mark.parametrize(
    ("env", "has_kitchen_sink"), [("local", True), ("test", True), ("production", False)]
)
def test_dispatcher_mounts_dev_routes_only_outside_production(
    env: str, has_kitchen_sink: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENV", env)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings kwarg
    dp = build_dispatcher(FakeApiClient(), MemoryStorage(), settings)
    names = {r.name for r in dp.sub_routers}
    assert ("kitchen_sink" in names) is has_kitchen_sink
    assert "errors" in names


async def test_throttle_allows_two_updates_per_second() -> None:
    clock = _Clock()
    throttle = ThrottleMiddleware(clock)
    data = {"event_from_user": USER}
    results = [await throttle(_ok, _message("x"), data) for _ in range(3)]
    assert results == ["handled", "handled", None]
    clock.now += 1.0
    assert await throttle(_ok, _message("x"), data) == "handled"


async def test_user_context_calls_start_once_then_caches_for_60_s() -> None:
    fake, clock, state = FakeApiClient(), _Clock(), _state()
    middleware = UserContextMiddleware(fake, clock)
    seen: list[UserState] = []

    async def handler(event: object, data: dict[str, Any]) -> None:
        seen.append(data["user_state"])

    await middleware(handler, _message("hi"), _data(state))
    await middleware(handler, _message("again"), _data(state))
    assert [c.name for c in fake.calls] == ["start"]
    clock.now += 61
    await middleware(handler, _message("later"), _data(state))
    assert [c.name for c in fake.calls] == ["start", "start"]
    assert seen[0].tg_id == 500 and seen[0].lang is Lang.ru


async def test_start_always_refreshes_and_passes_referral() -> None:
    fake, state = FakeApiClient(), _state()
    middleware = UserContextMiddleware(fake, _Clock())
    await middleware(_ok, _message("hi"), _data(state))
    await middleware(_ok, _message("/start r_ABC123"), _data(state))
    body = fake.calls[-1].body
    assert body is not None and body.model_dump()["referral_code"] == "ABC123"
    assert body.model_dump()["has_tg_profile_photo"] is True


async def test_banned_user_gets_ban_text_and_no_handler() -> None:
    fake, state = FakeApiClient(), _state()
    middleware = UserContextMiddleware(fake, _Clock())
    await middleware(_ok, _message("hi"), _data(state))
    fake.ban(500, None)
    answered: list[str] = []
    message = _message("/start")

    async def answer(text: str, **_: object) -> None:
        answered.append(text)

    object.__setattr__(message, "answer", answer)
    assert await middleware(_ok, message, _data(state)) is None
    assert answered == ["Твоя анкета заблокирована навсегда."]


async def test_other_api_errors_propagate_to_the_error_router() -> None:
    fake, state = FakeApiClient(), _state()
    fake.fail_next(
        "start",
        __import__("svoi_contracts.errors", fromlist=["ApiError"]).ApiError(
            code="internal", message="boom"
        ),
    )
    with pytest.raises(ApiException):
        await UserContextMiddleware(fake, _Clock())(_ok, _message("hi"), _data(state))


async def test_i18n_uses_user_state_then_telegram_language() -> None:
    i18n = I18nMiddleware()

    async def capture(event: object, data: dict[str, Any]) -> Lang:
        return get_locale()

    assert await i18n(capture, _message("x"), {"event_from_user": USER}) is Lang.ru
    fake = FakeApiClient()
    state = fake.onboard(1, lang=Lang.en)
    user_state = await fake.get_me(state.tg_id)
    assert await i18n(capture, _message("x"), {"user_state": user_state}) is Lang.en


@pytest.mark.parametrize("lang", list(Lang))
def test_command_list_is_complete_in_every_language(lang: Lang) -> None:
    listed = commands(lang)
    assert [c.command for c in listed] == list(COMMANDS)
    assert all(c.description for c in listed)
