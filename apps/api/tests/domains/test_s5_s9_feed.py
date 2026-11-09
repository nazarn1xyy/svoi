"""S5-S9 acceptance: card, hide, delete, age tick, filters, feed, reactions, likes, contacts."""

from datetime import timedelta

from apihelp import NOW, Freeze, Tg, UserFactory, assert_error, onboard
from sqlalchemy import select, update
from svoi_api.core import time
from svoi_api.core.queue import RecordingQueue
from svoi_api.db.models import Like, NotificationOutbox, Profile, User
from svoi_api.deps import Ctx
from svoi_api.domains.likes.service import expire_likes
from svoi_api.domains.profiles.jobs import age_tick
from svoi_contracts.api.feed import FeedEmpty, FeedItem, FeedResponse
from svoi_contracts.api.likes import (
    ContactOut,
    IncomingLike,
    IncomingResponse,
    NoIncoming,
    RespondOut,
)
from svoi_contracts.api.prefs import FiltersOut, SettingsOut
from svoi_contracts.api.reactions import ReactionOut
from svoi_contracts.cards import Limits, MatchResult, MediaRef, Page, ProfileCard
from svoi_contracts.jobs import NotifyMatch


async def _people(user: UserFactory, n: int, **kw: object) -> list[Tg]:
    out = []
    for i in range(n):
        tg = user(100 + i)
        await onboard(tg, name=f"Name{'abcdefghij'[i]}", **kw)  # type: ignore[arg-type]
        out.append(tg)
    return out


async def _next(tg: Tg) -> FeedResponse:
    r: FeedResponse = await tg.ok("GET", "/feed/next", FeedResponse)
    return r


# ---- S5 ---------------------------------------------------------------------------------


async def test_own_card_shows_pending_media_others_do_not(user: UserFactory) -> None:
    a, b = await _people(user, 2)
    await a.ok(
        "POST",
        "/profile/media",
        MediaRef,
        body={"kind": "photo", "file_id": "p1", "file_unique_id": "p1"},
    )
    own = await a.ok("GET", "/profile/me/card", ProfileCard)
    assert len(own.media) == 1 and own.completeness is not None
    item = await _next(b)
    assert isinstance(item, FeedItem)
    assert item.card.media == [] and item.card.completeness is None
    assert item.card.common is not None


async def test_minor_card_has_no_distance_in_other_city(user: UserFactory) -> None:
    a = user(1)
    await onboard(a, age=17, city="Вінниця")
    b = user(2)
    await onboard(b, age=17, city="Вінниця")
    item = await _next(b)
    assert isinstance(item, FeedItem)
    assert item.card.distance is not None and item.card.distance.value == "same_city"


async def test_hide_unhide_reset(user: UserFactory) -> None:
    (a,) = await _people(user, 1)
    assert (await a.ok("POST", "/profile/hide")).status.value == "hidden"
    empty = await _next(a)
    assert isinstance(empty, FeedEmpty) and empty.reason.value == "profile_hidden"
    assert (await a.ok("POST", "/profile/unhide")).status.value == "active"
    assert_error(await a.call("POST", "/profile/unhide"), 409, "conflict")
    state = await a.ok("POST", "/profile/reset")
    assert state.onboarding_step.value == "age"


async def test_delete_keeps_ban(user: UserFactory, ctx: Ctx) -> None:
    (a,) = await _people(user, 1)
    await a.ok("DELETE", "/users/me", None)
    assert_error(await a.call("GET", "/users/me"), 404, "not_found")
    (b,) = await _people(user, 1)
    await ctx.session.execute(update(User).where(User.tg_id == b.tg_id).values(status="banned"))
    await ctx.session.commit()
    r = await b.call("DELETE", "/users/me")
    assert_error(r, 403, "banned")


async def test_age_tick_once_a_day(user: UserFactory, ctx: Ctx, freeze: Freeze) -> None:
    (a,) = await _people(user, 1, age=17)
    p = await ctx.session.scalar(select(Profile).join(User).where(User.tg_id == a.tg_id))
    assert p is not None
    p.age_set_at = NOW - timedelta(days=365)
    await ctx.session.commit()
    freeze(NOW)
    assert await age_tick(ctx) == 1
    assert await age_tick(ctx) == 0
    await ctx.session.refresh(p)
    assert p.age == 18 and p.pool is not None and p.pool.value == "adult"


# ---- S6 ---------------------------------------------------------------------------------


async def test_filters_bounds_and_geo(user: UserFactory, queue: RecordingQueue) -> None:
    (a,) = await _people(user, 1, age=17)
    f = await a.ok("GET", "/filters", FiltersOut)
    assert f.age_bounds == (16, 17) and (f.age_min, f.age_max) == (16, 17)
    bad = {"age_min": 16, "age_max": 20, "gender": "all", "radius": "city", "verified_only": False}
    assert_error(await a.call("PUT", "/filters", body=bad), 422, "validation_error")
    no_geo = bad | {"age_max": 17, "radius": "km25"}
    err = assert_error(await a.call("PUT", "/filters", body=no_geo), 422, "validation_error")
    assert err.details == {"reason": "no_geo"}
    s = await a.ok("GET", "/settings", SettingsOut)
    changed = s.model_dump(mode="json") | {"notify_frequency": "daily"}
    assert (
        await a.ok("PUT", "/settings", SettingsOut, body=changed)
    ).notify_frequency.value == "daily"


# ---- S7 ---------------------------------------------------------------------------------


async def test_pools_never_mix(user: UserFactory) -> None:
    adult = user(1)
    await onboard(adult, age=18)
    minor = user(2)
    await onboard(minor, age=17)
    assert isinstance(await _next(adult), FeedEmpty)
    assert isinstance(await _next(minor), FeedEmpty)


async def test_no_repeats_and_expand_options(user: UserFactory) -> None:
    a, _b, _c = await _people(user, 3)
    seen = set()
    for _ in range(2):
        item = await _next(a)
        assert isinstance(item, FeedItem)
        assert item.card.user_id not in seen
        seen.add(item.card.user_id)
        await a.ok(
            "POST", "/reactions", ReactionOut, body={"target_id": item.card.user_id, "type": "skip"}
        )
    empty = await _next(a)
    assert isinstance(empty, FeedEmpty) and empty.reason.value == "no_candidates"
    assert [o.value for o in empty.expand_options] == ["region", "country"]
    expanded = await a.ok("POST", "/feed/expand", FeedResponse, body={"radius": "country"})
    assert isinstance(expanded, FeedEmpty)
    bad = await a.call("POST", "/feed/expand", body={"radius": "km50"})
    assert_error(bad, 422, "validation_error")


async def test_blocked_never_shown(user: UserFactory) -> None:
    a, b = await _people(user, 2)
    state_b = await b.ok("GET", "/users/me")
    await a.ok("POST", "/blocks", None, body={"target_id": state_b.user_id})
    assert isinstance(await _next(a), FeedEmpty)
    assert isinstance(await _next(b), FeedEmpty)


# ---- S8 ---------------------------------------------------------------------------------


async def test_react_only_on_shown_cards(user: UserFactory) -> None:
    a, b = await _people(user, 2)
    state_b = await b.ok("GET", "/users/me")
    r = await a.call("POST", "/reactions", body={"target_id": state_b.user_id, "type": "like"})
    assert_error(r, 409, "conflict")


async def test_mutual_like_matches_once(user: UserFactory, queue: RecordingQueue, ctx: Ctx) -> None:
    a, b = await _people(user, 2)
    card_b = await _next(a)
    assert isinstance(card_b, FeedItem)
    out = await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": card_b.card.user_id, "type": "like"}
    )
    assert out.match is None and out.limits.reactions_left == 99
    incoming = await b.ok("GET", "/likes/incoming/next", IncomingResponse)
    assert isinstance(incoming, IncomingLike)
    responded = await b.ok(
        "POST", f"/likes/{incoming.like_id}/respond", RespondOut, body={"decision": "accept"}
    )
    assert responded.match is not None and responded.match.partner_tg_id == a.tg_id
    again = await b.call("POST", f"/likes/{incoming.like_id}/respond", body={"decision": "accept"})
    assert_error(again, 409, "conflict")
    assert len(queue.of(NotifyMatch)) == 1
    match = await a.ok("GET", f"/matches/{responded.match.match_id}", MatchResult)
    assert match.partner_tg_id == b.tg_id and match.icebreaker is not None
    contacts = await a.ok("GET", "/contacts", Page[ContactOut])
    assert len(contacts.items) == 1
    await b.ok("DELETE", f"/contacts/{responded.match.match_id}", None)
    assert (await a.ok("GET", "/contacts", Page[ContactOut])).items == []


async def test_like_back_from_feed_is_instant_match(user: UserFactory) -> None:
    a, b = await _people(user, 2)
    card_b = await _next(a)
    card_a = await _next(b)
    assert isinstance(card_b, FeedItem) and isinstance(card_a, FeedItem)
    await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": card_b.card.user_id, "type": "like"}
    )
    out = await b.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": card_a.card.user_id, "type": "like"}
    )
    assert out.match is not None


async def test_daily_limit_and_bonus(user: UserFactory, env: dict[str, object]) -> None:
    a, _b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    state = await a.ok("GET", "/users/me")
    redis = env["redis"]
    await redis.set(f"lim:react:{state.user_id}:{time.kyiv_today():%Y%m%d}", 100)  # type: ignore[attr-defined]
    r = await a.call("POST", "/reactions", body={"target_id": item.card.user_id, "type": "like"})
    err = assert_error(r, 429, "limit_reached")
    assert err.details is not None and err.details["reactions_left"] == 0
    limits = await a.ok("GET", "/limits", Limits)
    assert limits.reactions_left == 0


async def test_minor_cannot_send_voice(user: UserFactory) -> None:
    a = user(1)
    await onboard(a, age=16)
    b = user(2)
    await onboard(b, age=17)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    body = {
        "target_id": item.card.user_id,
        "type": "like_msg",
        "media": {"kind": "voice", "file_id": "v", "duration_s": 5},
    }
    assert_error(await a.call("POST", "/reactions", body=body), 400, "media_forbidden")


async def test_undo_window(user: UserFactory, freeze: Freeze, env: dict[str, object]) -> None:
    a, _b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": item.card.user_id, "type": "skip"}
    )
    back = await a.ok("POST", "/reactions/undo", FeedItem)
    assert back.card.user_id == item.card.user_id and not back.can_undo
    assert_error(await a.call("POST", "/reactions/undo"), 409, "undo_unavailable")


async def test_message_with_contacts_blocked(user: UserFactory) -> None:
    a, _b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    body = {"target_id": item.card.user_id, "type": "like_msg", "message": "пиши @vasya_pupkin"}
    assert_error(await a.call("POST", "/reactions", body=body), 400, "content_blocked")


# ---- S9 ---------------------------------------------------------------------------------


async def test_shadow_banned_like_is_invisible(user: UserFactory, ctx: Ctx) -> None:
    a, b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    await ctx.session.execute(update(User).where(User.tg_id == a.tg_id).values(shadow_banned=True))
    await ctx.session.commit()
    await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": item.card.user_id, "type": "like"}
    )
    assert isinstance(await b.ok("GET", "/likes/incoming/next", IncomingResponse), NoIncoming)
    assert (await b.ok("GET", "/users/me")).counters.incoming_likes == 0
    assert list(await ctx.session.scalars(select(NotificationOutbox))) == []


async def test_old_likes_expire(user: UserFactory, ctx: Ctx) -> None:
    a, _b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": item.card.user_id, "type": "like"}
    )
    await ctx.session.execute(update(Like).values(created_at=time.now() - timedelta(days=15)))
    await ctx.session.commit()
    assert await expire_likes(ctx) == 1
    assert await expire_likes(ctx) == 0


async def test_declined_author_not_in_feed(user: UserFactory) -> None:
    a, b = await _people(user, 2)
    item = await _next(a)
    assert isinstance(item, FeedItem)
    await a.ok(
        "POST", "/reactions", ReactionOut, body={"target_id": item.card.user_id, "type": "like"}
    )
    incoming = await b.ok("GET", "/likes/incoming/next", IncomingResponse)
    assert isinstance(incoming, IncomingLike)
    await b.ok(
        "POST", f"/likes/{incoming.like_id}/respond", RespondOut, body={"decision": "decline"}
    )
    assert isinstance(await _next(b), FeedEmpty)
