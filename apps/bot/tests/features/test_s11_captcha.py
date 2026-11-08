"""S11-FE acceptance (FRONTEND.md S11): captcha and content-block texts."""

import pytest
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_bot.features.feed.states import FeedSG
from svoi_bot.middlewares.user_context import CACHE_TTL_S
from svoi_contracts.enums import ContentBlockReason
from svoi_contracts.errors import ApiError, ErrorCode

TG = 100


async def _in_feed_then_flagged() -> BotHarness:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    api.require_captcha(TG)
    harness.clock.tick(CACHE_TTL_S + 1)
    return harness


def _target(harness: BotHarness) -> str:
    text = next(t for t in reversed(harness.texts()) if "натисни на" in t)
    return text.rsplit(" ", 1)[-1]


async def test_flagged_user_solves_and_returns_to_the_same_state() -> None:
    harness = await _in_feed_then_flagged()
    await harness.send_text("❤️")
    assert "Перевірка, що ти не бот: натисни на" in harness.last_text()
    assert len(harness.buttons()) == 6
    await harness.tap(_target(harness))
    assert harness.last_text() == "Дякую! Продовжуємо 👌"
    assert await harness.state() == FeedSG.viewing.state
    assert harness.api.user(TG).captcha_required is False


async def test_wrong_answer_gives_a_new_captcha() -> None:
    harness = await _in_feed_then_flagged()
    await harness.send_text("❤️")
    first = _target(harness)
    wrong = next(b for b in harness.buttons() if b != first)
    await harness.tap(wrong)
    assert harness.last_text().startswith("Не вгадав, спробуй ще")
    await harness.tap(_target(harness))
    assert harness.api.user(TG).captcha_required is False


async def test_expired_captcha_is_replaced() -> None:
    harness = await _in_feed_then_flagged()
    await harness.send_text("❤️")
    harness.api.expire_captchas()
    await harness.tap(_target(harness))
    assert "натисни на" in harness.last_text()
    await harness.tap(_target(harness))
    assert harness.last_text() == "Дякую! Продовжуємо 👌"


async def test_unflagged_users_never_see_a_captcha() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    await harness.send_text("❤️")
    assert all("натисни на" not in t for t in harness.texts())


async def test_captcha_required_error_on_reaction_opens_the_captcha() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    api.require_captcha(TG)
    await harness.send_text("❤️")  # state cached: the API answers captcha_required
    assert any("натисни на" in t for t in harness.texts())


@pytest.mark.parametrize("reason", list(ContentBlockReason))
async def test_each_content_block_reason_has_its_text(reason: ContentBlockReason) -> None:
    from svoi_bot.ui.errors import render_api_error  # noqa: PLC0415

    err = ApiError(
        code=ErrorCode.content_blocked,
        message="m",
        details={"field": "name", "reason": reason.value},
    )
    texts = {
        r: render_api_error(
            ApiError(
                code=ErrorCode.content_blocked,
                message="m",
                details={"field": "name", "reason": r.value},
            )
        )
        for r in ContentBlockReason
    }
    assert len(set(texts.values())) == len(ContentBlockReason)
    assert render_api_error(err) == texts[reason]
