"""S10/S10b-FE acceptance (FRONTEND.md S10): reports, blocks, admin queues, metrics."""

from datetime import UTC, datetime
from typing import Any

import pytest
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_contracts.api.admin import AdminActionIn, AdminQueueItem, MetricsOut, ReportBrief
from svoi_contracts.enums import AdminAction, AdminQueueKind, ReportContext, ReportReason

TG, ADMIN = 100, 1
NOW = datetime(2026, 11, 8, tzinfo=UTC)


async def _feed() -> BotHarness:
    api = FakeApiClient(admin_ids={ADMIN})
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    return harness


def _reports(harness: BotHarness) -> list[Any]:
    return [c.body for c in harness.api.calls if c.name == "report"]


@pytest.mark.parametrize("reason", [r for r in ReportReason if r is not ReportReason.other])
async def test_report_with_each_reason_then_next_card(reason: ReportReason) -> None:
    from svoi_bot.ui.format import reason_label  # noqa: PLC0415

    harness = await _feed()
    target = harness.api.user(TG).current
    await harness.tap("⚠️ Поскаржитися")
    assert harness.last_text() == "Що не так з анкетою?"
    await harness.tap(reason_label(reason))
    (body,) = _reports(harness)
    assert (body.target_id, body.reason, body.context) == (target, reason, ReportContext.feed)
    assert "Дякуємо, ми перевіримо. Цю анкету ти більше не побачиш." in harness.texts()
    assert harness.last_text().startswith("<b>")


async def test_other_needs_a_text() -> None:
    harness = await _feed()
    await harness.tap("⚠️ Поскаржитися")
    await harness.tap("Інше")
    assert harness.last_text() == "Опиши коротко, що не так (до 500 символів)."
    await harness.send_text("   ")
    assert _reports(harness) == []
    await harness.send_text("пише всім одне й те саме")
    (body,) = _reports(harness)
    assert body.text == "пише всім одне й те саме"


async def test_block_and_repeated_report() -> None:
    harness = await _feed()
    await harness.tap("⚠️ Поскаржитися")
    await harness.tap("🚫 Заблокувати")
    assert "Заблоковано. Ви більше не побачите одне одного." in harness.texts()
    target = harness.api.user(TG).shown[0]
    harness.api.reports.add((harness.api.user(TG).id, target))
    harness.api.user(TG).current = None
    from svoi_bot.ui.callbacks import ReportCb  # noqa: PLC0415

    await harness.press(ReportCb(target_id=target, reason="spam", context="feed"))
    assert harness.last_text() == "Ти вже скаржився на цю анкету."


def _item(api: FakeApiClient, item_id: int, kind: AdminQueueKind) -> AdminQueueItem:
    demo = api.user(api.demo_tg_ids()[0])
    card = api._card(demo, demo, "admin")
    return AdminQueueItem(
        item_id=item_id,
        kind=kind,
        target_user_id=demo.id,
        target_tg_id=demo.tg_id,
        target_card=card,
        reports=[ReportBrief(reason=ReportReason.spam, text="реклама", created_at=NOW)],
        media=None,
        verification_file_id=None,
        verification_gesture=None,
        custom_interest_title=None,
        flagged_text=None,
        created_at=NOW,
    )


async def test_admin_action_is_one_post_and_moves_to_the_next_item() -> None:
    api = FakeApiClient(admin_ids={ADMIN})
    api.add_queue_item(_item(api, 1, AdminQueueKind.reports))
    api.add_queue_item(_item(api, 2, AdminQueueKind.reports))
    harness = BotHarness(api, user_id=ADMIN)
    await harness.send_command("admin")
    await harness.tap("Скарги (2)")
    assert "Спам або реклама · 08.11.2026 · реклама" in harness.texts()
    await harness.tap("✅ Все гаразд")
    assert api.admin_actions == [
        AdminActionIn(kind=AdminQueueKind.reports, item_id=1, action=AdminAction.ok)
    ]
    await harness.tap("⏳ Бан 7 днів")
    assert harness.last_text() == "Точно? ⏳ Бан 7 днів"
    assert len(api.admin_actions) == 1
    await harness.tap("Так")
    assert [a.action for a in api.admin_actions] == [AdminAction.ok, AdminAction.ban_7d]
    assert "Черга порожня 🎉" in harness.texts()


async def test_user_lookup_and_metrics() -> None:
    api = FakeApiClient(admin_ids={ADMIN})
    api.onboard(TG)
    harness = BotHarness(api, user_id=ADMIN)
    await harness.send_command("user", str(TG))
    assert f"tg {TG}" in harness.last_text()
    await harness.send_command("metrics")
    assert harness.last_text().startswith("Метрики за")


async def test_metrics_render_survives_zero_division() -> None:
    from svoi_bot.admin.features.queue.views import metrics  # noqa: PLC0415
    from svoi_bot.ui.i18n import set_locale  # noqa: PLC0415
    from svoi_contracts.enums import Lang  # noqa: PLC0415

    set_locale(Lang.uk)
    text = metrics(
        MetricsOut(
            period_from=NOW.date(),
            period_to=NOW.date(),
            starts=0,
            onboarding_completed=0,
            onboarding_rate=0.0,
            likes_total=0,
            matches_total=0,
            mutual_rate=0.0,
            d1_retention=0.0,
            d7_retention=0.0,
            reports_per_1000_views=0.0,
            confirmed_reports_rate=0.0,
        )
    )
    assert "старти 0, завершили анкету 0%" in text
