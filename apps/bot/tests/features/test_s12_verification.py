"""S12-FE acceptance (FRONTEND.md S12): verification by a round video."""

from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_contracts.api.profile import MediaIn
from svoi_contracts.enums import MediaKind, ModerationStatus

TG = 100


async def _with_photo() -> BotHarness:
    api = FakeApiClient()
    api.onboard(TG)
    await api.add_media(TG, MediaIn(kind=MediaKind.photo, file_id="p", file_unique_id="p"))
    api.approve_media(TG)
    return BotHarness(api, user_id=TG)


async def test_full_path() -> None:
    harness = await _with_photo()
    await harness.send_command("verify")
    assert harness.last_text().startswith("Верифікація підтверджує, що ти справжня людина.")
    await harness.send_video_note(6, "note-1")
    assert harness.last_text() == "Надіслано на перевірку. Повідомимо результат."
    assert harness.api.verifications[-1].file_id == "note-1"
    assert harness.api.verifications[-1].status is ModerationStatus.pending


async def test_only_a_round_video_is_accepted() -> None:
    harness = await _with_photo()
    await harness.send_command("verify")
    await harness.send_photo()
    assert harness.last_text() == "Потрібен саме відеокружок."


async def test_three_conflicts() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("verify")
    assert harness.last_text() == "Спочатку додай фото, щоб модератор міг порівняти."
    await api.add_media(TG, MediaIn(kind=MediaKind.photo, file_id="p", file_unique_id="p"))
    api.approve_media(TG)
    await harness.send_command("verify")
    await harness.send_video_note()
    await harness.send_command("verify")
    assert harness.last_text() == "Перевірка ще триває."
    api.verifications.clear()
    api.user(TG).verified = True
    await harness.send_command("verify")
    assert harness.last_text() == "Анкета вже верифікована ✅"


async def test_profile_button() -> None:
    harness = await _with_photo()
    await harness.send_text("👤 Моя анкета")
    await harness.tap("✅ Верифікація")
    assert harness.last_text().startswith("Верифікація підтверджує")
