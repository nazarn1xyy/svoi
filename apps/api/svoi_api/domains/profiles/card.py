"""build(viewer, target, mode) -> ProfileCard: the one card builder for S5, S7, S9, S10."""

from typing import Literal

from geoalchemy2.functions import ST_Distance
from sqlalchemy import select
from svoi_contracts.cards import CommonBlock, InterestChip, ProfileCard, PromptAnswer
from svoi_contracts.enums import Gender, Lang, ModerationStatus, Pool
from svoi_contracts.errors import ErrorCode

from svoi_api.core.errors import DomainError
from svoi_api.core.i18n import local
from svoi_api.db.models import (
    City,
    Clarification,
    Institution,
    Interest,
    Media,
    Profile,
    ProfileGoal,
    ProfileInterest,
    ProfilePrompt,
    Prompt,
    Settings,
    User,
)
from svoi_api.deps import Ctx
from svoi_api.domains.profiles import rules
from svoi_api.domains.profiles.service import media_ref

CardMode = Literal["own", "feed", "incoming", "match", "admin"]
_SEES_PENDING: frozenset[str] = frozenset({"own", "admin"})
_SHOWS_COMMON: frozenset[str] = frozenset({"feed", "incoming"})


async def _interests(ctx: Ctx, user_id: int, lang: Lang) -> list[tuple[int, str, str | None]]:
    """(id, title, localized note) of the user's approved interests."""
    rows = await ctx.session.execute(
        select(Interest, ProfileInterest.note_key, Clarification.options)
        .join(ProfileInterest, ProfileInterest.interest_id == Interest.id)
        .outerjoin(Clarification, Clarification.interest_id == Interest.id)
        .where(
            ProfileInterest.user_id == user_id,
            Interest.moderation_status == ModerationStatus.approved,
        )
        .order_by(Interest.id)
    )
    out = []
    for interest, note_key, options in rows.tuples():
        note = None
        if note_key and options:
            option = next((o for o in options if o["key"] == note_key), None)
            note = local(option, "title", lang) if option else None
        out.append((interest.id, local(interest, "title", lang), note))
    return out


async def _distance_km(ctx: Ctx, a: Profile, b: Profile) -> float | None:
    if a.geo is None or b.geo is None:
        return None
    meters = await ctx.session.scalar(
        select(
            ST_Distance(
                Profile.geo,
                select(Profile.geo).where(Profile.user_id == b.user_id).scalar_subquery(),
            )
        ).where(Profile.user_id == a.user_id)
    )
    return None if meters is None else float(meters) / 1000


async def build(ctx: Ctx, viewer: User, target_id: int, mode: CardMode) -> ProfileCard:
    """Card of target_id as viewer sees it in this mode."""
    target = await ctx.session.get(User, target_id)
    p = await ctx.session.get(Profile, target_id)
    if target is None or p is None or p.age is None or p.name is None or p.city_id is None:
        raise DomainError(ErrorCode.not_found, message="card is not ready")
    lang = viewer.lang
    own = mode == "own"
    settings = await ctx.session.get(Settings, target_id)
    city = await ctx.session.get(City, p.city_id)
    if city is None:
        raise RuntimeError("city is missing")
    goals = list(
        await ctx.session.scalars(
            select(ProfileGoal.goal)
            .where(ProfileGoal.user_id == target_id)
            .order_by(ProfileGoal.goal)
        )
    )
    interests = await _interests(ctx, target_id, lang)
    viewer_interests = (
        set()
        if own
        else set(
            await ctx.session.scalars(
                select(ProfileInterest.interest_id).where(ProfileInterest.user_id == viewer.id)
            )
        )
    )
    chips = [
        InterestChip(id=i, title=t, note=n, common=i in viewer_interests) for i, t, n in interests
    ]
    chips.sort(key=lambda c: not c.common)  # stable: common first

    show_pending = mode in _SEES_PENDING
    media_q = select(Media).where(Media.user_id == target_id).order_by(Media.position)
    prompt_q = (
        select(ProfilePrompt, Prompt)
        .join(Prompt, Prompt.id == ProfilePrompt.prompt_id)
        .where(ProfilePrompt.user_id == target_id)
        .order_by(Prompt.id)
    )
    if not show_pending:
        media_q = media_q.where(Media.moderation_status == ModerationStatus.approved)
        prompt_q = prompt_q.where(ProfilePrompt.moderation_status == ModerationStatus.approved)
    media = [media_ref(m) for m in await ctx.session.scalars(media_q)]
    prompts = [
        PromptAnswer(prompt_id=pr.id, title=local(pr, "title", lang), text=pp.text)
        for pp, pr in (await ctx.session.execute(prompt_q)).tuples()
    ]

    hide_inst = not own and settings is not None and not settings.show_institution
    institution = (
        None
        if p.institution_id is None or hide_inst
        else await ctx.session.get(Institution, p.institution_id)
    )

    distance = None
    common = None
    if not own and mode != "admin":
        vp = await ctx.session.get(Profile, viewer.id)
        if vp is not None and (settings is None or settings.show_distance):
            distance = rules.distance_bucket(
                await _distance_km(ctx, vp, p),
                same_city=vp.city_id == p.city_id,
                minor=p.pool is Pool.minor,
            )
        if mode in _SHOWS_COMMON and vp is not None:
            from svoi_api.domains.matching import service as matching  # noqa: PLC0415 - cycle

            common = CommonBlock(
                interest_titles=[c.title for c in chips if c.common],
                same_institution=p.institution_id is not None
                and p.institution_id == vp.institution_id,
                match_percent=await matching.match_percent(ctx, viewer.id, target_id),
            )

    return ProfileCard(
        user_id=target_id,
        name=p.name,
        age=p.age,
        verified=target.verified,
        gender=None if p.gender in (None, Gender.hidden) else p.gender,
        city_name=local(city, "name", lang),
        distance=distance,
        goals=goals,
        interests=chips,
        institution_name=None
        if institution is None
        else (institution.short_name or institution.name),
        height_cm=p.height_cm,
        prompts=prompts,
        media=media,
        common=common,
        completeness=p.completeness if own else None,
    )
