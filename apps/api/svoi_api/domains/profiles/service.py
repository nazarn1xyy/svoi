"""Profiles: onboarding fields, media, completeness, my card, hide (S1-S5)."""

from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_Distance, ST_GeogFromText
from sqlalchemy import delete, func, select, update
from svoi_contracts.api.profile import (
    CityIn,
    ClarificationOut,
    MediaIn,
    OptionOut,
    PromptsIn,
)
from svoi_contracts.cards import MediaRef, ProfileCard, UserState
from svoi_contracts.constants import CLARIFICATIONS_MAX, HEIGHT_CM, INTERESTS_COUNT, MEDIA_MAX
from svoi_contracts.enums import (
    ContentField,
    Gender,
    GoalCode,
    MediaKind,
    ModerationStatus,
    OnboardingStep,
    RebuildReason,
    UserStatus,
)
from svoi_contracts.errors import ErrorCode
from svoi_contracts.jobs import ModeratePhoto, RebuildFeed

from svoi_api.core import time
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
    User,
)
from svoi_api.deps import Ctx
from svoi_api.domains.profiles import rules
from svoi_api.domains.users import service as users

CITY_MAX_KM = 50


async def profile(ctx: Ctx, user_id: int) -> Profile:
    """The user's profile row (created with the user)."""
    row = await ctx.session.get(Profile, user_id)
    if row is None:
        raise DomainError(ErrorCode.not_found, message="no profile")
    return row


async def _check_text(ctx: Ctx, user: User, text: str, field: ContentField) -> None:
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

    await safety.check_field(ctx, user, text, field)


# ---- S1 ---------------------------------------------------------------------------------


async def set_age(ctx: Ctx, user: User, age: int) -> UserState:
    """Age with the edit window, cooldown and pool rules."""
    users.check_step(user, OnboardingStep.age)
    p = await profile(ctx, user.id)
    now = time.now()
    error = rules.age_decision(
        age,
        current=p.age,
        set_at=p.age_set_at,
        edits=p.age_edits,
        rejected_at=p.age_rejected_at,
        now=now,
    )
    if error is not None:
        if error is ErrorCode.age_too_young:
            await ctx.session.execute(
                update(Profile).where(Profile.user_id == user.id).values(age_rejected_at=now)
            )
            await ctx.session.commit()
        raise DomainError(error)
    if p.age is None:
        p.age_set_at = now
    elif age != p.age:
        p.age_edits += 1
    p.age, p.pool = age, rules.pool_for(age)
    users.advance(user, OnboardingStep.age)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


async def set_name(ctx: Ctx, user: User, name: str) -> UserState:
    """2-20 letters, content filter."""
    users.check_step(user, OnboardingStep.name)
    name = " ".join(name.split())
    await _check_text(ctx, user, name, ContentField.name)
    if not rules.valid_name(name):
        raise DomainError(ErrorCode.validation_error, message="name: 2-20 letters, no digits")
    (await profile(ctx, user.id)).name = name
    users.advance(user, OnboardingStep.name)
    await ctx.session.commit()
    return await users.state(ctx, user)


async def set_gender(ctx: Ctx, user: User, gender: Gender) -> UserState:
    """male | female | hidden."""
    users.check_step(user, OnboardingStep.gender)
    (await profile(ctx, user.id)).gender = gender
    users.advance(user, OnboardingStep.gender)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


# ---- S2 ---------------------------------------------------------------------------------


async def set_city(ctx: Ctx, user: User, body: CityIn) -> UserState:
    """City plus optional rounded coordinates near it."""
    users.check_step(user, OnboardingStep.city)
    city = await ctx.session.get(City, body.city_id)
    if city is None:
        raise DomainError(ErrorCode.not_found, message="no such city")
    p = await profile(ctx, user.id)
    p.city_id = city.id
    p.geo = None
    if body.lat is not None and body.lon is not None:
        lat, lon = rules.round_coord(body.lat), rules.round_coord(body.lon)
        point = f"SRID=4326;POINT({lon} {lat})"
        meters = await ctx.session.scalar(
            select(ST_Distance(City.location, ST_GeogFromText(point))).where(City.id == city.id)
        )
        if meters is None or meters / 1000 > CITY_MAX_KM:
            await ctx.session.rollback()
            raise DomainError(ErrorCode.validation_error, message="location is far from the city")
        p.geo = WKTElement(f"POINT({lon} {lat})", srid=4326)  # type: ignore[assignment]  # WKT on write
    users.advance(user, OnboardingStep.city)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


# ---- S3 ---------------------------------------------------------------------------------


async def set_goals(ctx: Ctx, user: User, codes: list[GoalCode]) -> UserState:
    """Replace the goal set."""
    users.check_step(user, OnboardingStep.goals)
    if len(set(codes)) != len(codes):
        raise DomainError(ErrorCode.validation_error, message="goals must not repeat")
    await ctx.session.execute(delete(ProfileGoal).where(ProfileGoal.user_id == user.id))
    ctx.session.add_all(ProfileGoal(user_id=user.id, goal=c) for c in codes)
    users.advance(user, OnboardingStep.goals)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


async def set_interests(ctx: Ctx, user: User, ids: list[int]) -> UserState:
    """Replace the interest set; notes of kept interests survive."""
    users.check_step(user, OnboardingStep.interests)
    found = set(
        await ctx.session.scalars(
            select(Interest.id).where(
                Interest.id.in_(ids), Interest.moderation_status == ModerationStatus.approved
            )
        )
    )
    if found != set(ids) or not INTERESTS_COUNT[0] <= len(ids) <= INTERESTS_COUNT[1]:
        raise DomainError(ErrorCode.validation_error, message="unknown or unapproved interest")
    await ctx.session.execute(
        delete(ProfileInterest).where(
            ProfileInterest.user_id == user.id, ProfileInterest.interest_id.not_in(ids)
        )
    )
    have = set(
        await ctx.session.scalars(
            select(ProfileInterest.interest_id).where(ProfileInterest.user_id == user.id)
        )
    )
    ctx.session.add_all(
        ProfileInterest(user_id=user.id, interest_id=i) for i in ids if i not in have
    )
    users.advance(user, OnboardingStep.interests)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


async def add_interest(ctx: Ctx, user_id: int, interest_id: int) -> None:
    """Approved custom tag goes into its author's profile (S10)."""
    exists = await ctx.session.get(ProfileInterest, (user_id, interest_id))
    if exists is None:
        ctx.session.add(ProfileInterest(user_id=user_id, interest_id=interest_id))


# ---- S4 ---------------------------------------------------------------------------------


async def clarifications(ctx: Ctx, user: User) -> list[ClarificationOut]:
    """Unanswered clarifications of the user's interests, top priority first."""
    rows = await ctx.session.execute(
        select(Clarification, Interest)
        .join(Interest, Interest.id == Clarification.interest_id)
        .join(
            ProfileInterest,
            (ProfileInterest.interest_id == Interest.id) & (ProfileInterest.user_id == user.id),
        )
        .where(ProfileInterest.note_key.is_(None))
        .order_by(Clarification.priority.desc(), Clarification.id)
        .limit(CLARIFICATIONS_MAX)
    )
    return [
        ClarificationOut(
            interest_id=interest.id,
            interest_title=local(interest, "title", user.lang),
            question_key=c.question_key,
            options=[
                OptionOut(key=o["key"], title=local(o, "title", user.lang)) for o in c.options
            ],
        )
        for c, interest in rows.tuples()
    ]


async def set_note(ctx: Ctx, user: User, interest_id: int, option_key: str) -> UserState:
    """Answer one clarification; the step closes with /onboarding/skip."""
    users.check_step(user, OnboardingStep.clarify)
    link = await ctx.session.get(ProfileInterest, (user.id, interest_id))
    clar = await ctx.session.scalar(
        select(Clarification).where(Clarification.interest_id == interest_id)
    )
    if link is None or clar is None:
        raise DomainError(ErrorCode.not_found)
    if option_key not in {o["key"] for o in clar.options}:
        raise DomainError(ErrorCode.validation_error, message="unknown option")
    link.note_key = option_key
    await ctx.session.commit()
    await profile_changed(ctx, user.id, rebuild=False)
    return await users.state(ctx, user)


async def set_institution(ctx: Ctx, user: User, institution_id: int | None) -> UserState:
    """Institution or None to remove."""
    users.check_step(user, OnboardingStep.institution)
    if institution_id is not None and await ctx.session.get(Institution, institution_id) is None:
        raise DomainError(ErrorCode.not_found)
    (await profile(ctx, user.id)).institution_id = institution_id
    users.advance(user, OnboardingStep.institution)
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


async def set_height(ctx: Ctx, user: User, height_cm: int | None) -> UserState:
    """Height within HEIGHT_CM or None."""
    users.check_step(user, OnboardingStep.height)
    if height_cm is not None and not HEIGHT_CM[0] <= height_cm <= HEIGHT_CM[1]:
        raise DomainError(ErrorCode.validation_error, message="height out of range")
    (await profile(ctx, user.id)).height_cm = height_cm
    users.advance(user, OnboardingStep.height)
    await ctx.session.commit()
    await profile_changed(ctx, user.id, rebuild=False)
    return await users.state(ctx, user)


async def set_prompts(ctx: Ctx, user: User, body: PromptsIn) -> UserState:
    """Replace prompt answers; underage hints in the adult pool go to moderation."""
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

    users.check_step(user, OnboardingStep.prompts)
    ids = [a.prompt_id for a in body.answers]
    active = set(
        await ctx.session.scalars(select(Prompt.id).where(Prompt.id.in_(ids), Prompt.active))
    )
    if active != set(ids) or len(set(ids)) != len(ids):
        raise DomainError(ErrorCode.validation_error, message="unknown or repeated prompt")
    statuses = []
    for answer in body.answers:
        await _check_text(ctx, user, answer.text, ContentField.prompt)
        flagged = await safety.flag_underage_prompt(ctx, user, answer.text)
        statuses.append(ModerationStatus.pending if flagged else ModerationStatus.approved)
    await ctx.session.execute(delete(ProfilePrompt).where(ProfilePrompt.user_id == user.id))
    ctx.session.add_all(
        ProfilePrompt(user_id=user.id, prompt_id=a.prompt_id, text=a.text, moderation_status=s)
        for a, s in zip(body.answers, statuses, strict=True)
    )
    users.advance(user, OnboardingStep.prompts)
    await ctx.session.commit()
    await profile_changed(ctx, user.id, rebuild=False)
    return await users.state(ctx, user)


def media_ref(m: Media) -> MediaRef:
    """Contract view of a media row."""
    return MediaRef(id=m.id, kind=m.kind, file_id=m.file_id, moderation_status=m.moderation_status)


async def _media(ctx: Ctx, user_id: int) -> list[Media]:
    return list(
        await ctx.session.scalars(
            select(Media).where(Media.user_id == user_id).order_by(Media.position)
        )
    )


async def add_media(ctx: Ctx, user: User, body: MediaIn) -> MediaRef:
    """Photo goes to the NSFW check, video straight to the manual queue."""
    current = await _media(ctx, user.id)
    if len(current) >= MEDIA_MAX:
        raise DomainError(ErrorCode.media_limit)
    m = Media(
        user_id=user.id,
        kind=body.kind,
        file_id=body.file_id,
        file_unique_id=body.file_unique_id,
        position=len(current),
        moderation_status=ModerationStatus.pending,
    )
    ctx.session.add(m)
    await ctx.session.commit()
    if body.kind is MediaKind.photo:
        await ctx.queue.enqueue(ModeratePhoto(dedupe_key=f"photo:{m.id}", media_id=m.id), "api")
    await profile_changed(ctx, user.id, rebuild=False)
    return media_ref(m)


async def _renumber(ctx: Ctx, rows: list[Media]) -> None:
    # two passes: (user_id, position) is unique
    for i, m in enumerate(rows):
        m.position = 100 + i
    await ctx.session.flush()
    for i, m in enumerate(rows):
        m.position = i


async def delete_media(ctx: Ctx, user: User, media_id: int) -> UserState:
    """Remove one media and close the gap."""
    rows = await _media(ctx, user.id)
    target = next((m for m in rows if m.id == media_id), None)
    if target is None:
        raise DomainError(ErrorCode.not_found)
    await ctx.session.delete(target)
    await ctx.session.flush()
    await _renumber(ctx, [m for m in rows if m.id != media_id])
    await ctx.session.commit()
    await profile_changed(ctx, user.id)
    return await users.state(ctx, user)


async def reorder_media(ctx: Ctx, user: User, ids: list[int]) -> list[MediaRef]:
    """New order: exactly all of the user's media ids."""
    rows = {m.id: m for m in await _media(ctx, user.id)}
    if sorted(ids) != sorted(rows):
        raise DomainError(ErrorCode.validation_error, message="ids must list every media once")
    await _renumber(ctx, [rows[i] for i in ids])
    await ctx.session.commit()
    return [media_ref(rows[i]) for i in ids]


async def drop_media(ctx: Ctx, user_id: int, media_id: int | None = None) -> None:
    """Moderation: delete one media or all of them (no commit)."""
    query = delete(Media).where(Media.user_id == user_id)
    if media_id is not None:
        query = query.where(Media.id == media_id)
    await ctx.session.execute(query)
    await ctx.session.flush()
    await _renumber(ctx, await _media(ctx, user_id))


# ---- completeness, missing fields, change hook -------------------------------------------


async def missing_fields(ctx: Ctx, user_id: int) -> list[str]:
    """Required fields for /onboarding/complete that are still empty."""
    p = await profile(ctx, user_id)
    goals = await ctx.session.scalar(
        select(func.count()).select_from(ProfileGoal).where(ProfileGoal.user_id == user_id)
    )
    interests = await ctx.session.scalar(
        select(func.count()).select_from(ProfileInterest).where(ProfileInterest.user_id == user_id)
    )
    have = {
        "age": p.age is not None,
        "name": p.name is not None,
        "gender": p.gender is not None,
        "city": p.city_id is not None,
        "goals": bool(goals),
        "interests": (interests or 0) >= INTERESTS_COUNT[0],
    }
    return [k for k, ok in have.items() if not ok]


async def _completeness(ctx: Ctx, user_id: int, p: Profile) -> int:
    approved_photo = await ctx.session.scalar(
        select(func.count()).where(
            Media.user_id == user_id,
            Media.kind == MediaKind.photo,
            Media.moderation_status == ModerationStatus.approved,
        )
    )
    prompts = await ctx.session.scalar(
        select(func.count()).select_from(ProfilePrompt).where(ProfilePrompt.user_id == user_id)
    )
    notes = await ctx.session.scalar(
        select(func.count()).where(
            ProfileInterest.user_id == user_id, ProfileInterest.note_key.is_not(None)
        )
    )
    return rules.completeness(
        required=not await missing_fields(ctx, user_id),
        has_photo=bool(approved_photo),
        has_prompt=bool(prompts),
        has_institution=p.institution_id is not None,
        has_height_or_note=p.height_cm is not None or bool(notes),
    )


async def profile_changed(ctx: Ctx, user_id: int, *, rebuild: bool = True) -> None:
    """Recount completeness and snapshot hash; rebuild the feed when matching inputs moved."""
    p = await profile(ctx, user_id)
    interest_ids = await ctx.session.scalars(
        select(ProfileInterest.interest_id).where(ProfileInterest.user_id == user_id)
    )
    media_ids = await ctx.session.scalars(select(Media.id).where(Media.user_id == user_id))
    p.snapshot_hash = rules.snapshot_hash(interest_ids, media_ids)
    p.completeness = await _completeness(ctx, user_id, p)
    await ctx.session.commit()
    user = await ctx.session.get(User, user_id)
    if rebuild and user is not None and user.status is UserStatus.active:
        stamp = time.now().strftime("%Y%m%d%H%M")
        reason = RebuildReason.profile_changed
        job = RebuildFeed(
            dedupe_key=f"feed:{user_id}:{reason.value}:{stamp}", user_id=user_id, reason=reason
        )
        await ctx.queue.enqueue(job, "api")


# ---- S5 ---------------------------------------------------------------------------------


async def my_card(ctx: Ctx, user: User) -> ProfileCard:
    """Own card with all media and completeness."""
    from svoi_api.domains.profiles import card  # noqa: PLC0415 - card imports this module

    missing = [m for m in await missing_fields(ctx, user.id) if m in ("age", "name", "city")]
    if missing:
        raise DomainError(ErrorCode.profile_incomplete, {"missing": missing})
    return await card.build(ctx, user, user.id, "own")


async def reset(ctx: Ctx, user: User) -> UserState:
    """Fill in again from the age step; likes, contacts and views stay."""
    user.status, user.onboarding_step = UserStatus.onboarding, OnboardingStep.age
    await ctx.session.commit()
    return await users.state(ctx, user)


async def hide(ctx: Ctx, user: User) -> UserState:
    """Out of everyone's feed."""
    user.status = UserStatus.hidden
    await ctx.session.commit()
    return await users.state(ctx, user)


async def unhide(ctx: Ctx, user: User) -> UserState:
    """Back to the feed; only from hidden."""
    if user.status is not UserStatus.hidden:
        raise DomainError(ErrorCode.conflict, message="profile is not hidden")
    user.status = UserStatus.active
    await ctx.session.commit()
    return await users.state(ctx, user)
