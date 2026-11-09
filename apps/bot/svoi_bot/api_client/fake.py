"""FakeApiClient: in-memory API on seed fixtures for tests and BOT_USE_FAKE_API=true.

It validates every request against the contract (ContractViolation on garbage) and follows
the rules tech.md states for each endpoint closely enough for bot slices to be tested.
"""

import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from svoi_contracts.api.admin import AdminActionIn, AdminQueueItem, AdminUserOut, MetricsOut
from svoi_contracts.api.catalog import (
    CategoryOut,
    CityOut,
    CustomInterestIn,
    CustomInterestOut,
    GoalOut,
    InstitutionOut,
    InterestOut,
    PromptOut,
)
from svoi_contracts.api.feed import ExpandIn, FeedEmpty, FeedItem
from svoi_contracts.api.likes import (
    ContactOut,
    CountOut,
    IncomingLike,
    NoIncoming,
    RespondIn,
    RespondOut,
)
from svoi_contracts.api.moderation import BlockIn, ReportIn
from svoi_contracts.api.prefs import FiltersIn, FiltersOut, SettingsIn, SettingsOut
from svoi_contracts.api.profile import (
    AgeIn,
    CityIn,
    ClarificationOut,
    GenderIn,
    GoalsIn,
    HeightIn,
    InstitutionIn,
    InterestsIn,
    MediaIn,
    MediaOrderIn,
    NameIn,
    NoteIn,
    OptionOut,
    PromptsIn,
    SkipIn,
)
from svoi_contracts.api.reactions import MessageMedia, ReactionIn, ReactionOut
from svoi_contracts.api.referral import ReferralOut
from svoi_contracts.api.safety import CaptchaAnswerIn, CaptchaChallenge
from svoi_contracts.api.users import LangIn, StartIn
from svoi_contracts.api.verification import GestureOut, VerificationIn, VerificationOut
from svoi_contracts.cards import (
    CommonBlock,
    Counters,
    Icebreaker,
    InterestChip,
    Limits,
    MatchResult,
    MediaRef,
    Page,
    ProfileCard,
    ProfileCardShort,
    PromptAnswer,
    UserState,
)
from svoi_contracts.constants import (
    ADULT_AGE,
    AGE_MAX,
    AGE_MIN,
    CAPTCHA_OPTIONS,
    CLARIFICATIONS_MAX,
    DEFAULT_AGE_RANGE_DELTA,
    HEIGHT_CM,
    INTERESTS_COUNT,
    MEDIA_MAX,
    MESSAGES_PER_DAY,
    NAME_LEN,
    QUIET_HOURS_DEFAULT,
    REACTIONS_PER_DAY,
    REFERRAL_BONUS_REACTIONS,
)
from svoi_contracts.enums import (
    AdminQueueKind,
    ContentBlockReason,
    ContentField,
    FeedEmptyReason,
    Gender,
    GenderFilter,
    GestureCode,
    GoalCode,
    IcebreakerTemplate,
    InstitutionType,
    Lang,
    LikeDecision,
    MediaKind,
    ModerationStatus,
    NotifyFrequency,
    OnboardingStep,
    Pool,
    RadiusMode,
    ReactionType,
    UserStatus,
)
from svoi_contracts.errors import ApiError, ErrorCode

from svoi_bot.api_client import fixtures
from svoi_bot.api_client.base import OPS, ApiClient, Op
from svoi_bot.api_client.errors import ApiException, ApiTimeout, ContractViolation

STEPS = list(OnboardingStep)
REQUIRED = ("age", "name", "gender", "city", "goals", "interests")
POOL_BOUNDS = {Pool.minor: (16, 17), Pool.adult: (18, 99)}
RADIUS_ORDER = [
    RadiusMode.city,
    RadiusMode.km25,
    RadiusMode.km50,
    RadiusMode.km100,
    RadiusMode.region,
    RadiusMode.country,
    RadiusMode.any_online,
]
CAPTCHA_EMOJI = ("🍎", "🚗", "🐶", "⚽", "🎸", "🌙")
LOCATION_MAX_KM = 50.0
NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
DEMO_ID_FLOOR = 900_000_000  # seed demo users start here (svoi_api.seed.profiles)
_LINK = re.compile(r"(https?://|t\.me/|www\.|\.(com|ua|net|org)\b)", re.IGNORECASE)
_MENTION = re.compile(r"@\w")
_PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")


@dataclass(frozen=True)
class Call:
    """One recorded request, for asserts in bot tests."""

    name: str
    tg_id: int | None
    body: BaseModel | None
    params: dict[str, Any] | None
    path: dict[str, Any] | None


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _SearchCities(_Params):
    q: str = Field(min_length=2)
    limit: int = Field(default=5, ge=1)


class _ByLocation(_Params):
    lat: float
    lon: float


class _CategoryId(_Params):
    category_id: int


class _SearchInstitutions(_Params):
    city_id: int
    q: str = ""
    limit: int = Field(default=8, ge=1)


class _Contacts(_Params):
    cursor: str | None = None
    limit: int = Field(default=20, ge=1)


class _AdminQueue(_Params):
    kind: str = Field(pattern="^(" + "|".join(k.value for k in AdminQueueKind) + ")$")


class _Metrics(_Params):
    days: int = Field(default=7, ge=1, le=90)


PARAMS: dict[str, type[_Params]] = {
    "search_cities": _SearchCities,
    "city_by_location": _ByLocation,
    "get_interests": _CategoryId,
    "search_institutions": _SearchInstitutions,
    "get_contacts": _Contacts,
    "admin_queue": _AdminQueue,
    "admin_metrics": _Metrics,
}


@dataclass
class FakeUser:
    """Server-side state of one user."""

    id: int
    tg_id: int
    tg_username: str | None
    tg_first_name: str | None
    referral_code: str
    lang: Lang = Lang.uk
    status: UserStatus = UserStatus.onboarding
    step: OnboardingStep = OnboardingStep.lang
    has_photo: bool = False
    referred_by: int | None = None
    age: int | None = None
    age_rejected: bool = False
    age_edits: int = 0
    name: str | None = None
    gender: Gender | None = None
    city_id: int | None = None
    geo: tuple[float, float] | None = None
    goals: list[GoalCode] = field(default_factory=list)
    interests: dict[int, str | None] = field(default_factory=dict)
    institution_id: int | None = None
    height_cm: int | None = None
    prompts: list[tuple[int, str]] = field(default_factory=list)
    media: list[MediaRef] = field(default_factory=list)
    banned_until: datetime | None = None
    banned_forever: bool = False
    captcha_required: bool = False
    verified: bool = False
    filters: FiltersOut | None = None
    settings: SettingsOut | None = None
    shown: list[int] = field(default_factory=list)
    reacted: dict[int, ReactionType] = field(default_factory=dict)
    current: int | None = None
    last_skip: int | None = None
    reactions_left: int = REACTIONS_PER_DAY
    messages_left: int = MESSAGES_PER_DAY
    invited: int = 0

    @property
    def pool(self) -> Pool | None:
        """Pool follows age, as the DB check requires."""
        if self.age is None:
            return None
        return Pool.adult if self.age >= ADULT_AGE else Pool.minor


@dataclass
class FakeLike:
    id: int
    from_id: int
    to_id: int
    message: str | None
    media: MessageMedia | None
    status: str = "pending"


@dataclass
class FakeMatch:
    id: int
    a: int
    b: int
    removed: bool = False
    created_at: datetime = NOW


@dataclass
class FakeVerification:
    id: int
    user_id: int
    gesture: GestureCode
    file_id: str | None = None
    status: ModerationStatus | None = None


@dataclass
class QueueEntry:
    item: AdminQueueItem
    done: bool = False


def _error(
    code: ErrorCode, message: str = "", details: dict[str, Any] | None = None
) -> ApiException:
    return ApiException(ApiError(code=code, message=message or code.value, details=details))


def _need[T](value: T | None) -> T:
    """Narrow Optional state the handler already checked; a None here is a fake bug."""
    if value is None:
        raise RuntimeError("FakeApiClient state is inconsistent")
    return value


def _blocked_reason(text: str) -> ContentBlockReason | None:
    if _LINK.search(text):
        return ContentBlockReason.link
    if _MENTION.search(text):
        return ContentBlockReason.mention
    if _PHONE.search(text):
        return ContentBlockReason.phone
    return None


def _content_blocked(text: str, where: ContentField) -> None:
    reason = _blocked_reason(text)
    if reason is not None:
        raise _error(
            ErrorCode.content_blocked, details={"field": where.value, "reason": reason.value}
        )


class FakeApiClient(ApiClient):
    """In-memory API. Tests drive it through the same methods the bot uses."""

    def __init__(self, admin_ids: set[int] | None = None, *, demo_users: bool = True) -> None:
        self.data = fixtures.load()
        self.calls: list[Call] = []
        self.admin_ids = set(admin_ids or ())
        self.users: dict[int, FakeUser] = {}
        self.likes: list[FakeLike] = []
        self.matches: list[FakeMatch] = []
        self.reports: set[tuple[int, int]] = set()
        self.blocks: set[tuple[int, int]] = set()
        self.queue: list[QueueEntry] = []
        self.admin_actions: list[AdminActionIn] = []
        self.bot_blocked: set[int] = set()
        self.sent_notifications: list[str] = []
        self.custom_tags: list[str] = []
        self.verifications: list[FakeVerification] = []
        self.captchas: dict[str, tuple[int, str]] = {}
        self._fail: dict[str, list[ApiError]] = {}
        self._timeout: dict[str, int] = {}
        self._next_id = 1
        self._cities = {c["id"]: c for c in self.data.cities}
        self._interests = {i["id"]: i for i in self.data.interests}
        self._prompts = {p["id"]: p for p in self.data.prompts}
        self._institutions = {i["id"]: i for i in self.data.institutions}
        self._clarifications = {c["interest_id"]: c for c in self.data.clarifications}
        if demo_users:
            for row in self.data.profiles:
                self._add_demo(row)

    # ---- test controls ---------------------------------------------------------------

    def fail_next(self, method: str, error: ApiError) -> None:
        """The next call of `method` raises ApiException(error)."""
        self._check_name(method)
        self._fail.setdefault(method, []).append(error)

    def timeout_next(self, method: str) -> None:
        """The next call of `method` raises ApiTimeout."""
        self._check_name(method)
        self._timeout[method] = self._timeout.get(method, 0) + 1

    def user(self, tg_id: int) -> FakeUser:
        """Server-side state for asserts and setup."""
        return self.users[tg_id]

    def demo_tg_ids(self, pool: Pool | None = None) -> list[int]:
        """Seeded demo users, optionally of one pool."""
        return [
            u.tg_id
            for u in self.users.values()
            if u.id >= DEMO_ID_FLOOR and (pool is None or u.pool is pool)
        ]

    def add_like(
        self,
        from_tg: int,
        to_tg: int,
        message: str | None = None,
        media: MessageMedia | None = None,
    ) -> int:
        """Seed an incoming like; returns its id."""
        like = FakeLike(self._id(), self.users[from_tg].id, self.users[to_tg].id, message, media)
        self.likes.append(like)
        return like.id

    def ban(self, tg_id: int, until: datetime | None = None) -> None:
        """Ban a user; None means forever."""
        user = self.users[tg_id]
        user.status = UserStatus.banned
        user.banned_until = until
        user.banned_forever = until is None

    def require_captcha(self, tg_id: int) -> None:
        """Flag a user as suspicious."""
        self.users[tg_id].captcha_required = True

    def expire_captchas(self) -> None:
        """Simulate CAPTCHA_TTL_SECONDS passing."""
        self.captchas.clear()

    def approve_media(self, tg_id: int) -> None:
        """Moderation approves every pending photo of a user."""
        user = self.users[tg_id]
        user.media = [
            m.model_copy(update={"moderation_status": ModerationStatus.approved})
            for m in user.media
        ]

    def add_queue_item(self, item: AdminQueueItem) -> None:
        """Put an item into a moderation queue."""
        self.queue.append(QueueEntry(item))

    def onboard(
        self,
        tg_id: int,
        *,
        age: int = 19,
        city_id: int = 700918,
        lang: Lang = Lang.uk,
        username: str | None = "tester",
    ) -> FakeUser:
        """Create an active user with a complete profile."""
        user = self._new_user(tg_id, username, "Тест", lang)
        user.age, user.name, user.gender, user.city_id = age, "Тест", Gender.male, city_id
        user.goals = [GoalCode.friends]
        user.interests = {i["id"]: None for i in self.data.interests[:3]}
        self._finish(user)
        return user

    # ---- transport -------------------------------------------------------------------

    async def aclose(self) -> None:
        """Nothing to close."""

    def _check_name(self, method: str) -> None:
        if method not in OPS:
            raise ValueError(f"unknown ApiClient method {method!r}")

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def _call(
        self,
        op: Op,
        tg_id: int | None,
        *,
        body: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        path: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append(Call(op.name, tg_id, body, params, path))
        body = self._validate_body(op, body)
        params = self._validate_params(op, params)
        if self._timeout.get(op.name):
            self._timeout[op.name] -= 1
            raise ApiTimeout(op.name)
        if self._fail.get(op.name):
            raise ApiException(self._fail[op.name].pop(0))
        handler: Callable[..., Awaitable[Any]] = getattr(self, f"_h_{op.name}")
        if op.internal:
            return await handler(**(path or {}))
        tg_id = _need(tg_id)
        if op.name != "start":
            user = self.users.get(tg_id)
            if user is None:
                raise _error(ErrorCode.not_found, "unknown user")
            if user.status is UserStatus.banned and op.name != "get_me":
                until = None if user.banned_until is None else user.banned_until.isoformat()
                raise _error(ErrorCode.banned, details={"until": until})
        result = await handler(tg_id, body=body, params=params or {}, path=path or {})
        adapter = op.adapter()
        # the fake must answer exactly what the contract promises
        return None if adapter is None else adapter.validate_python(result)

    @staticmethod
    def _validate_body(op: Op, body: BaseModel | None) -> BaseModel | None:
        if op.body is None:
            if body is not None:
                raise ContractViolation(f"{op.name} takes no body")
            return None
        if type(body) is not op.body:
            raise ContractViolation(f"{op.name} expects {op.body.__name__}, got {type(body)!r}")
        try:
            return op.body.model_validate_json(body.model_dump_json())
        except (ValidationError, ValueError) as exc:
            raise ContractViolation(f"{op.name}: {exc}") from exc

    @staticmethod
    def _validate_params(op: Op, params: dict[str, Any] | None) -> dict[str, Any] | None:
        schema = PARAMS.get(op.name)
        if schema is None:
            if params:
                raise ContractViolation(f"{op.name} takes no query parameters")
            return None
        try:
            return schema.model_validate(params or {}).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise ContractViolation(f"{op.name}: {exc}") from exc

    # ---- helpers ---------------------------------------------------------------------

    def _new_user(
        self, tg_id: int, username: str | None, first_name: str | None, lang: Lang
    ) -> FakeUser:
        user = FakeUser(self._id(), tg_id, username, first_name, f"R{tg_id}", lang=lang)
        self.users[tg_id] = user
        return user

    def _add_demo(self, row: dict[str, Any]) -> None:
        u, p = row["user"], row["profile"]
        user = FakeUser(
            u["id"],
            u["tg_id"],
            u["tg_username"],
            u["tg_first_name"],
            u["referral_code"],
            lang=Lang(u["lang"]),
            status=UserStatus.active,
            step=OnboardingStep.done,
        )
        user.age, user.name, user.gender = p["age"], p["name"], Gender(p["gender"])
        user.city_id, user.institution_id, user.height_cm = (
            p["city_id"],
            p["institution_id"],
            p["height_cm"],
        )
        user.goals = [GoalCode(g) for g in row["goals"]]
        user.interests = {i["interest_id"]: i["note_key"] for i in row["interests"]}
        user.prompts = [(x["prompt_id"], x["text"]) for x in row["prompts"]]
        user.filters, user.settings = self._default_filters(user), self._default_settings()
        self.users[user.tg_id] = user

    def _by_id(self, user_id: int) -> FakeUser:
        for user in self.users.values():
            if user.id == user_id:
                return user
        raise _error(ErrorCode.not_found)

    def _state(self, user: FakeUser) -> UserState:
        pending = sum(
            1 for like in self.likes if like.to_id == user.id and like.status == "pending"
        )
        return UserState(
            user_id=user.id,
            tg_id=user.tg_id,
            status=user.status,
            lang=user.lang,
            onboarding_step=user.step,
            pool=user.pool,
            needs_username=user.tg_username is None,
            captcha_required=user.captcha_required,
            is_admin=user.tg_id in self.admin_ids,
            counters=Counters(incoming_likes=pending),
        )

    def _put_step(self, user: FakeUser, step: OnboardingStep) -> None:
        """A PUT for the current step advances; past steps edit; future steps conflict."""
        if user.status is not UserStatus.onboarding:
            return
        if STEPS.index(step) > STEPS.index(user.step):
            raise _error(ErrorCode.conflict, f"current step is {user.step}")
        if step is user.step:
            user.step = STEPS[STEPS.index(step) + 1]

    @staticmethod
    def _t(row: dict[str, Any], key: str, lang: Lang) -> str:
        value: str = row[f"{key}_{lang.value}"]
        return value

    def _city_out(self, row: dict[str, Any], lang: Lang) -> CityOut:
        return CityOut(
            id=row["id"],
            name=self._t(row, "name", lang),
            region=self._t(row, "region", lang),
            country_code=row["country_code"],
        )

    def _missing(self, user: FakeUser) -> list[str]:
        have = {
            "age": user.age,
            "name": user.name,
            "gender": user.gender,
            "city": user.city_id,
            "goals": user.goals or None,
            "interests": user.interests if len(user.interests) >= INTERESTS_COUNT[0] else None,
        }
        return [k for k in REQUIRED if have[k] is None]

    def _default_filters(self, user: FakeUser) -> FiltersOut:
        age, pool = _need(user.age), _need(user.pool)
        low, high = POOL_BOUNDS[pool]
        return FiltersOut(
            age_min=max(low, age - DEFAULT_AGE_RANGE_DELTA),
            age_max=min(high, age + DEFAULT_AGE_RANGE_DELTA),
            age_bounds=(low, high),
            gender=GenderFilter.all,
            radius=RadiusMode.city,
            verified_only=False,
        )

    @staticmethod
    def _default_settings() -> SettingsOut:
        return SettingsOut(
            notify_frequency=NotifyFrequency.instant,
            quiet_from=time.fromisoformat(QUIET_HOURS_DEFAULT[0]),
            quiet_to=time.fromisoformat(QUIET_HOURS_DEFAULT[1]),
            show_distance=True,
            show_institution=True,
        )

    def _finish(self, user: FakeUser) -> None:
        user.status, user.step = UserStatus.active, OnboardingStep.done
        user.filters = user.filters or self._default_filters(user)
        user.settings = user.settings or self._default_settings()
        if user.referred_by is not None:
            referrer = self._by_id(user.referred_by)
            referrer.invited += 1
            referrer.reactions_left += REFERRAL_BONUS_REACTIONS
            user.reactions_left += REFERRAL_BONUS_REACTIONS

    def _completeness(self, user: FakeUser) -> int:
        optional = [user.media, user.prompts, user.institution_id, user.height_cm]
        return 60 + 10 * sum(1 for x in optional if x)

    def _card(self, owner: FakeUser, viewer: FakeUser, mode: str) -> ProfileCard:
        lang = viewer.lang
        own = owner.id == viewer.id
        common_ids = set(owner.interests) & set(viewer.interests) if not own else set()
        chips = []
        for interest_id, note in sorted(
            owner.interests.items(), key=lambda kv: (kv[0] not in common_ids, kv[0])
        ):
            row = self._interests.get(interest_id)
            if row is None:
                continue
            note_title = None
            if note is not None and interest_id in self._clarifications:
                options = self._clarifications[interest_id]["options"]
                note_title = next(
                    (self._t(o, "title", lang) for o in options if o["key"] == note), None
                )
            chips.append(
                InterestChip(
                    id=interest_id,
                    title=self._t(row, "title", lang),
                    note=note_title,
                    common=interest_id in common_ids,
                )
            )
        common = None
        if mode in ("feed", "incoming"):
            union = set(owner.interests) | set(viewer.interests)
            same_inst = owner.institution_id is not None and (
                owner.institution_id == viewer.institution_id
            )
            common = CommonBlock(
                interest_titles=[c.title for c in chips if c.common],
                same_institution=same_inst,
                match_percent=round(100 * len(common_ids) / len(union)) if union else 0,
            )
        media = (
            owner.media
            if own or mode == "admin"
            else [m for m in owner.media if m.moderation_status is ModerationStatus.approved]
        )
        institution = self._institutions.get(owner.institution_id or -1)
        name, age, city_id = _need(owner.name), _need(owner.age), _need(owner.city_id)
        return ProfileCard(
            user_id=owner.id,
            name=name,
            age=age,
            verified=owner.verified,
            gender=None if owner.gender is Gender.hidden else owner.gender,
            city_name=self._t(self._cities[city_id], "name", lang),
            distance=None,
            goals=list(owner.goals),
            interests=chips,
            institution_name=None
            if institution is None
            else (institution["short_name"] or institution["name"]),
            height_cm=owner.height_cm,
            prompts=[
                PromptAnswer(
                    prompt_id=pid, title=self._t(self._prompts[pid], "title", lang), text=text
                )
                for pid, text in owner.prompts
            ],
            media=list(media),
            common=common,
            completeness=self._completeness(owner) if own else None,
        )

    def _short(self, owner: FakeUser, lang: Lang) -> ProfileCardShort:
        name, age, city_id = _need(owner.name), _need(owner.age), _need(owner.city_id)
        return ProfileCardShort(
            user_id=owner.id,
            name=name,
            age=age,
            city_name=self._t(self._cities[city_id], "name", lang),
        )

    def _limits(self, user: FakeUser) -> Limits:
        return Limits(
            reactions_left=user.reactions_left,
            messages_left=user.messages_left,
            resets_at=NOW + timedelta(days=1),
        )

    def _blocked_between(self, a: int, b: int) -> bool:
        return (a, b) in self.blocks or (b, a) in self.blocks

    # ---- S1 ----------------------------------------------------------------------------

    async def _h_start(self, tg_id: int, body: StartIn, **_: Any) -> UserState:
        user = self.users.get(tg_id)
        if user is None:
            code = body.tg_language_code or ""
            lang = Lang(code) if code in {lang.value for lang in Lang} else Lang.uk
            user = self._new_user(tg_id, body.tg_username, body.tg_first_name, lang)
            user.has_photo = body.has_tg_profile_photo
            if body.referral_code:
                referrer = next(
                    (u for u in self.users.values() if u.referral_code == body.referral_code), None
                )
                user.referred_by = None if referrer is None else referrer.id
        else:
            user.tg_username, user.tg_first_name = body.tg_username, body.tg_first_name
        if user.status is UserStatus.banned:
            until = None if user.banned_until is None else user.banned_until.isoformat()
            raise _error(ErrorCode.banned, details={"until": until})
        return self._state(user)

    async def _h_get_me(self, tg_id: int, **_: Any) -> UserState:
        return self._state(self.users[tg_id])

    async def _h_set_lang(self, tg_id: int, body: LangIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        user.lang = body.lang
        self._put_step(user, OnboardingStep.lang)
        return self._state(user)

    async def _h_consent(self, tg_id: int, **_: Any) -> UserState:
        user = self.users[tg_id]
        if user.step is not OnboardingStep.consent:
            raise _error(ErrorCode.conflict, "consent is not the current step")
        self._put_step(user, OnboardingStep.consent)
        return self._state(user)

    async def _h_set_age(self, tg_id: int, body: AgeIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        if STEPS.index(user.step) < STEPS.index(OnboardingStep.age) and (
            user.status is UserStatus.onboarding
        ):
            raise _error(ErrorCode.conflict, f"current step is {user.step}")
        if user.age_rejected or (user.age is not None and user.age_edits >= 1):
            raise _error(ErrorCode.age_locked)
        if body.age < AGE_MIN:
            user.age_rejected = True
            raise _error(ErrorCode.age_too_young)
        if body.age > AGE_MAX:
            raise _error(ErrorCode.validation_error, "age above AGE_MAX")
        if user.age is not None:
            user.age_edits += 1
        user.age = body.age
        self._put_step(user, OnboardingStep.age)
        return self._state(user)

    async def _h_set_name(self, tg_id: int, body: NameIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        name = body.name.strip()
        _content_blocked(name, ContentField.name)
        if not NAME_LEN[0] <= len(name) <= NAME_LEN[1] or any(ch.isdigit() for ch in name):
            raise _error(ErrorCode.validation_error, "name: 2-20 letters, no digits")
        user.name = name
        self._put_step(user, OnboardingStep.name)
        return self._state(user)

    async def _h_set_gender(self, tg_id: int, body: GenderIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        user.gender = body.gender
        self._put_step(user, OnboardingStep.gender)
        return self._state(user)

    async def _h_skip_step(self, tg_id: int, body: SkipIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        optional = {
            OnboardingStep.clarify,
            OnboardingStep.institution,
            OnboardingStep.height,
            OnboardingStep.prompts,
            OnboardingStep.media,
        }
        if body.step not in optional or body.step is not user.step:
            raise _error(ErrorCode.conflict, f"cannot skip {body.step}")
        user.step = STEPS[STEPS.index(user.step) + 1]
        return self._state(user)

    # ---- S2 ----------------------------------------------------------------------------

    async def _h_search_cities(self, tg_id: int, params: dict[str, Any], **_: Any) -> list[CityOut]:
        lang = self.users[tg_id].lang
        q = params["q"].casefold().replace("'", "’")
        names = ("name_uk", "name_ru", "name_en")
        hits = [c for c in self.data.cities if any(q in c[n].casefold() for n in names)]
        hits.sort(
            key=lambda c: (not any(c[n].casefold().startswith(q) for n in names), -c["population"])
        )
        return [self._city_out(c, lang) for c in hits[: params["limit"]]]

    async def _h_city_by_location(self, tg_id: int, params: dict[str, Any], **_: Any) -> CityOut:
        lat, lon = params["lat"], params["lon"]

        def km(c: dict[str, Any]) -> float:
            dlat, dlon = math.radians(c["lat"] - lat), math.radians(c["lon"] - lon)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat))
                * math.cos(math.radians(c["lat"]))
                * math.sin(dlon / 2) ** 2
            )
            return 6371 * 2 * math.asin(math.sqrt(a))

        nearest = min(self.data.cities, key=km)
        if km(nearest) > LOCATION_MAX_KM:
            raise _error(ErrorCode.not_found, "no city nearby")
        return self._city_out(nearest, self.users[tg_id].lang)

    async def _h_set_city(self, tg_id: int, body: CityIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        if body.city_id not in self._cities:
            raise _error(ErrorCode.not_found, "unknown city")
        user.city_id = body.city_id
        user.geo = (
            None
            if body.lat is None or body.lon is None
            else (round(body.lat, 2), round(body.lon, 2))
        )
        self._put_step(user, OnboardingStep.city)
        return self._state(user)

    # ---- S3 ----------------------------------------------------------------------------

    async def _h_get_goals(self, tg_id: int, **_: Any) -> list[GoalOut]:
        lang = self.users[tg_id].lang
        return [
            GoalOut(code=g["code"], title=self._t(g, "title", lang), emoji=g["emoji"])
            for g in self.data.goals
        ]

    async def _h_set_goals(self, tg_id: int, body: GoalsIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        user.goals = [g for g in GoalCode if g in set(body.codes)]
        self._put_step(user, OnboardingStep.goals)
        return self._state(user)

    async def _h_get_categories(self, tg_id: int, **_: Any) -> list[CategoryOut]:
        lang = self.users[tg_id].lang
        rows = sorted(
            (c for c in self.data.categories if not c["hidden"]), key=lambda c: c["position"]
        )
        return [
            CategoryOut(
                id=c["id"], code=c["code"], emoji=c["emoji"], title=self._t(c, "title", lang)
            )
            for c in rows
        ]

    async def _h_get_interests(
        self, tg_id: int, params: dict[str, Any], **_: Any
    ) -> list[InterestOut]:
        lang = self.users[tg_id].lang
        rows = [i for i in self.data.interests if i["category_id"] == params["category_id"]]
        if not rows:
            raise _error(ErrorCode.not_found, "unknown category")
        return [
            InterestOut(id=i["id"], category_id=i["category_id"], title=self._t(i, "title", lang))
            for i in rows
        ]

    async def _h_set_interests(self, tg_id: int, body: InterestsIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        if any(i not in self._interests for i in body.interest_ids):
            raise _error(ErrorCode.validation_error, "unknown interest")
        user.interests = {i: user.interests.get(i) for i in body.interest_ids}
        self._put_step(user, OnboardingStep.interests)
        return self._state(user)

    async def _h_custom_interest(
        self, tg_id: int, body: CustomInterestIn, **_: Any
    ) -> CustomInterestOut:
        user = self.users[tg_id]
        _content_blocked(body.title, ContentField.custom_interest)
        title = body.title.strip().casefold()
        for row in self.data.interests:
            if title in {row[f"title_{lang.value}"].casefold() for lang in Lang}:
                out = InterestOut(
                    id=row["id"],
                    category_id=row["category_id"],
                    title=self._t(row, "title", user.lang),
                )
                return CustomInterestOut(matched=out, pending=False)
        self.custom_tags.append(body.title)
        return CustomInterestOut(matched=None, pending=True)

    # ---- S4 ----------------------------------------------------------------------------

    async def _h_get_clarifications(self, tg_id: int, **_: Any) -> list[ClarificationOut]:
        user = self.users[tg_id]
        rows = [
            c
            for c in self.data.clarifications
            if c["interest_id"] in user.interests and user.interests[c["interest_id"]] is None
        ]
        rows.sort(key=lambda c: -c["priority"])
        return [
            ClarificationOut(
                interest_id=c["interest_id"],
                interest_title=self._t(self._interests[c["interest_id"]], "title", user.lang),
                question_key=c["question_key"],
                options=[
                    OptionOut(key=o["key"], title=self._t(o, "title", user.lang))
                    for o in c["options"]
                ],
            )
            for c in rows[:CLARIFICATIONS_MAX]
        ]

    async def _h_set_interest_note(
        self, tg_id: int, body: NoteIn, path: dict[str, Any], **_: Any
    ) -> UserState:
        user = self.users[tg_id]
        interest_id = path["interest_id"]
        clarification = self._clarifications.get(interest_id)
        if interest_id not in user.interests or clarification is None:
            raise _error(ErrorCode.not_found)
        if body.option_key not in {o["key"] for o in clarification["options"]}:
            raise _error(ErrorCode.validation_error, "unknown option")
        user.interests[interest_id] = body.option_key
        return self._state(user)

    async def _h_search_institutions(
        self, tg_id: int, params: dict[str, Any], **_: Any
    ) -> list[InstitutionOut]:
        q = params.get("q", "").casefold()
        rows = [
            i
            for i in self.data.institutions
            if i["city_id"] == params["city_id"]
            and (not q or q in i["name"].casefold() or q in (i["short_name"] or "").casefold())
        ]
        return [
            InstitutionOut(
                id=i["id"],
                name=i["name"],
                short_name=i["short_name"],
                type=InstitutionType(i["type"]),
            )
            for i in rows[: params["limit"]]
        ]

    async def _h_set_institution(self, tg_id: int, body: InstitutionIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        if body.institution_id is not None and body.institution_id not in self._institutions:
            raise _error(ErrorCode.not_found)
        user.institution_id = body.institution_id
        self._put_step(user, OnboardingStep.institution)
        return self._state(user)

    async def _h_set_height(self, tg_id: int, body: HeightIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        if body.height_cm is not None and not HEIGHT_CM[0] <= body.height_cm <= HEIGHT_CM[1]:
            raise _error(ErrorCode.validation_error, "height out of range")
        user.height_cm = body.height_cm
        self._put_step(user, OnboardingStep.height)
        return self._state(user)

    async def _h_get_prompts(self, tg_id: int, **_: Any) -> list[PromptOut]:
        lang = self.users[tg_id].lang
        return [PromptOut(id=p["id"], title=self._t(p, "title", lang)) for p in self.data.prompts]

    async def _h_set_prompts(self, tg_id: int, body: PromptsIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        for answer in body.answers:
            if answer.prompt_id not in self._prompts:
                raise _error(ErrorCode.validation_error, "unknown prompt")
            _content_blocked(answer.text, ContentField.prompt)
        user.prompts = [(a.prompt_id, a.text) for a in body.answers]
        self._put_step(user, OnboardingStep.prompts)
        return self._state(user)

    async def _h_add_media(self, tg_id: int, body: MediaIn, **_: Any) -> MediaRef:
        user = self.users[tg_id]
        if len(user.media) >= MEDIA_MAX:
            raise _error(ErrorCode.media_limit)
        ref = MediaRef(
            id=self._id(),
            kind=body.kind,
            file_id=body.file_id,
            moderation_status=ModerationStatus.pending,
        )
        user.media.append(ref)
        return ref

    async def _h_delete_media(self, tg_id: int, path: dict[str, Any], **_: Any) -> UserState:
        user = self.users[tg_id]
        before = len(user.media)
        user.media = [m for m in user.media if m.id != path["media_id"]]
        if len(user.media) == before:
            raise _error(ErrorCode.not_found)
        return self._state(user)

    async def _h_reorder_media(self, tg_id: int, body: MediaOrderIn, **_: Any) -> list[MediaRef]:
        user = self.users[tg_id]
        by_id = {m.id: m for m in user.media}
        if sorted(body.ids) != sorted(by_id):
            raise _error(ErrorCode.validation_error, "ids must list every media once")
        user.media = [by_id[i] for i in body.ids]
        return list(user.media)

    async def _h_complete_onboarding(self, tg_id: int, **_: Any) -> UserState:
        user = self.users[tg_id]
        missing = self._missing(user)
        if missing:
            raise _error(ErrorCode.profile_incomplete, details={"missing": missing})
        self._finish(user)
        return self._state(user)

    # ---- S5 ----------------------------------------------------------------------------

    async def _h_get_my_card(self, tg_id: int, **_: Any) -> ProfileCard:
        user = self.users[tg_id]
        missing = [m for m in self._missing(user) if m in ("age", "name", "city")]
        if missing:
            raise _error(ErrorCode.profile_incomplete, details={"missing": missing})
        return self._card(user, user, "own")

    async def _h_reset_profile(self, tg_id: int, **_: Any) -> UserState:
        user = self.users[tg_id]
        user.status, user.step = UserStatus.onboarding, OnboardingStep.age
        return self._state(user)

    async def _h_hide_profile(self, tg_id: int, **_: Any) -> UserState:
        user = self.users[tg_id]
        user.status = UserStatus.hidden
        return self._state(user)

    async def _h_unhide_profile(self, tg_id: int, **_: Any) -> UserState:
        user = self.users[tg_id]
        if user.status is not UserStatus.hidden:
            raise _error(ErrorCode.conflict, "profile is not hidden")
        user.status = UserStatus.active
        return self._state(user)

    async def _h_delete_me(self, tg_id: int, **_: Any) -> None:
        user = self.users.pop(tg_id)
        self.likes = [x for x in self.likes if user.id not in (x.from_id, x.to_id)]
        for match in self.matches:
            if user.id in (match.a, match.b):
                match.removed = True

    # ---- S6 ----------------------------------------------------------------------------

    def _active(self, tg_id: int) -> FakeUser:
        user = self.users[tg_id]
        if user.filters is None or user.settings is None:
            raise _error(ErrorCode.profile_incomplete, details={"missing": self._missing(user)})
        return user

    async def _h_get_filters(self, tg_id: int, **_: Any) -> FiltersOut:
        return _need(self._active(tg_id).filters)

    async def _h_set_filters(self, tg_id: int, body: FiltersIn, **_: Any) -> FiltersOut:
        user = self._active(tg_id)
        low, high = _need(user.filters).age_bounds
        if not low <= body.age_min <= body.age_max <= high:
            raise _error(ErrorCode.validation_error, "age range outside pool bounds")
        user.filters = FiltersOut(age_bounds=(low, high), **body.model_dump())
        return user.filters

    async def _h_get_settings(self, tg_id: int, **_: Any) -> SettingsOut:
        return _need(self._active(tg_id).settings)

    async def _h_set_settings(self, tg_id: int, body: SettingsIn, **_: Any) -> SettingsOut:
        user = self._active(tg_id)
        user.settings = SettingsOut(**body.model_dump())
        return user.settings

    # ---- S7 ----------------------------------------------------------------------------

    def _candidates(self, user: FakeUser) -> list[FakeUser]:
        filters = _need(user.filters)
        same_city = filters.radius is RadiusMode.city
        return sorted(
            (
                c
                for c in self.users.values()
                if c.id != user.id
                and c.status is UserStatus.active
                and c.pool is user.pool
                and c.id not in user.shown
                and not self._blocked_between(c.id, user.id)
                and c.age is not None
                and filters.age_min <= c.age <= filters.age_max
                and (filters.gender is GenderFilter.all or c.gender is Gender(filters.gender.value))
                and (not filters.verified_only or c.verified)
                and (not same_city or c.city_id == user.city_id)
            ),
            key=lambda c: c.id,
        )

    def _empty(self, user: FakeUser, reason: FeedEmptyReason) -> FeedEmpty:
        radius = user.filters.radius if user.filters else RadiusMode.city
        wider = [r for r in RADIUS_ORDER if RADIUS_ORDER.index(r) > RADIUS_ORDER.index(radius)]
        offered: list[RadiusMode] = [
            r
            for r in (RadiusMode.km50, RadiusMode.region, RadiusMode.country, RadiusMode.any_online)
            if r in wider
        ]
        resets = NOW + timedelta(days=1) if reason is FeedEmptyReason.limit_reached else None
        return FeedEmpty(
            reason=reason,
            expand_options=offered if reason is FeedEmptyReason.no_candidates else [],
            resets_at=resets,
        )

    async def _h_feed_next(self, tg_id: int, **_: Any) -> FeedItem | FeedEmpty:
        user = self.users[tg_id]
        if user.status is UserStatus.hidden:
            return self._empty(user, FeedEmptyReason.profile_hidden)
        if user.status is not UserStatus.active:
            return self._empty(user, FeedEmptyReason.profile_incomplete)
        if user.reactions_left <= 0:
            return self._empty(user, FeedEmptyReason.limit_reached)
        candidates = self._candidates(user)
        if not candidates:
            return self._empty(user, FeedEmptyReason.no_candidates)
        target = candidates[0]
        user.shown.append(target.id)
        user.current = target.id
        return FeedItem(card=self._card(target, user, "feed"), can_undo=user.last_skip is not None)

    async def _h_feed_expand(self, tg_id: int, body: ExpandIn, **_: Any) -> FeedItem | FeedEmpty:
        user = self._active(tg_id)
        user.filters = _need(user.filters).model_copy(update={"radius": body.radius})
        return await self._h_feed_next(tg_id)

    # ---- S8 ----------------------------------------------------------------------------

    def _match(self, a: FakeUser, b: FakeUser) -> FakeMatch:
        low, high = sorted((a.id, b.id))
        match = FakeMatch(self._id(), low, high)
        self.matches.append(match)
        return match

    def _match_result(self, match: FakeMatch, viewer: FakeUser) -> MatchResult:
        partner = self._by_id(match.b if match.a == viewer.id else match.a)
        common = sorted(set(partner.interests) & set(viewer.interests))
        icebreaker = None
        if common:
            icebreaker = Icebreaker(
                template=IcebreakerTemplate.common_interest,
                interest_title=self._t(self._interests[common[0]], "title", viewer.lang),
            )
        return MatchResult(
            match_id=match.id,
            partner=self._card(partner, viewer, "match"),
            partner_username=partner.tg_username,
            partner_tg_id=partner.tg_id,
            icebreaker=icebreaker,
        )

    async def _h_react(self, tg_id: int, body: ReactionIn, **_: Any) -> ReactionOut:
        user = self._active(tg_id)
        if user.captcha_required:
            raise _error(ErrorCode.captcha_required)
        if body.target_id not in user.shown or body.target_id in user.reacted:
            raise _error(ErrorCode.conflict, "not shown or already reacted")
        if user.reactions_left <= 0:
            raise _error(
                ErrorCode.limit_reached, details=self._limits(user).model_dump(mode="json")
            )
        if body.type is ReactionType.like_msg:
            if body.media is not None and user.pool is Pool.minor:
                raise _error(ErrorCode.media_forbidden)
            if body.message:
                _content_blocked(body.message, ContentField.like_message)
            if user.messages_left <= 0:
                raise _error(
                    ErrorCode.limit_reached, details=self._limits(user).model_dump(mode="json")
                )
            user.messages_left -= 1
        user.reactions_left -= 1
        user.reacted[body.target_id] = body.type
        user.current = None
        target = self._by_id(body.target_id)
        if body.type is ReactionType.skip:
            user.last_skip = body.target_id
            return ReactionOut(match=None, limits=self._limits(user))
        user.last_skip = None
        back = next(
            (
                x
                for x in self.likes
                if x.from_id == target.id and x.to_id == user.id and x.status == "pending"
            ),
            None,
        )
        if back is not None:
            back.status = "matched"
            match = self._match(user, target)
            return ReactionOut(match=self._match_result(match, user), limits=self._limits(user))
        self.likes.append(FakeLike(self._id(), user.id, target.id, body.message, body.media))
        return ReactionOut(match=None, limits=self._limits(user))

    async def _h_undo_reaction(self, tg_id: int, **_: Any) -> FeedItem:
        user = self._active(tg_id)
        if user.last_skip is None:
            raise _error(ErrorCode.undo_unavailable)
        target = self._by_id(user.last_skip)
        user.reacted.pop(target.id, None)
        user.last_skip = None
        user.current = target.id
        return FeedItem(card=self._card(target, user, "feed"), can_undo=False)

    async def _h_get_limits(self, tg_id: int, **_: Any) -> Limits:
        return self._limits(self.users[tg_id])

    # ---- S9 ----------------------------------------------------------------------------

    def _pending_for(self, user: FakeUser) -> list[FakeLike]:
        return [
            x
            for x in self.likes
            if x.to_id == user.id
            and x.status == "pending"
            and not self._blocked_between(x.from_id, user.id)
        ]

    async def _h_incoming_count(self, tg_id: int, **_: Any) -> CountOut:
        return CountOut(count=len(self._pending_for(self.users[tg_id])))

    async def _h_incoming_next(self, tg_id: int, **_: Any) -> IncomingLike | NoIncoming:
        user = self.users[tg_id]
        pending = self._pending_for(user)
        if not pending:
            return NoIncoming()
        like = pending[0]
        return IncomingLike(
            like_id=like.id,
            card=self._card(self._by_id(like.from_id), user, "incoming"),
            message=like.message,
            media=like.media,
        )

    async def _h_respond_like(
        self, tg_id: int, body: RespondIn, path: dict[str, Any], **_: Any
    ) -> RespondOut:
        user = self.users[tg_id]
        like = next((x for x in self.likes if x.id == path["like_id"] and x.to_id == user.id), None)
        if like is None:
            raise _error(ErrorCode.not_found)
        if like.status != "pending":
            raise _error(ErrorCode.conflict, "already answered")
        if body.decision is LikeDecision.decline:
            like.status = "declined"
            return RespondOut(match=None)
        like.status = "matched"
        match = self._match(user, self._by_id(like.from_id))
        return RespondOut(match=self._match_result(match, user))

    def _my_match(self, user: FakeUser, match_id: int) -> FakeMatch:
        match = next(
            (
                m
                for m in self.matches
                if m.id == match_id and not m.removed and user.id in (m.a, m.b)
            ),
            None,
        )
        if match is None:
            raise _error(ErrorCode.not_found)
        return match

    async def _h_get_match(self, tg_id: int, path: dict[str, Any], **_: Any) -> MatchResult:
        user = self.users[tg_id]
        return self._match_result(self._my_match(user, path["match_id"]), user)

    async def _h_get_contacts(
        self, tg_id: int, params: dict[str, Any], **_: Any
    ) -> Page[ContactOut]:
        user = self.users[tg_id]
        mine = [m for m in self.matches if not m.removed and user.id in (m.a, m.b)]
        mine.sort(key=lambda m: -m.id)
        start = int(params.get("cursor", "0"))
        chunk = mine[start : start + params["limit"]]
        items = []
        for m in chunk:
            partner = self._by_id(m.b if m.a == user.id else m.a)
            items.append(
                ContactOut(
                    match_id=m.id,
                    partner=self._short(partner, user.lang),
                    partner_username=partner.tg_username,
                    partner_tg_id=partner.tg_id,
                    matched_at=m.created_at,
                )
            )
        end = start + len(chunk)
        return Page[ContactOut](items=items, next_cursor=str(end) if end < len(mine) else None)

    async def _h_delete_contact(self, tg_id: int, path: dict[str, Any], **_: Any) -> None:
        self._my_match(self.users[tg_id], path["match_id"]).removed = True

    # ---- S10 ---------------------------------------------------------------------------

    async def _h_report(self, tg_id: int, body: ReportIn, **_: Any) -> None:
        user = self.users[tg_id]
        target = self._by_id(body.target_id)
        if (user.id, target.id) in self.reports:
            raise _error(ErrorCode.conflict, "already reported")
        if body.text:
            _content_blocked(body.text, ContentField.report_text)
        self.reports.add((user.id, target.id))
        if target.id not in user.shown:  # a reported profile never shows again
            user.shown.append(target.id)

    async def _h_block(self, tg_id: int, body: BlockIn, **_: Any) -> None:
        self.blocks.add((self.users[tg_id].id, self._by_id(body.target_id).id))

    async def _h_unblock(self, tg_id: int, path: dict[str, Any], **_: Any) -> None:
        key = (self.users[tg_id].id, path["target_id"])
        if key not in self.blocks:
            raise _error(ErrorCode.not_found)
        self.blocks.discard(key)

    def _admin(self, tg_id: int) -> FakeUser:
        if tg_id not in self.admin_ids:
            raise _error(ErrorCode.forbidden)
        return self.users[tg_id]

    async def _h_admin_queue(
        self, tg_id: int, params: dict[str, Any], **_: Any
    ) -> AdminQueueItem | None:
        self._admin(tg_id)
        kind = AdminQueueKind(params["kind"])
        entry = next((e for e in self.queue if not e.done and e.item.kind is kind), None)
        return None if entry is None else entry.item

    async def _h_admin_queue_stats(self, tg_id: int, **_: Any) -> dict[AdminQueueKind, int]:
        self._admin(tg_id)
        return {
            k: sum(1 for e in self.queue if not e.done and e.item.kind is k) for k in AdminQueueKind
        }

    async def _h_admin_action(self, tg_id: int, body: AdminActionIn, **_: Any) -> None:
        self._admin(tg_id)
        entry = next(
            (e for e in self.queue if e.item.kind is body.kind and e.item.item_id == body.item_id),
            None,
        )
        if entry is None:
            raise _error(ErrorCode.not_found)
        if entry.done:
            raise _error(ErrorCode.conflict, "already handled")
        entry.done = True
        self.admin_actions.append(body)

    async def _h_admin_user(self, tg_id: int, path: dict[str, Any], **_: Any) -> AdminUserOut:
        admin = self._admin(tg_id)
        target = self.users.get(path["tg_id"])
        if target is None:
            raise _error(ErrorCode.not_found)
        card = None if self._missing(target)[:3] else self._card(target, admin, "admin")
        return AdminUserOut(
            user_id=target.id,
            tg_id=target.tg_id,
            status=target.status,
            shadow_banned=False,
            banned_until=target.banned_until,
            risk_score=0,
            card=card,
            reports_total=sum(1 for _, t in self.reports if t == target.id),
            mod_actions=[],
        )

    async def _h_admin_metrics(self, tg_id: int, params: dict[str, Any], **_: Any) -> MetricsOut:
        self._admin(tg_id)
        starts = sum(1 for u in self.users.values() if u.id < DEMO_ID_FLOOR)
        done = sum(
            1 for u in self.users.values() if u.id < DEMO_ID_FLOOR and u.status is UserStatus.active
        )
        likes = len(self.likes)
        matched = sum(1 for x in self.likes if x.status == "matched")
        today = NOW.date()
        return MetricsOut(
            period_from=today - timedelta(days=params["days"] - 1),
            period_to=today,
            starts=starts,
            onboarding_completed=done,
            onboarding_rate=done / starts if starts else 0.0,
            likes_total=likes,
            matches_total=len(self.matches),
            mutual_rate=matched / likes if likes else 0.0,
            d1_retention=0.0,
            d7_retention=0.0,
            reports_per_1000_views=0.0,
            confirmed_reports_rate=0.0,
            users_total=len(self.users),
            users_by_status={
                st: sum(1 for u in self.users.values() if u.status is st) for st in UserStatus
            },
            users_by_pool={
                pool: sum(1 for u in self.users.values() if u.pool is pool) for pool in Pool
            },
            verified_total=0,
            shadow_banned_total=0,
            bot_blocked_total=0,
            active_today=starts,
            active_7d=starts,
            active_30d=starts,
            views_total=0,
            skips_total=0,
            likes_with_message=sum(1 for x in self.likes if x.message or x.media),
            reports_total=len(self.reports),
            likes_all_time=likes,
            matches_all_time=len(self.matches),
            likes_pending=sum(1 for x in self.likes if x.status == "pending"),
        )

    # ---- S11 ---------------------------------------------------------------------------

    async def _h_captcha_new(self, tg_id: int, **_: Any) -> CaptchaChallenge:
        user = self.users[tg_id]
        if not user.captcha_required:
            raise _error(ErrorCode.conflict, "captcha not required")
        challenge_id = f"c{self._id()}"
        target = CAPTCHA_EMOJI[self._next_id % CAPTCHA_OPTIONS]
        self.captchas[challenge_id] = (tg_id, target)
        return CaptchaChallenge(
            challenge_id=challenge_id, target_emoji=target, options=list(CAPTCHA_EMOJI)
        )

    async def _h_captcha_verify(self, tg_id: int, body: CaptchaAnswerIn, **_: Any) -> UserState:
        user = self.users[tg_id]
        challenge = self.captchas.pop(body.challenge_id, None)
        if challenge is None or challenge[0] != tg_id:
            raise _error(ErrorCode.not_found, "challenge expired")
        if body.answer != challenge[1]:
            raise _error(ErrorCode.validation_error, "wrong answer")
        user.captcha_required = False
        return self._state(user)

    # ---- S12 ---------------------------------------------------------------------------

    async def _h_verification_start(self, tg_id: int, **_: Any) -> GestureOut:
        user = self.users[tg_id]
        if user.verified:
            raise _error(ErrorCode.conflict, details={"reason": "already_verified"})
        if any(
            v.user_id == user.id and v.status is ModerationStatus.pending
            for v in self.verifications
        ):
            raise _error(ErrorCode.conflict, details={"reason": "pending"})
        if not any(
            m.moderation_status is ModerationStatus.approved and m.kind is MediaKind.photo
            for m in user.media
        ):
            raise _error(ErrorCode.conflict, details={"reason": "no_photo"})
        gestures = list(GestureCode)
        verification = FakeVerification(
            self._id(), user.id, gestures[self._next_id % len(gestures)]
        )
        self.verifications.append(verification)
        return GestureOut(verification_id=verification.id, gesture=verification.gesture)

    async def _h_verification_submit(
        self, tg_id: int, body: VerificationIn, **_: Any
    ) -> VerificationOut:
        user = self.users[tg_id]
        verification = next(
            (
                v
                for v in self.verifications
                if v.id == body.verification_id and v.user_id == user.id
            ),
            None,
        )
        if verification is None:
            raise _error(ErrorCode.not_found)
        if verification.file_id is not None:
            raise _error(ErrorCode.conflict, details={"reason": "pending"})
        verification.file_id = body.video_note_file_id
        verification.status = ModerationStatus.pending
        return VerificationOut(status=ModerationStatus.pending)

    async def _h_verification_status(self, tg_id: int, **_: Any) -> VerificationOut:
        user = self.users[tg_id]
        mine = [v for v in self.verifications if v.user_id == user.id and v.status is not None]
        if user.verified:
            return VerificationOut(status=ModerationStatus.approved)
        return VerificationOut(status=mine[-1].status if mine else None)

    # ---- S13 internal ------------------------------------------------------------------

    async def _h_mark_bot_blocked(self, tg_id: int) -> None:
        if tg_id not in self.users:
            raise _error(ErrorCode.not_found)
        self.bot_blocked.add(tg_id)

    async def _h_mark_notification_sent(self, dedupe_key: str) -> None:
        self.sent_notifications.append(dedupe_key)

    # ---- S14 ---------------------------------------------------------------------------

    async def _h_get_referral(self, tg_id: int, **_: Any) -> ReferralOut:
        user = self.users[tg_id]
        return ReferralOut(
            code=user.referral_code,
            invited_count=user.invited,
            bonus_per_invite=REFERRAL_BONUS_REACTIONS,
        )
