"""Feed: hard filters, scoring, batches, views, expand (S7)."""

import random
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from geoalchemy2.functions import ST_Distance, ST_DWithin
from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from svoi_contracts.api.feed import FeedEmpty, FeedItem, FeedResponse
from svoi_contracts.constants import (
    FEED_REFILL_AT,
    INACTIVE_CUTOFF_DAYS,
    NEWBIE_BOOST_HOURS,
    SKIP_REPEAT_DAYS,
)
from svoi_contracts.enums import (
    FeedEmptyReason,
    Gender,
    GenderFilter,
    GoalCode,
    LikeStatus,
    MediaKind,
    ModerationStatus,
    RadiusMode,
    RebuildReason,
    ReportStatus,
    UserStatus,
    ViewAction,
)
from svoi_contracts.errors import ErrorCode
from svoi_contracts.jobs import RebuildFeed

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.core.redis import aw
from svoi_api.db.models import (
    Block,
    City,
    Filters,
    Institution,
    Interest,
    Like,
    Match,
    Media,
    Profile,
    ProfileGoal,
    ProfileInterest,
    ProfilePrompt,
    Report,
    User,
    View,
)
from svoi_api.deps import Ctx
from svoi_api.domains.matching import rules

CANDIDATES_MAX = 500
BATCH_TTL = 6 * 3600
RESHOW_AFTER = timedelta(minutes=30)
REFERRAL_BOOST_HOURS = 48
TWO_DAYS = 48 * 3600


def _batch_key(user_id: int) -> str:
    return f"feed:batch:{user_id}"


def _seen_key(user_id: int) -> str:
    return f"feed:seen:{user_id}"


# ---- stage 1: hard filters --------------------------------------------------------------


def _accepts(wanted: GenderFilter, gender: ColumnElement[Any]) -> ColumnElement[bool]:
    """The viewer's filter accepts the candidate's gender; hidden passes only `all`."""
    if wanted is GenderFilter.all:
        return true()
    return gender == (Gender.male if wanted is GenderFilter.male else Gender.female)


def _accepted_by(wanted: ColumnElement[Any], gender: Gender | None) -> ColumnElement[bool]:
    """The candidate's filter accepts the viewer's gender."""
    if gender in (Gender.male, Gender.female):
        allowed = GenderFilter.male if gender is Gender.male else GenderFilter.female
        return or_(wanted == GenderFilter.all, wanted == allowed)
    return wanted == GenderFilter.all


async def _candidates_query(
    ctx: Ctx,
    viewer: User,
    *,
    only: Sequence[int] | None = None,
    ignore_views: bool = False,
    repeat_skips: bool = False,
) -> Select[Any] | None:
    """SQL of BACKEND S7 stage 1; None when the viewer cannot have a feed."""
    vp = await ctx.session.get(Profile, viewer.id)
    vf = await ctx.session.get(Filters, viewer.id)
    if vp is None or vf is None or vp.pool is None or vp.age is None or vp.city_id is None:
        return None
    t = aliased(Profile, name="t")
    tu = aliased(User, name="tu")
    tf = aliased(Filters, name="tf")
    vid = viewer.id
    now = time.now()
    q = (
        select(t.user_id)
        .join(tu, tu.id == t.user_id)
        .join(tf, tf.user_id == t.user_id)
        .where(
            t.pool == vp.pool,
            t.user_id != vid,
            tu.status == UserStatus.active,
            tu.shadow_banned.is_(False),
            t.hidden_by_moderation.is_(False),
            tu.bot_blocked.is_(False),
            tu.last_active_at > now - timedelta(days=INACTIVE_CUTOFF_DAYS),
            ~exists().where(
                or_(
                    and_(Block.user_id == vid, Block.blocked_id == t.user_id),
                    and_(Block.user_id == t.user_id, Block.blocked_id == vid),
                )
            ),
            ~exists().where(Like.from_id == vid, Like.to_id == t.user_id),
            ~exists().where(
                Like.from_id == t.user_id,
                Like.to_id == vid,
                Like.status.in_((LikeStatus.pending, LikeStatus.declined)),
            ),
            ~exists().where(
                Match.user_a_id == func.least(vid, t.user_id),
                Match.user_b_id == func.greatest(vid, t.user_id),
            ),
            ~exists().where(Report.reporter_id == vid, Report.target_id == t.user_id),
            t.age.between(vf.age_min, vf.age_max),
            tf.age_min <= vp.age,
            tf.age_max >= vp.age,
            _accepts(vf.gender, t.gender),  # type: ignore[arg-type]  # mapped column
            _accepted_by(tf.gender, vp.gender),  # type: ignore[arg-type]  # mapped column
        )
    )
    if vf.verified_only:
        q = q.where(tu.verified.is_(True))
    if not ignore_views:
        hard = (ViewAction.like, ViewAction.like_msg, ViewAction.report, ViewAction.block)
        view = select(View).where(View.viewer_id == vid, View.target_id == t.user_id)
        if repeat_skips:
            # an old skip comes back only when the target's profile changed since
            q = q.where(
                ~exists(
                    view.where(
                        or_(
                            View.action.in_(hard),
                            View.action != ViewAction.skip,
                            View.acted_at > now - timedelta(days=SKIP_REPEAT_DAYS),
                            View.target_snapshot_hash == t.snapshot_hash,
                        )
                    )
                )
            )
        else:
            q = q.where(~exists(view))
    q = await _geo(ctx, q, t, vp, vf.radius, viewer.id)
    if only is not None:
        q = q.where(t.user_id.in_(only))
    return q.order_by(tu.last_active_at.desc()).limit(CANDIDATES_MAX)


async def _geo(  # noqa: PLR0913, PLR0917 - one query, many inputs
    ctx: Ctx, q: Select[Any], t: type[Profile], vp: Profile, radius: RadiusMode, vid: int
) -> Select[Any]:
    if radius is RadiusMode.city:
        return q.where(t.city_id == vp.city_id)
    if radius in rules.RADIUS_KM:
        if vp.geo is None:
            return q.where(t.city_id == vp.city_id)
        return q.where(ST_DWithin(t.geo, vp.geo, rules.RADIUS_KM[radius] * 1000))
    city = await ctx.session.get(City, vp.city_id)
    if city is None:
        raise RuntimeError("city is missing")
    tc = aliased(City, name="tc")
    if radius is RadiusMode.region:
        return q.join(tc, tc.id == t.city_id).where(tc.region_uk == city.region_uk)
    if radius is RadiusMode.country:
        return q.join(tc, tc.id == t.city_id).where(tc.country_code == city.country_code)
    goals = set(
        await ctx.session.scalars(select(ProfileGoal.goal).where(ProfileGoal.user_id == vid))
    )
    online = goals & rules.ONLINE_GOALS
    if online:
        q = q.where(exists().where(ProfileGoal.user_id == t.user_id, ProfileGoal.goal.in_(online)))
    return q


# ---- stage 2: features and scores -------------------------------------------------------


async def _people(ctx: Ctx, ids: Sequence[int]) -> dict[int, rules.Person]:
    rows = await ctx.session.execute(
        select(Profile, City.region_uk, Institution.type)
        .join(City, City.id == Profile.city_id)
        .outerjoin(Institution, Institution.id == Profile.institution_id)
        .where(Profile.user_id.in_(ids))
    )
    interests: dict[int, set[int]] = defaultdict(set)
    for uid, iid in await ctx.session.execute(
        select(ProfileInterest.user_id, ProfileInterest.interest_id).where(
            ProfileInterest.user_id.in_(ids)
        )
    ):
        interests[uid].add(iid)
    goals: dict[int, set[GoalCode]] = defaultdict(set)
    for uid, goal in await ctx.session.execute(
        select(ProfileGoal.user_id, ProfileGoal.goal).where(ProfileGoal.user_id.in_(ids))
    ):
        goals[uid].add(goal)
    out = {}
    for p, region, itype in rows:
        if p.age is None or p.city_id is None:
            continue
        out[p.user_id] = rules.Person(
            user_id=p.user_id,
            age=p.age,
            city_id=p.city_id,
            region=region,
            interests=frozenset(interests[p.user_id]),
            goals=frozenset(goals[p.user_id]),
            institution_id=p.institution_id,
            institution_type=itype,
        )
    return out


async def _catalog(ctx: Ctx, ids: set[int]) -> rules.Catalog:
    rows = await ctx.session.execute(
        select(Interest.id, Interest.idf, Interest.category_id).where(Interest.id.in_(ids))
    )
    idf, category = {}, {}
    for iid, value, cat in rows:
        idf[iid], category[iid] = value, cat
    return rules.Catalog(idf=idf, category=category)


async def _candidates(ctx: Ctx, viewer: User, ids: Sequence[int]) -> list[rules.Candidate]:
    people = await _people(ctx, [viewer.id, *ids])
    now = time.now()
    users = {u.id: u for u in await ctx.session.scalars(select(User).where(User.id.in_(ids)))}
    vp = await ctx.session.get(Profile, viewer.id)
    km: dict[int, float] = {}
    if vp is not None and vp.geo is not None:
        for uid, meters in await ctx.session.execute(
            select(Profile.user_id, ST_Distance(Profile.geo, vp.geo)).where(
                Profile.user_id.in_(ids), Profile.geo.is_not(None)
            )
        ):
            km[uid] = float(meters) / 1000
    photos = set(
        await ctx.session.scalars(
            select(Media.user_id).where(
                Media.user_id.in_(ids),
                Media.kind == MediaKind.photo,
                Media.moderation_status == ModerationStatus.approved,
            )
        )
    )
    prompts = set(
        await ctx.session.scalars(
            select(ProfilePrompt.user_id).where(
                ProfilePrompt.user_id.in_(ids),
                ProfilePrompt.moderation_status == ModerationStatus.approved,
            )
        )
    )
    report_rows = await ctx.session.execute(
        select(Report.target_id, func.count())
        .where(Report.target_id.in_(ids), Report.status == ReportStatus.open)
        .group_by(Report.target_id)
    )
    # a Result has .keys(), so dict(result) would treat it as a mapping
    reports: dict[int, int] = {target: n for target, n in report_rows}
    day = f"{time.kyiv_today():%Y%m%d}"
    exposure = await ctx.redis.mget([f"exposure:{i}:{day}" for i in ids]) if ids else []
    out = []
    for uid, seen in zip(ids, exposure, strict=True):
        person, user = people.get(uid), users.get(uid)
        if person is None or user is None:
            continue
        referral = (user.referred_by_id == viewer.id or viewer.referred_by_id == uid) and (
            now - max(user.created_at, viewer.created_at) < timedelta(hours=REFERRAL_BOOST_HOURS)
        )
        out.append(
            rules.Candidate(
                person=person,
                km=km.get(uid),
                hours_inactive=(now - user.last_active_at).total_seconds() / 3600,
                has_photo=uid in photos,
                has_prompt=uid in prompts,
                verified=user.verified,
                open_reports=reports.get(uid, 0),
                newbie=now - user.created_at < timedelta(hours=NEWBIE_BOOST_HOURS),
                exposure_today=int(seen or 0),
                referral=referral,
            )
        )
    return out


async def _viewer(ctx: Ctx, viewer: User) -> tuple[rules.Person, RadiusMode] | None:
    people = await _people(ctx, [viewer.id])
    vf = await ctx.session.get(Filters, viewer.id)
    if viewer.id not in people or vf is None:
        return None
    return people[viewer.id], vf.radius


async def match_percent(ctx: Ctx, viewer_id: int, target_id: int) -> int:
    """Shared-ness of two people for the card (0..100)."""
    viewer = await ctx.session.get(User, viewer_id)
    if viewer is None:
        return 0
    me = await _viewer(ctx, viewer)
    found = await _candidates(ctx, viewer, [target_id])
    if me is None or not found:
        return 0
    person, radius = me
    cat = await _catalog(ctx, set(person.interests | found[0].person.interests))
    return rules.match_percent(rules.base_score(person, found[0], radius, cat))


# ---- stage 3: batch and feed ------------------------------------------------------------


async def rebuild_batch(ctx: Ctx, viewer: User, rng: random.Random | None = None) -> list[int]:
    """Score candidates, mix 70/20/10, store feed:batch."""
    me = await _viewer(ctx, viewer)
    q = await _candidates_query(ctx, viewer)
    key = _batch_key(viewer.id)
    if me is None or q is None:
        await ctx.redis.delete(key)
        return []
    ids = list(await ctx.session.scalars(q))
    if not ids:
        q = await _candidates_query(ctx, viewer, repeat_skips=True)
        ids = list(await ctx.session.scalars(q)) if q is not None else []
    seen = {int(x) for x in await aw(ctx.redis.smembers(_seen_key(viewer.id)))}
    ids = [i for i in ids if i not in seen] or ids
    person, radius = me
    candidates = await _candidates(ctx, viewer, ids)
    all_interests = set(person.interests).union(*(c.person.interests for c in candidates))
    cat = await _catalog(ctx, all_interests)
    ranked = sorted(
        candidates,
        key=lambda c: rules.rank_score(rules.base_score(person, c, radius, cat), c),
        reverse=True,
    )
    batch = rules.mix_batch([c.person.user_id for c in ranked], rng or random.Random())  # noqa: S311
    await ctx.redis.delete(key)
    if batch:
        await aw(ctx.redis.rpush(key, *batch))
        await aw(ctx.redis.expire(key, BATCH_TTL))
    return batch


async def _still_valid(ctx: Ctx, viewer: User, target_id: int, *, ignore_views: bool) -> bool:
    q = await _candidates_query(ctx, viewer, only=[target_id], ignore_views=ignore_views)
    return q is not None and await ctx.session.scalar(q) is not None


async def record_view(ctx: Ctx, viewer_id: int, target_id: int) -> None:
    """views(shown) before the response, plus feed:seen and exposure."""
    snapshot = await ctx.session.scalar(
        select(Profile.snapshot_hash).where(Profile.user_id == target_id)
    )
    now = time.now()
    await ctx.session.execute(
        insert(View)
        .values(
            viewer_id=viewer_id,
            target_id=target_id,
            action=ViewAction.shown,
            target_snapshot_hash=snapshot,
            shown_at=now,
            acted_at=None,
            reshown=False,
        )
        .on_conflict_do_update(
            index_elements=["viewer_id", "target_id"],
            set_={
                "action": ViewAction.shown,
                "target_snapshot_hash": snapshot,
                "shown_at": now,
                "acted_at": None,
            },
        )
    )
    await ctx.session.commit()
    await aw(ctx.redis.sadd(_seen_key(viewer_id), target_id))
    exposure = f"exposure:{target_id}:{time.kyiv_today():%Y%m%d}"
    await aw(ctx.redis.incr(exposure))
    await aw(ctx.redis.expire(exposure, TWO_DAYS))


async def _item(ctx: Ctx, viewer: User, target_id: int) -> FeedItem:
    from svoi_api.domains.profiles import card  # noqa: PLC0415 - cycle

    can_undo = bool(await aw(ctx.redis.exists(f"feed:undo:{viewer.id}")))
    return FeedItem(card=await card.build(ctx, viewer, target_id, "feed"), can_undo=can_undo)


async def _empty_reason(ctx: Ctx, viewer: User) -> FeedEmpty | None:
    from svoi_api.domains.reactions import service as reactions  # noqa: PLC0415 - cycle

    if viewer.status is UserStatus.hidden:
        return FeedEmpty(reason=FeedEmptyReason.profile_hidden, expand_options=[], resets_at=None)
    if viewer.status is UserStatus.onboarding or await ctx.session.get(Filters, viewer.id) is None:
        return FeedEmpty(
            reason=FeedEmptyReason.profile_incomplete, expand_options=[], resets_at=None
        )
    limits = await reactions.limits(ctx, viewer)
    if limits.reactions_left <= 0:
        return FeedEmpty(
            reason=FeedEmptyReason.limit_reached, expand_options=[], resets_at=limits.resets_at
        )
    return None


async def _reshow(ctx: Ctx, viewer: User) -> int | None:
    """One card shown last session without a reaction, once."""
    rows = await ctx.session.scalars(
        select(View)
        .where(
            View.viewer_id == viewer.id,
            View.action == ViewAction.shown,
            View.acted_at.is_(None),
            View.reshown.is_(False),
            View.shown_at < time.now() - RESHOW_AFTER,
        )
        .order_by(View.shown_at)
        .limit(5)
    )
    for view in list(rows):
        view.reshown = True
        await ctx.session.commit()
        if await _still_valid(ctx, viewer, view.target_id, ignore_views=True):
            return view.target_id
    return None


async def _no_candidates(ctx: Ctx, viewer: User) -> FeedEmpty:
    vf = await ctx.session.get(Filters, viewer.id)
    vp = await ctx.session.get(Profile, viewer.id)
    goals = set(
        await ctx.session.scalars(select(ProfileGoal.goal).where(ProfileGoal.user_id == viewer.id))
    )
    options = rules.expand_options(
        vf.radius if vf else RadiusMode.city,
        has_geo=vp is not None and vp.geo is not None,
        gaming=GoalCode.gaming in goals,
    )
    return FeedEmpty(reason=FeedEmptyReason.no_candidates, expand_options=options, resets_at=None)


async def _pop(ctx: Ctx, viewer: User) -> int | None:
    key = _batch_key(viewer.id)
    while True:
        raw = await aw(ctx.redis.lpop(key))
        if raw is None or isinstance(raw, list):
            return None
        target = int(raw)
        if await _still_valid(ctx, viewer, target, ignore_views=False):
            return target


async def _refill(ctx: Ctx, viewer: User) -> None:
    stamp = time.now().strftime("%Y%m%d%H%M")
    reason = RebuildReason.refill
    job = RebuildFeed(
        dedupe_key=f"feed:{viewer.id}:{reason.value}:{stamp}", user_id=viewer.id, reason=reason
    )
    await ctx.queue.enqueue(job, "api")


async def feed_next(ctx: Ctx, viewer: User) -> FeedResponse:
    """Next card or the reason there is none."""
    empty = await _empty_reason(ctx, viewer)
    if empty is not None:
        return empty
    target = await _reshow(ctx, viewer)
    if target is None:
        target = await _pop(ctx, viewer)
        if target is None:
            await rebuild_batch(ctx, viewer)
            target = await _pop(ctx, viewer)
        elif await aw(ctx.redis.llen(_batch_key(viewer.id))) <= FEED_REFILL_AT:
            await _refill(ctx, viewer)
    if target is None:
        return await _no_candidates(ctx, viewer)
    await record_view(ctx, viewer.id, target)
    return await _item(ctx, viewer, target)


async def expand(ctx: Ctx, viewer: User, radius: RadiusMode) -> FeedResponse:
    """Wider search from the empty-feed buttons."""
    from svoi_api.domains.prefs import service as prefs  # noqa: PLC0415 - cycle

    empty = await _no_candidates(ctx, viewer)
    if radius not in empty.expand_options:
        raise DomainError(ErrorCode.validation_error, message="radius is not an expand option")
    await prefs.set_radius(ctx, viewer, radius)
    await rebuild_batch(ctx, viewer)
    return await feed_next(ctx, viewer)


async def item_for(ctx: Ctx, viewer: User, target_id: int) -> FeedItem:
    """A specific card as a feed item (undo)."""
    return await _item(ctx, viewer, target_id)


async def rebuild_job(ctx: Ctx, user_id: int) -> None:
    """api.rebuild_feed: overwrite the batch (idempotent by construction)."""
    user = await ctx.session.get(User, user_id)
    if user is not None and user.status is UserStatus.active:
        await rebuild_batch(ctx, user)
