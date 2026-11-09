"""S10-S14 acceptance: reports, admin, metrics, safety, verification, notify, referral."""

from datetime import UTC, datetime, timedelta

from apihelp import ADMIN_TG, Freeze, Tg, UserFactory, assert_error, city_id, onboard
from sqlalchemy import select, update
from svoi_api.core import time as clock
from svoi_api.core.queue import RecordingQueue
from svoi_api.db.models import (
    Match,
    Media,
    NotificationOutbox,
    Profile,
    ReactionBonus,
    User,
)
from svoi_api.deps import Ctx
from svoi_api.domains.notifications.service import notify_schedule
from svoi_contracts.api.admin import AdminQueueItem, AdminUserOut, MetricsOut
from svoi_contracts.api.feed import FeedItem, FeedResponse
from svoi_contracts.api.referral import ReferralOut
from svoi_contracts.api.safety import CaptchaChallenge
from svoi_contracts.api.verification import GestureOut, VerificationOut
from svoi_contracts.cards import MediaRef
from svoi_contracts.enums import ModerationStatus, OutboxStatus
from svoi_contracts.jobs import NotifyLikes, NotifyModeration


async def _uid(tg: Tg) -> int:
    return int((await tg.ok("GET", "/users/me")).user_id)


async def _people(user: UserFactory, n: int, start: int = 100, **kw: object) -> list[Tg]:
    out = []
    for i in range(n):
        tg = user(start + i)
        await onboard(tg, name=f"Name{'abcdefghij'[i]}", **kw)  # type: ignore[arg-type]
        out.append(tg)
    return out


# ---- S10 --------------------------------------------------------------------------------


async def test_three_reports_hide_profile(user: UserFactory, ctx: Ctx) -> None:
    target, *reporters = await _people(user, 4)
    tid = await _uid(target)
    for r in reporters:
        await r.ok(
            "POST", "/reports", None, body={"target_id": tid, "reason": "spam", "context": "feed"}
        )
    again = await reporters[0].call(
        "POST", "/reports", body={"target_id": tid, "reason": "spam", "context": "feed"}
    )
    assert_error(again, 409, "conflict")
    p = await ctx.session.get(Profile, tid)
    assert p is not None and p.hidden_by_moderation


async def test_one_underage_report_hides(user: UserFactory, ctx: Ctx) -> None:
    target, reporter = await _people(user, 2)
    tid = await _uid(target)
    await reporter.ok(
        "POST", "/reports", None, body={"target_id": tid, "reason": "underage", "context": "feed"}
    )
    p = await ctx.session.get(Profile, tid)
    assert p is not None and p.hidden_by_moderation


async def test_other_reason_needs_text(user: UserFactory) -> None:
    target, reporter = await _people(user, 2)
    r = await reporter.call(
        "POST",
        "/reports",
        body={"target_id": await _uid(target), "reason": "other", "context": "feed"},
    )
    assert_error(r, 422, "validation_error")


async def test_admin_only(user: UserFactory) -> None:
    (a,) = await _people(user, 1)
    assert_error(await a.call("GET", "/admin/queue/stats"), 403, "forbidden")
    assert_error(await a.call("GET", "/admin/metrics"), 403, "forbidden")


async def test_report_queue_and_ban(user: UserFactory, ctx: Ctx, queue: RecordingQueue) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    target, reporter = await _people(user, 2)
    tid = await _uid(target)
    await reporter.ok(
        "POST", "/reports", None, body={"target_id": tid, "reason": "spam", "context": "feed"}
    )
    stats = await admin.ok("GET", "/admin/queue/stats", dict[str, int])
    assert stats["reports"] == 1 and set(stats) == {
        "reports",
        "photos",
        "verifications",
        "custom_tags",
        "texts",
    }
    item = await admin.ok("GET", "/admin/queue", AdminQueueItem, params={"kind": "reports"})
    assert item.target_tg_id == target.tg_id and len(item.reports) == 1
    body = {"kind": "reports", "item_id": item.item_id, "action": "ban_7d"}
    await admin.ok("POST", "/admin/actions", None, body=body)
    assert_error(await admin.call("POST", "/admin/actions", body=body), 409, "conflict")
    assert_error(await target.call("GET", "/feed/next"), 403, "banned")
    assert (await target.ok("GET", "/users/me")).status.value == "banned"
    assert len(queue.of(NotifyModeration)) == 1
    info = await admin.ok("GET", f"/admin/users/{target.tg_id}", AdminUserOut)
    assert info.status.value == "banned" and info.mod_actions
    empty = await admin.call("GET", "/admin/queue", params={"kind": "reports"})
    assert empty.status_code == 200 and empty.json() is None


async def test_ban_expires(user: UserFactory, ctx: Ctx, freeze: Freeze) -> None:
    (a,) = await _people(user, 1)
    await ctx.session.execute(
        update(User)
        .where(User.tg_id == a.tg_id)
        .values(status="banned", banned_until=clock.now() + timedelta(days=7))
    )
    await ctx.session.commit()
    assert_error(await a.call("GET", "/limits"), 403, "banned")
    freeze(clock.now() + timedelta(days=8))
    assert (await a.ok("GET", "/users/me")).status.value == "active"
    await a.ok("GET", "/limits", dict)


async def test_move_to_minor_cuts_adult_links(user: UserFactory, ctx: Ctx) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    a, b = await _people(user, 2)
    item_b = await a.ok("GET", "/feed/next", FeedResponse)
    item_a = await b.ok("GET", "/feed/next", FeedResponse)
    assert isinstance(item_b, FeedItem) and isinstance(item_a, FeedItem)
    await a.ok("POST", "/reactions", dict, body={"target_id": item_b.card.user_id, "type": "like"})
    await b.ok("POST", "/reactions", dict, body={"target_id": item_a.card.user_id, "type": "like"})
    await b.ok(
        "POST",
        "/reports",
        None,
        body={
            "target_id": item_b.card.user_id and await _uid(a),
            "reason": "underage",
            "context": "contact",
        },
    )
    item = await admin.ok("GET", "/admin/queue", AdminQueueItem, params={"kind": "reports"})
    await admin.ok(
        "POST",
        "/admin/actions",
        None,
        body={"kind": "reports", "item_id": item.item_id, "action": "move_to_minor_pool"},
    )
    p = await ctx.session.get(Profile, await _uid(a))
    assert p is not None and p.age == 17 and p.pool is not None and p.pool.value == "minor"
    match = await ctx.session.scalar(select(Match))
    assert match is not None and match.removed_by_id is not None


async def test_photo_review_approve(user: UserFactory, ctx: Ctx) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    (a,) = await _people(user, 1)
    ref = await a.ok(
        "POST",
        "/profile/media",
        MediaRef,
        body={"kind": "video", "file_id": "v1", "file_unique_id": "v1"},
    )
    item = await admin.ok("GET", "/admin/queue", AdminQueueItem, params={"kind": "photos"})
    assert item.media is not None and item.media.id == ref.id
    await admin.ok(
        "POST",
        "/admin/actions",
        None,
        body={"kind": "photos", "item_id": ref.id, "action": "approve"},
    )
    media = await ctx.session.get(Media, ref.id)
    assert media is not None and media.moderation_status is ModerationStatus.approved


async def test_custom_tag_approval_adds_it(user: UserFactory) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    (a,) = await _people(user, 1)
    await a.ok("POST", "/catalog/interests/custom", dict, body={"title": "лонгборд у парку"})
    item = await admin.ok("GET", "/admin/queue", AdminQueueItem, params={"kind": "custom_tags"})
    assert item.custom_interest_title == "лонгборд у парку"
    await admin.ok(
        "POST",
        "/admin/actions",
        None,
        body={"kind": "custom_tags", "item_id": item.item_id, "action": "approve"},
    )
    card = await a.ok("GET", "/profile/me/card", dict)
    assert any(i["title"] == "лонгборд у парку" for i in card["interests"])


async def test_metrics(user: UserFactory) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    await _people(user, 2)
    m = await admin.ok("GET", "/admin/metrics", MetricsOut, params={"days": 7})
    assert m.starts == 3 and m.onboarding_completed == 3 and m.onboarding_rate == 1.0
    assert_error(
        await admin.call("GET", "/admin/metrics", params={"days": 0}), 422, "validation_error"
    )


# ---- S11 --------------------------------------------------------------------------------


async def test_underage_prompt_hides_for_review(user: UserFactory, ctx: Ctx) -> None:
    (a,) = await _people(user, 1)
    state = await a.ok(
        "PUT",
        "/profile/prompts",
        body={"answers": [{"prompt_id": 1, "text": "мені 17, шукаю друзів"}]},
    )
    assert state.status.value == "active"
    p = await ctx.session.get(Profile, state.user_id)
    assert p is not None and p.hidden_by_moderation


async def test_spam_to_five_people_shadow_bans(user: UserFactory, ctx: Ctx) -> None:
    spammer, *targets = await _people(user, 6)
    for _ in targets:
        item = await spammer.ok("GET", "/feed/next", FeedResponse)
        assert isinstance(item, FeedItem)
        await spammer.ok(
            "POST",
            "/reactions",
            dict,
            body={
                "target_id": item.card.user_id,
                "type": "like_msg",
                "message": "Привіт, як справи?",
            },
        )
    me = await ctx.session.scalar(select(User).where(User.tg_id == spammer.tg_id))
    assert me is not None and me.shadow_banned


async def test_captcha_flow(user: UserFactory, ctx: Ctx) -> None:
    (a,) = await _people(user, 1)
    assert_error(await a.call("POST", "/users/me/captcha"), 409, "conflict")
    await ctx.session.execute(update(User).where(User.tg_id == a.tg_id).values(risk_score=60))
    await ctx.session.commit()
    assert (await a.ok("GET", "/users/me")).captcha_required
    c = await a.ok("POST", "/users/me/captcha", CaptchaChallenge)
    assert len(set(c.options)) == 6 and c.target_emoji in c.options
    wrong = next(o for o in c.options if o != c.target_emoji)
    assert (
        await a.ok(
            "POST",
            "/users/me/captcha/verify",
            body={"challenge_id": c.challenge_id, "answer": wrong},
        )
    ).captcha_required
    assert_error(
        await a.call(
            "POST",
            "/users/me/captcha/verify",
            body={"challenge_id": c.challenge_id, "answer": wrong},
        ),
        404,
        "not_found",
    )
    c = await a.ok("POST", "/users/me/captcha", CaptchaChallenge)
    ok = await a.ok(
        "POST",
        "/users/me/captcha/verify",
        body={"challenge_id": c.challenge_id, "answer": c.target_emoji},
    )
    assert not ok.captcha_required


# ---- S12 --------------------------------------------------------------------------------


async def test_verification_cycle(user: UserFactory, ctx: Ctx) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    (a,) = await _people(user, 1)
    err = assert_error(await a.call("POST", "/verification/start"), 409, "conflict")
    assert err.details == {"reason": "no_photo"}
    ref = await a.ok(
        "POST",
        "/profile/media",
        MediaRef,
        body={"kind": "photo", "file_id": "p", "file_unique_id": "p"},
    )
    await ctx.session.execute(
        update(Media).where(Media.id == ref.id).values(moderation_status="approved")
    )
    await ctx.session.commit()
    assert (await a.ok("GET", "/verification/status", VerificationOut)).status is None
    g = await a.ok("POST", "/verification/start", GestureOut)
    await a.ok(
        "POST",
        "/verification/submit",
        VerificationOut,
        body={"verification_id": g.verification_id, "video_note_file_id": "note"},
    )
    err = assert_error(await a.call("POST", "/verification/start"), 409, "conflict")
    assert err.details == {"reason": "pending"}
    item = await admin.ok("GET", "/admin/queue", AdminQueueItem, params={"kind": "verifications"})
    assert item.verification_file_id == "note" and item.verification_gesture == g.gesture
    await admin.ok(
        "POST",
        "/admin/actions",
        None,
        body={"kind": "verifications", "item_id": g.verification_id, "action": "approve"},
    )
    assert (
        await a.ok("GET", "/verification/status", VerificationOut)
    ).status is ModerationStatus.approved
    err = assert_error(await a.call("POST", "/verification/start"), 409, "conflict")
    assert err.details == {"reason": "already_verified"}


# ---- S13 --------------------------------------------------------------------------------


async def test_quiet_hours_delay_likes(
    user: UserFactory, ctx: Ctx, freeze: Freeze, queue: RecordingQueue
) -> None:
    a, _b = await _people(user, 2)
    item = await a.ok("GET", "/feed/next", FeedResponse)
    assert isinstance(item, FeedItem)
    freeze(datetime(2026, 11, 9, 21, 30, tzinfo=UTC))  # 23:30 in Kyiv
    await a.ok("POST", "/reactions", dict, body={"target_id": item.card.user_id, "type": "like"})
    row = await ctx.session.scalar(select(NotificationOutbox))
    assert row is not None and row.status is OutboxStatus.pending
    assert row.scheduled_for == datetime(2026, 11, 10, 6, 0, tzinfo=UTC)  # 08:00 Kyiv
    assert queue.of(NotifyLikes) == []
    freeze(datetime(2026, 11, 10, 6, 1, tzinfo=UTC))
    assert await notify_schedule(ctx) == 1
    assert await notify_schedule(ctx) == 0
    assert len(queue.of(NotifyLikes)) == 1


async def test_bot_blocked_and_sent(user: UserFactory, ctx: Ctx) -> None:
    a, b = await _people(user, 2)
    item = await a.ok("GET", "/feed/next", FeedResponse)
    assert isinstance(item, FeedItem)
    await a.ok("POST", "/reactions", dict, body={"target_id": item.card.user_id, "type": "like"})
    row = await ctx.session.scalar(select(NotificationOutbox))
    assert row is not None
    r = await a.http.post(
        f"/v1/internal/notifications/{row.dedupe_key}/sent",
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 204
    r = await a.http.post(
        f"/v1/internal/users/{b.tg_id}/bot-blocked", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 204
    r = await a.http.post(
        "/v1/internal/users/999/bot-blocked", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 404
    left = await ctx.session.scalar(
        select(NotificationOutbox).where(NotificationOutbox.status == OutboxStatus.pending)
    )
    assert left is None


# ---- S14 --------------------------------------------------------------------------------


async def test_referral_bonus_once(user: UserFactory, ctx: Ctx) -> None:
    (host,) = await _people(user, 1)
    code = (await host.ok("GET", "/referral", ReferralOut)).code
    guest = user(500)
    await onboard(guest, name="Guest", referral_code=code)
    info = await host.ok("GET", "/referral", ReferralOut)
    assert info.invited_count == 1 and info.bonus_per_invite == 20
    # fill in again after reset and complete once more: still one bonus each
    await guest.ok("POST", "/profile/reset")
    await guest.ok("PUT", "/profile/age", body={"age": 19})
    for path, body in (
        ("/profile/name", {"name": "Guest"}),
        ("/profile/gender", {"gender": "female"}),
    ):
        await guest.ok("PUT", path, body=body)
    card = await guest.ok("GET", "/profile/me/card", dict)
    await guest.ok("PUT", "/profile/city", body={"city_id": await city_id(guest, "Вінниця")})
    await guest.ok("PUT", "/profile/goals", body={"codes": card["goals"]})
    await guest.ok(
        "PUT", "/profile/interests", body={"interest_ids": [i["id"] for i in card["interests"]]}
    )
    for step in ("clarify", "institution", "height", "prompts", "media"):
        await guest.ok("POST", "/onboarding/skip", body={"step": step})
    await guest.ok("POST", "/onboarding/complete")
    bonuses = list(await ctx.session.scalars(select(ReactionBonus)))
    assert len(bonuses) == 2
    limits = await host.ok("GET", "/limits", dict)
    assert limits["reactions_left"] == 120


async def test_metrics_totals(user: UserFactory) -> None:
    admin = user(ADMIN_TG)
    await onboard(admin, name="Admin")
    a, _b = await _people(user, 2)
    item = await a.ok("GET", "/feed/next", FeedResponse)
    assert isinstance(item, FeedItem)
    await a.ok(
        "POST",
        "/reactions",
        dict,
        body={"target_id": item.card.user_id, "type": "like_msg", "message": "Привіт"},
    )
    m = await admin.ok("GET", "/admin/metrics", MetricsOut)
    assert m.users_total == 3 and m.users_by_status["active"] == 3
    assert m.users_by_pool["adult"] == 3 and m.users_by_pool["minor"] == 0
    assert m.active_today == 3 and m.active_30d == 3
    assert m.views_total >= 1 and m.likes_with_message == 1 and m.likes_pending == 1
    assert m.likes_all_time == 1 and m.matches_all_time == 0
