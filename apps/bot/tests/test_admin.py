"""K12 acceptance: the admin section answers admins only (ADMIN_TG_IDS, ADR 0001)."""

from harness import BotHarness
from svoi_bot.api_client import FakeApiClient


async def test_admin_gets_the_admin_section_before_onboarding() -> None:
    harness = BotHarness(FakeApiClient(admin_ids={100}), user_id=100)
    await harness.send_command("admin")
    assert harness.last_text() == "Адмін-розділ. Черги модерації з'являться тут."


async def test_non_admin_gets_no_answer() -> None:
    harness = BotHarness(FakeApiClient(admin_ids={1}), user_id=100)
    await harness.send_command("admin")
    assert harness.shown() == []
