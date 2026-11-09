"""Safety: content filter on fields, age hints, spam detector, risk, captcha (S11)."""

import hashlib
import itertools
import secrets
import uuid

from svoi_contracts.api.safety import CaptchaChallenge
from svoi_contracts.cards import UserState
from svoi_contracts.constants import (
    ADULT_AGE,
    CAPTCHA_FAILS_RISK,
    CAPTCHA_OPTIONS,
    CAPTCHA_TTL_SECONDS,
    DUP_MESSAGE_THRESHOLD,
    FAST_ONBOARDING_SECONDS,
    RAPID_REACTION_INTERVAL_S,
    RAPID_REACTION_STREAK_S,
    RISK_CAPTCHA_THRESHOLD,
)
from svoi_contracts.enums import (
    ContentBlockReason,
    ContentField,
    Pool,
    ReportContext,
    ReportReason,
)
from svoi_contracts.errors import ErrorCode

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.core.redis import aw
from svoi_api.db.models import Profile, Report, User
from svoi_api.deps import Ctx
from svoi_api.domains.safety import rules

RISK_NO_USERNAME = 15
RISK_NO_PHOTO = 15
RISK_NEW_ACCOUNT = 20
RISK_FAST_ONBOARDING = 20
RISK_STOPWORD = 30
RISK_PHASH_DUP = 20
RISK_RHYTHM = 30
RISK_SPAM = 30
RISK_CAPTCHA_FAILS = 10
CAPTCHA_PASS_BONUS = 30
TWO_DAYS = 48 * 3600
EMOJI = (
    "🐶", "🐱", "🦊", "🐻", "🐼", "🐸", "🐵", "🦁", "🐯", "🐨",
    "🐷", "🐮", "🐔", "🐧", "🐙", "🦄", "🐝", "🐢", "🐳", "🦉",
)  # fmt: skip


async def add_risk(ctx: Ctx, user: User, points: int) -> None:
    """Raise risk_score (no commit); remembers when it last grew for the captcha rule."""
    user.risk_score = min(32767, user.risk_score + points)
    await ctx.redis.set(f"risk:raised:{user.id}", time.now().timestamp())


async def captcha_required(ctx: Ctx, user: User) -> bool:
    """risk >= threshold, and the captcha was never passed or the risk grew after it."""
    if user.risk_score < RISK_CAPTCHA_THRESHOLD:
        return False
    if user.captcha_passed_at is None:
        return True
    raised = await ctx.redis.get(f"risk:raised:{user.id}")
    return raised is not None and float(raised) > user.captcha_passed_at.timestamp()


async def score_new_user(ctx: Ctx, user: User, *, has_photo: bool) -> None:
    """Signals known at /start."""
    points = 0
    if user.tg_username is None:
        points += RISK_NO_USERNAME
    if not has_photo:
        points += RISK_NO_PHOTO
    minimum = ctx.settings.new_account_tg_id_min
    if minimum and user.tg_id > minimum:
        points += RISK_NEW_ACCOUNT
    if points:
        await add_risk(ctx, user, points)


async def score_onboarding_speed(ctx: Ctx, user: User) -> None:
    """Onboarding faster than a human could read it."""
    if (time.now() - user.created_at).total_seconds() < FAST_ONBOARDING_SECONDS:
        await add_risk(ctx, user, RISK_FAST_ONBOARDING)


async def _pool(ctx: Ctx, user: User) -> Pool | None:
    profile = await ctx.session.get(Profile, user.id)
    return None if profile is None else profile.pool


def _system_report(target_id: int, text: str) -> Report:
    return Report(
        reporter_id=None,
        target_id=target_id,
        reason=ReportReason.underage,
        text=text[:500],
        context=ReportContext.system,
    )


async def check_field(ctx: Ctx, user: User, text: str, field: ContentField) -> None:
    """content_blocked {field, reason} for links, mentions, phones, stopwords, age in name."""
    reason = rules.check_text(text)
    if reason is None and field is ContentField.name:
        age = rules.detect_age_mention(text)
        if age is not None and age < ADULT_AGE and await _pool(ctx, user) is Pool.adult:
            reason = ContentBlockReason.age_mismatch
    if reason is None:
        return
    if reason is ContentBlockReason.stopword:
        await add_risk(ctx, user, RISK_STOPWORD)
        await ctx.session.commit()
    raise DomainError(ErrorCode.content_blocked, {"field": field.value, "reason": reason.value})


async def flag_underage_prompt(ctx: Ctx, user: User, text: str) -> bool:
    """Adult pool + "мені 17" in a prompt: hide for moderation, system report (no error)."""
    age = rules.detect_age_mention(text)
    if age is None or age >= ADULT_AGE or await _pool(ctx, user) is not Pool.adult:
        return False
    profile = await ctx.session.get(Profile, user.id)
    if profile is None:
        raise RuntimeError("profile is missing")
    profile.hidden_by_moderation = True
    ctx.session.add(_system_report(user.id, text))
    return True


async def check_like_message(ctx: Ctx, user: User, text: str) -> None:
    """Filter for a message with a like; underage hints there are blocked and reported."""
    await check_field(ctx, user, text, ContentField.like_message)
    age = rules.detect_age_mention(text)
    if age is not None and age < ADULT_AGE and await _pool(ctx, user) is Pool.adult:
        ctx.session.add(_system_report(user.id, text))
        await ctx.session.commit()
        raise DomainError(
            ErrorCode.content_blocked,
            {"field": ContentField.like_message.value, "reason": ContentBlockReason.age_mismatch},
        )


async def register_message(ctx: Ctx, user: User, recipient_id: int, text: str) -> None:
    """Same text to DUP_MESSAGE_THRESHOLD people in a day -> shadow ban (no commit)."""
    digest = hashlib.sha1(rules.normalize(text).encode()).hexdigest()  # noqa: S324 - not security
    key = f"dup:msg:{digest}:{time.kyiv_today():%Y%m%d}"
    await aw(ctx.redis.sadd(key, recipient_id))
    await aw(ctx.redis.expire(key, TWO_DAYS))
    if await aw(ctx.redis.scard(key)) >= DUP_MESSAGE_THRESHOLD and not user.shadow_banned:
        user.shadow_banned = True
        await add_risk(ctx, user, RISK_SPAM)


async def check_rhythm(ctx: Ctx, user: User) -> None:
    """Reactions <= RAPID_REACTION_INTERVAL_S apart for RAPID_REACTION_STREAK_S -> rate_limited."""
    key = f"rate:react:{user.id}"
    now = time.now().timestamp()
    await aw(ctx.redis.zadd(key, {str(now): now}))
    await aw(ctx.redis.zremrangebyscore(key, 0, now - 2 * RAPID_REACTION_STREAK_S))
    await aw(ctx.redis.expire(key, 2 * RAPID_REACTION_STREAK_S))
    stamps = sorted(
        float(s)
        for s in await aw(ctx.redis.zrangebyscore(key, now - RAPID_REACTION_STREAK_S - 1, now))
    )
    covers = bool(stamps) and now - stamps[0] >= RAPID_REACTION_STREAK_S
    tight = all(b - a <= RAPID_REACTION_INTERVAL_S for a, b in itertools.pairwise(stamps))
    if covers and tight:
        await ctx.redis.delete(key)
        await add_risk(ctx, user, RISK_RHYTHM)
        await ctx.session.commit()
        raise DomainError(ErrorCode.rate_limited)


async def new_captcha(ctx: Ctx, user: User) -> CaptchaChallenge:
    """Six different emoji, one is the target; lives CAPTCHA_TTL_SECONDS."""
    if not await captcha_required(ctx, user):
        raise DomainError(ErrorCode.conflict, message="captcha is not required")
    rng = secrets.SystemRandom()
    options = rng.sample(EMOJI, CAPTCHA_OPTIONS)
    target = rng.choice(options)
    challenge_id = uuid.uuid4().hex
    key = f"captcha:{challenge_id}"
    await aw(ctx.redis.hset(key, mapping={"user_id": user.id, "target": target}))
    await aw(ctx.redis.expire(key, CAPTCHA_TTL_SECONDS))
    return CaptchaChallenge(challenge_id=challenge_id, target_emoji=target, options=options)


async def verify_captcha(ctx: Ctx, user: User, challenge_id: str, answer: str) -> UserState:
    """Right: passed, risk -30. Wrong: one more failure (3 in a row -> +10 risk)."""
    from svoi_api.domains.users import service as users  # noqa: PLC0415 - cycle

    key = f"captcha:{challenge_id}"
    data = await aw(ctx.redis.hgetall(key))
    if not data or int(data[b"user_id"]) != user.id:
        raise DomainError(ErrorCode.not_found, message="captcha expired")
    await ctx.redis.delete(key)
    fails_key = f"captcha:fails:{user.id}"
    if answer == data[b"target"].decode():
        user.captcha_passed_at = time.now()
        user.risk_score = max(0, user.risk_score - CAPTCHA_PASS_BONUS)
        await ctx.redis.delete(fails_key)
    elif await aw(ctx.redis.incr(fails_key)) >= CAPTCHA_FAILS_RISK:
        await ctx.redis.delete(fails_key)
        await add_risk(ctx, user, RISK_CAPTCHA_FAILS)
    await ctx.session.commit()
    return await users.state(ctx, user)
