"""Users: start, state, language, consent, onboarding step machine, delete (S1, S5)."""

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from svoi_contracts.api.users import StartIn
from svoi_contracts.cards import Counters, UserState
from svoi_contracts.enums import Lang, OnboardingStep, UserStatus
from svoi_contracts.errors import ErrorCode

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.db.models import Profile, User
from svoi_api.deps import Ctx
from svoi_api.domains.users import rules


async def incoming_likes(ctx: Ctx, user_id: int) -> int:
    """Pending likes to the user from visible authors (S9 counter)."""
    from svoi_api.domains.likes import service as likes  # noqa: PLC0415 - cycle

    return await likes.incoming_count(ctx, user_id)


async def captcha_required(ctx: Ctx, user: User) -> bool:
    """S11b rule, delegated to safety."""
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

    return await safety.captcha_required(ctx, user)


async def state(ctx: Ctx, user: User) -> UserState:
    """UserState after the change (BACKEND 4.5)."""
    pool = await ctx.session.scalar(select(Profile.pool).where(Profile.user_id == user.id))
    return UserState(
        user_id=user.id,
        tg_id=user.tg_id,
        status=user.status,
        lang=user.lang,
        onboarding_step=user.onboarding_step,
        pool=pool,
        needs_username=user.tg_username is None,
        captcha_required=await captcha_required(ctx, user),
        is_admin=user.tg_id in ctx.settings.admin_tg_ids,
        counters=Counters(incoming_likes=await incoming_likes(ctx, user.id)),
    )


def check_step(user: User, step: OnboardingStep) -> None:
    """PUT of a future step -> conflict; call before validating the body."""
    if user.status is not UserStatus.onboarding:
        return
    if rules.is_ahead(step, user.onboarding_step):
        raise DomainError(
            ErrorCode.conflict,
            {"current": user.onboarding_step.value},
            f"current step is {user.onboarding_step.value}",
        )


def advance(user: User, step: OnboardingStep) -> None:
    """After a successful PUT of `step`: the current step moves on, past steps stay."""
    check_step(user, step)
    if user.status is UserStatus.onboarding and step is user.onboarding_step:
        user.onboarding_step = rules.next_step(step)


async def _unique_code(ctx: Ctx) -> str:
    while True:
        code = rules.new_referral_code()
        taken = await ctx.session.scalar(select(func.count()).where(User.referral_code == code))
        if not taken:
            return code


async def start(ctx: Ctx, tg_id: int, body: StartIn) -> UserState:
    """Create the user on first contact, refresh Telegram fields after."""
    user = await ctx.session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        referrer = None
        if body.referral_code:
            referrer = await ctx.session.scalar(
                select(User.id).where(User.referral_code == body.referral_code)
            )
        user = User(
            tg_id=tg_id,
            tg_username=body.tg_username,
            tg_first_name=body.tg_first_name,
            lang=rules.default_lang(body.tg_language_code),
            status=UserStatus.onboarding,
            onboarding_step=OnboardingStep.lang,
            referral_code=await _unique_code(ctx),
            referred_by_id=referrer,
            last_active_at=time.now(),
        )
        ctx.session.add(user)
        try:
            await ctx.session.flush()
        except IntegrityError:
            # a parallel /start created the same tg_id first
            await ctx.session.rollback()
            return await start(ctx, tg_id, body)
        ctx.session.add(Profile(user_id=user.id))
        from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

        await safety.score_new_user(ctx, user, has_photo=body.has_tg_profile_photo)
    else:
        user.tg_username, user.tg_first_name = body.tg_username, body.tg_first_name
        user.bot_blocked = False
    await ctx.session.commit()
    if user.status is UserStatus.banned:
        if user.banned_until is not None and user.banned_until <= time.now():
            user.status, user.banned_until = UserStatus.active, None
            await ctx.session.commit()
        else:
            until = None if user.banned_until is None else user.banned_until.isoformat()
            raise DomainError(ErrorCode.banned, {"until": until})
    return await state(ctx, user)


async def set_lang(ctx: Ctx, user: User, lang: Lang) -> UserState:
    """Language; on the lang step also moves to consent."""
    advance(user, OnboardingStep.lang)
    user.lang = lang  # no validation can fail after the step check
    await ctx.session.commit()
    return await state(ctx, user)


async def consent(ctx: Ctx, user: User) -> UserState:
    """Rules accepted: only from the consent step."""
    if user.onboarding_step is not OnboardingStep.consent:
        raise DomainError(ErrorCode.conflict, {"current": user.onboarding_step.value})
    user.consent_at = time.now()
    user.onboarding_step = OnboardingStep.age
    await ctx.session.commit()
    return await state(ctx, user)


async def skip(ctx: Ctx, user: User, step: OnboardingStep) -> UserState:
    """Skip the current optional step."""
    if step not in rules.OPTIONAL_STEPS or step is not user.onboarding_step:
        raise DomainError(ErrorCode.conflict, {"current": user.onboarding_step.value})
    user.onboarding_step = rules.next_step(step)
    await ctx.session.commit()
    return await state(ctx, user)


async def complete(ctx: Ctx, user: User) -> UserState:
    """Required fields present -> active, filters and settings, referral bonus."""
    from svoi_api.domains import prefs, profiles, referrals, safety  # noqa: PLC0415 - cycle

    missing = await profiles.service.missing_fields(ctx, user.id)
    if missing:
        raise DomainError(ErrorCode.profile_incomplete, {"missing": missing})
    first_time = user.onboarding_step is not OnboardingStep.done
    user.status = UserStatus.active
    user.onboarding_step = OnboardingStep.done
    await prefs.service.ensure_defaults(ctx, user.id)
    if first_time:
        await safety.service.score_onboarding_speed(ctx, user)
    await referrals.service.reward(ctx, user)
    await ctx.session.commit()
    await profiles.service.profile_changed(ctx, user.id)
    return await state(ctx, user)


async def delete_me(ctx: Ctx, user: User) -> None:
    """Remove everything; a banned user keeps the users row so the ban survives."""
    banned = user.status is UserStatus.banned
    keep = (user.tg_id, user.banned_until, user.referral_code)
    await ctx.session.execute(delete(User).where(User.id == user.id))  # cascades everywhere
    if banned:
        tg_id, until, code = keep
        ctx.session.add(
            User(
                tg_id=tg_id,
                status=UserStatus.banned,
                banned_until=until,
                referral_code=code,
                onboarding_step=OnboardingStep.lang,
                last_active_at=time.now(),
            )
        )
    await ctx.session.commit()
    await ctx.redis.delete(f"feed:batch:{user.id}", f"feed:seen:{user.id}")
