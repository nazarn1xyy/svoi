"""S14-FE acceptance (FRONTEND.md S14): invite a friend."""

from urllib.parse import parse_qs, urlparse

from aiogram.types import InlineKeyboardMarkup
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient

TG = 100


async def test_screen_from_settings_with_link_and_share_button() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("⚙️ Налаштування")
    await harness.tap("🎁 Запросити друга")
    text = harness.last_text()
    assert "+20 реакцій" in text
    assert "https://t.me/svoi_test_bot?start=r_R100" in text
    assert "Запрошено: 0" in text
    markup = harness.last_markup()
    assert isinstance(markup, InlineKeyboardMarkup)
    share = markup.inline_keyboard[0][0]
    assert share.text == "📤 Поділитися"
    query = parse_qs(urlparse(share.url or "").query)
    assert query["url"] == ["https://t.me/svoi_test_bot?start=r_R100"]


async def test_screen_from_the_daily_limit() -> None:
    api = FakeApiClient()
    api.onboard(TG).reactions_left = 0
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    await harness.tap("🎁 Запросити друга")
    assert "Твоє посилання:" in harness.last_text()


async def test_invited_friend_counts_after_onboarding() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    friend = BotHarness(api, user_id=200)
    await friend.send_command("start", "r_R100")
    start = next(c for c in api.calls if c.name == "start" and c.tg_id == 200)
    assert start.body is not None and start.body.model_dump()["referral_code"] == "R100"
    assert api.user(200).referred_by == api.user(TG).id
