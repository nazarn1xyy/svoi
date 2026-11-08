"""K12/S10 acceptance: the admin section answers admins only (ADMIN_TG_IDS, ADR 0001)."""

from harness import BotHarness
from svoi_bot.api_client import FakeApiClient


async def test_admin_gets_the_queues_before_onboarding() -> None:
    harness = BotHarness(FakeApiClient(admin_ids={100}), user_id=100)
    await harness.send_command("admin")
    assert harness.last_text() == "Черги модерації"
    assert harness.buttons()[0] == "Скарги (0)"


async def test_non_admin_gets_no_admin_section() -> None:
    # /admin is an unknown command for others: they see what any message shows them
    harness = BotHarness(FakeApiClient(admin_ids={1}), user_id=100)
    await harness.send_command("admin")
    assert all("Черги" not in text for text in harness.texts())
    assert harness.texts() == ["Choose your language 👇"]
