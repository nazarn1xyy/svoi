"""ApiClient: one typed method per endpoint of docs/tech.md section 7.2.

Implementations only provide `_call`; every endpoint method is defined once here.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, TypeAdapter
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
from svoi_contracts.api.feed import ExpandIn, FeedItem, FeedResponse
from svoi_contracts.api.likes import (
    ContactOut,
    CountOut,
    IncomingResponse,
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
    PromptsIn,
    SkipIn,
)
from svoi_contracts.api.reactions import ReactionIn, ReactionOut
from svoi_contracts.api.referral import ReferralOut
from svoi_contracts.api.safety import CaptchaAnswerIn, CaptchaChallenge
from svoi_contracts.api.users import LangIn, StartIn
from svoi_contracts.api.verification import GestureOut, VerificationIn, VerificationOut
from svoi_contracts.cards import Limits, MatchResult, MediaRef, Page, ProfileCard, UserState
from svoi_contracts.enums import AdminQueueKind

Method = Literal["GET", "POST", "PUT", "DELETE"]


@dataclass(frozen=True)
class Op:
    """One endpoint: HTTP method, path template under /v1 and the response type."""

    name: str
    method: Method
    path: str
    response: Any  # a type for TypeAdapter; None for 204
    body: type[BaseModel] | None = None
    internal: bool = False  # /internal/*: no X-Tg-User-Id

    def adapter(self) -> TypeAdapter[Any] | None:
        """Validator for the response body."""
        return None if self.response is None else TypeAdapter(self.response)


_OPS = (
    # S1
    Op("start", "POST", "/users/start", UserState, StartIn),
    Op("get_me", "GET", "/users/me", UserState),
    Op("set_lang", "PUT", "/users/me/lang", UserState, LangIn),
    Op("consent", "POST", "/users/me/consent", UserState),
    Op("set_age", "PUT", "/profile/age", UserState, AgeIn),
    Op("set_name", "PUT", "/profile/name", UserState, NameIn),
    Op("set_gender", "PUT", "/profile/gender", UserState, GenderIn),
    Op("skip_step", "POST", "/onboarding/skip", UserState, SkipIn),
    # S2
    Op("search_cities", "GET", "/catalog/cities/search", list[CityOut]),
    Op("city_by_location", "GET", "/catalog/cities/by-location", CityOut),
    Op("set_city", "PUT", "/profile/city", UserState, CityIn),
    # S3
    Op("get_goals", "GET", "/catalog/goals", list[GoalOut]),
    Op("set_goals", "PUT", "/profile/goals", UserState, GoalsIn),
    Op("get_categories", "GET", "/catalog/interest-categories", list[CategoryOut]),
    Op("get_interests", "GET", "/catalog/interests", list[InterestOut]),
    Op("set_interests", "PUT", "/profile/interests", UserState, InterestsIn),
    Op("custom_interest", "POST", "/catalog/interests/custom", CustomInterestOut, CustomInterestIn),
    # S4
    Op("get_clarifications", "GET", "/profile/clarifications", list[ClarificationOut]),
    Op("set_interest_note", "PUT", "/profile/interests/{interest_id}/note", UserState, NoteIn),
    Op("search_institutions", "GET", "/catalog/institutions/search", list[InstitutionOut]),
    Op("set_institution", "PUT", "/profile/institution", UserState, InstitutionIn),
    Op("set_height", "PUT", "/profile/height", UserState, HeightIn),
    Op("get_prompts", "GET", "/catalog/prompts", list[PromptOut]),
    Op("set_prompts", "PUT", "/profile/prompts", UserState, PromptsIn),
    Op("add_media", "POST", "/profile/media", MediaRef, MediaIn),
    Op("delete_media", "DELETE", "/profile/media/{media_id}", UserState),
    Op("reorder_media", "PUT", "/profile/media/order", list[MediaRef], MediaOrderIn),
    Op("complete_onboarding", "POST", "/onboarding/complete", UserState),
    # S5
    Op("get_my_card", "GET", "/profile/me/card", ProfileCard),
    Op("reset_profile", "POST", "/profile/reset", UserState),
    Op("hide_profile", "POST", "/profile/hide", UserState),
    Op("unhide_profile", "POST", "/profile/unhide", UserState),
    Op("delete_me", "DELETE", "/users/me", None),
    # S6
    Op("get_filters", "GET", "/filters", FiltersOut),
    Op("set_filters", "PUT", "/filters", FiltersOut, FiltersIn),
    Op("get_settings", "GET", "/settings", SettingsOut),
    Op("set_settings", "PUT", "/settings", SettingsOut, SettingsIn),
    # S7
    Op("feed_next", "GET", "/feed/next", FeedResponse),
    Op("feed_expand", "POST", "/feed/expand", FeedResponse, ExpandIn),
    # S8
    Op("react", "POST", "/reactions", ReactionOut, ReactionIn),
    Op("undo_reaction", "POST", "/reactions/undo", FeedItem),
    Op("get_limits", "GET", "/limits", Limits),
    # S9
    Op("incoming_count", "GET", "/likes/incoming/count", CountOut),
    Op("incoming_next", "GET", "/likes/incoming/next", IncomingResponse),
    Op("respond_like", "POST", "/likes/{like_id}/respond", RespondOut, RespondIn),
    Op("get_match", "GET", "/matches/{match_id}", MatchResult),
    Op("get_contacts", "GET", "/contacts", Page[ContactOut]),
    Op("delete_contact", "DELETE", "/contacts/{match_id}", None),
    # S10
    Op("report", "POST", "/reports", None, ReportIn),
    Op("block", "POST", "/blocks", None, BlockIn),
    Op("unblock", "DELETE", "/blocks/{target_id}", None),
    Op("admin_queue", "GET", "/admin/queue", AdminQueueItem | None),
    Op("admin_queue_stats", "GET", "/admin/queue/stats", dict[AdminQueueKind, int]),
    Op("admin_action", "POST", "/admin/actions", None, AdminActionIn),
    Op("admin_user", "GET", "/admin/users/{tg_id}", AdminUserOut),
    Op("admin_metrics", "GET", "/admin/metrics", MetricsOut),
    # S11
    Op("captcha_new", "POST", "/users/me/captcha", CaptchaChallenge),
    Op("captcha_verify", "POST", "/users/me/captcha/verify", UserState, CaptchaAnswerIn),
    # S12
    Op("verification_start", "POST", "/verification/start", GestureOut),
    Op("verification_submit", "POST", "/verification/submit", VerificationOut, VerificationIn),
    Op("verification_status", "GET", "/verification/status", VerificationOut),
    # S13
    Op("mark_bot_blocked", "POST", "/internal/users/{tg_id}/bot-blocked", None, internal=True),
    Op(
        "mark_notification_sent",
        "POST",
        "/internal/notifications/{dedupe_key}/sent",
        None,
        internal=True,
    ),
    # S14
    Op("get_referral", "GET", "/referral", ReferralOut),
)
OPS: dict[str, Op] = {op.name: op for op in _OPS}


class ApiClient(Protocol):
    """Bot-side API. `tg_id` is the acting user (X-Tg-User-Id)."""

    async def _call(
        self,
        op: Op,
        tg_id: int | None,
        *,
        body: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        path: dict[str, Any] | None = None,
    ) -> Any: ...

    async def aclose(self) -> None:
        """Release network resources."""

    # S1
    async def start(self, tg_id: int, body: StartIn) -> UserState:
        """POST /users/start."""
        result: UserState = await self._call(OPS["start"], tg_id, body=body)
        return result

    async def get_me(self, tg_id: int) -> UserState:
        """GET /users/me."""
        result: UserState = await self._call(OPS["get_me"], tg_id)
        return result

    async def set_lang(self, tg_id: int, body: LangIn) -> UserState:
        """PUT /users/me/lang."""
        result: UserState = await self._call(OPS["set_lang"], tg_id, body=body)
        return result

    async def consent(self, tg_id: int) -> UserState:
        """POST /users/me/consent."""
        result: UserState = await self._call(OPS["consent"], tg_id)
        return result

    async def set_age(self, tg_id: int, body: AgeIn) -> UserState:
        """PUT /profile/age."""
        result: UserState = await self._call(OPS["set_age"], tg_id, body=body)
        return result

    async def set_name(self, tg_id: int, body: NameIn) -> UserState:
        """PUT /profile/name."""
        result: UserState = await self._call(OPS["set_name"], tg_id, body=body)
        return result

    async def set_gender(self, tg_id: int, body: GenderIn) -> UserState:
        """PUT /profile/gender."""
        result: UserState = await self._call(OPS["set_gender"], tg_id, body=body)
        return result

    async def skip_step(self, tg_id: int, body: SkipIn) -> UserState:
        """POST /onboarding/skip."""
        result: UserState = await self._call(OPS["skip_step"], tg_id, body=body)
        return result

    # S2
    async def search_cities(self, tg_id: int, q: str, limit: int = 5) -> list[CityOut]:
        """GET /catalog/cities/search; q has at least 2 characters."""
        result: list[CityOut] = await self._call(
            OPS["search_cities"], tg_id, params={"q": q, "limit": limit}
        )
        return result

    async def city_by_location(self, tg_id: int, lat: float, lon: float) -> CityOut:
        """GET /catalog/cities/by-location."""
        result: CityOut = await self._call(
            OPS["city_by_location"], tg_id, params={"lat": lat, "lon": lon}
        )
        return result

    async def set_city(self, tg_id: int, body: CityIn) -> UserState:
        """PUT /profile/city."""
        result: UserState = await self._call(OPS["set_city"], tg_id, body=body)
        return result

    # S3
    async def get_goals(self, tg_id: int) -> list[GoalOut]:
        """GET /catalog/goals."""
        result: list[GoalOut] = await self._call(OPS["get_goals"], tg_id)
        return result

    async def set_goals(self, tg_id: int, body: GoalsIn) -> UserState:
        """PUT /profile/goals."""
        result: UserState = await self._call(OPS["set_goals"], tg_id, body=body)
        return result

    async def get_categories(self, tg_id: int) -> list[CategoryOut]:
        """GET /catalog/interest-categories."""
        result: list[CategoryOut] = await self._call(OPS["get_categories"], tg_id)
        return result

    async def get_interests(self, tg_id: int, category_id: int) -> list[InterestOut]:
        """GET /catalog/interests."""
        result: list[InterestOut] = await self._call(
            OPS["get_interests"], tg_id, params={"category_id": category_id}
        )
        return result

    async def set_interests(self, tg_id: int, body: InterestsIn) -> UserState:
        """PUT /profile/interests."""
        result: UserState = await self._call(OPS["set_interests"], tg_id, body=body)
        return result

    async def custom_interest(self, tg_id: int, body: CustomInterestIn) -> CustomInterestOut:
        """POST /catalog/interests/custom."""
        result: CustomInterestOut = await self._call(OPS["custom_interest"], tg_id, body=body)
        return result

    # S4
    async def get_clarifications(self, tg_id: int) -> list[ClarificationOut]:
        """GET /profile/clarifications."""
        result: list[ClarificationOut] = await self._call(OPS["get_clarifications"], tg_id)
        return result

    async def set_interest_note(self, tg_id: int, interest_id: int, body: NoteIn) -> UserState:
        """PUT /profile/interests/{interest_id}/note."""
        result: UserState = await self._call(
            OPS["set_interest_note"], tg_id, body=body, path={"interest_id": interest_id}
        )
        return result

    async def search_institutions(
        self, tg_id: int, city_id: int, q: str = "", limit: int = 8
    ) -> list[InstitutionOut]:
        """GET /catalog/institutions/search."""
        result: list[InstitutionOut] = await self._call(
            OPS["search_institutions"], tg_id, params={"city_id": city_id, "q": q, "limit": limit}
        )
        return result

    async def set_institution(self, tg_id: int, body: InstitutionIn) -> UserState:
        """PUT /profile/institution."""
        result: UserState = await self._call(OPS["set_institution"], tg_id, body=body)
        return result

    async def set_height(self, tg_id: int, body: HeightIn) -> UserState:
        """PUT /profile/height."""
        result: UserState = await self._call(OPS["set_height"], tg_id, body=body)
        return result

    async def get_prompts(self, tg_id: int) -> list[PromptOut]:
        """GET /catalog/prompts."""
        result: list[PromptOut] = await self._call(OPS["get_prompts"], tg_id)
        return result

    async def set_prompts(self, tg_id: int, body: PromptsIn) -> UserState:
        """PUT /profile/prompts."""
        result: UserState = await self._call(OPS["set_prompts"], tg_id, body=body)
        return result

    async def add_media(self, tg_id: int, body: MediaIn) -> MediaRef:
        """POST /profile/media."""
        result: MediaRef = await self._call(OPS["add_media"], tg_id, body=body)
        return result

    async def delete_media(self, tg_id: int, media_id: int) -> UserState:
        """DELETE /profile/media/{media_id}."""
        result: UserState = await self._call(
            OPS["delete_media"], tg_id, path={"media_id": media_id}
        )
        return result

    async def reorder_media(self, tg_id: int, body: MediaOrderIn) -> list[MediaRef]:
        """PUT /profile/media/order."""
        result: list[MediaRef] = await self._call(OPS["reorder_media"], tg_id, body=body)
        return result

    async def complete_onboarding(self, tg_id: int) -> UserState:
        """POST /onboarding/complete."""
        result: UserState = await self._call(OPS["complete_onboarding"], tg_id)
        return result

    # S5
    async def get_my_card(self, tg_id: int) -> ProfileCard:
        """GET /profile/me/card."""
        result: ProfileCard = await self._call(OPS["get_my_card"], tg_id)
        return result

    async def reset_profile(self, tg_id: int) -> UserState:
        """POST /profile/reset."""
        result: UserState = await self._call(OPS["reset_profile"], tg_id)
        return result

    async def hide_profile(self, tg_id: int) -> UserState:
        """POST /profile/hide."""
        result: UserState = await self._call(OPS["hide_profile"], tg_id)
        return result

    async def unhide_profile(self, tg_id: int) -> UserState:
        """POST /profile/unhide."""
        result: UserState = await self._call(OPS["unhide_profile"], tg_id)
        return result

    async def delete_me(self, tg_id: int) -> None:
        """DELETE /users/me."""
        await self._call(OPS["delete_me"], tg_id)

    # S6
    async def get_filters(self, tg_id: int) -> FiltersOut:
        """GET /filters."""
        result: FiltersOut = await self._call(OPS["get_filters"], tg_id)
        return result

    async def set_filters(self, tg_id: int, body: FiltersIn) -> FiltersOut:
        """PUT /filters."""
        result: FiltersOut = await self._call(OPS["set_filters"], tg_id, body=body)
        return result

    async def get_settings(self, tg_id: int) -> SettingsOut:
        """GET /settings."""
        result: SettingsOut = await self._call(OPS["get_settings"], tg_id)
        return result

    async def set_settings(self, tg_id: int, body: SettingsIn) -> SettingsOut:
        """PUT /settings."""
        result: SettingsOut = await self._call(OPS["set_settings"], tg_id, body=body)
        return result

    # S7
    async def feed_next(self, tg_id: int) -> FeedResponse:
        """GET /feed/next."""
        result: FeedResponse = await self._call(OPS["feed_next"], tg_id)
        return result

    async def feed_expand(self, tg_id: int, body: ExpandIn) -> FeedResponse:
        """POST /feed/expand."""
        result: FeedResponse = await self._call(OPS["feed_expand"], tg_id, body=body)
        return result

    # S8
    async def react(self, tg_id: int, body: ReactionIn) -> ReactionOut:
        """POST /reactions."""
        result: ReactionOut = await self._call(OPS["react"], tg_id, body=body)
        return result

    async def undo_reaction(self, tg_id: int) -> FeedItem:
        """POST /reactions/undo."""
        result: FeedItem = await self._call(OPS["undo_reaction"], tg_id)
        return result

    async def get_limits(self, tg_id: int) -> Limits:
        """GET /limits."""
        result: Limits = await self._call(OPS["get_limits"], tg_id)
        return result

    # S9
    async def incoming_count(self, tg_id: int) -> CountOut:
        """GET /likes/incoming/count."""
        result: CountOut = await self._call(OPS["incoming_count"], tg_id)
        return result

    async def incoming_next(self, tg_id: int) -> IncomingResponse:
        """GET /likes/incoming/next."""
        result: IncomingResponse = await self._call(OPS["incoming_next"], tg_id)
        return result

    async def respond_like(self, tg_id: int, like_id: int, body: RespondIn) -> RespondOut:
        """POST /likes/{like_id}/respond."""
        result: RespondOut = await self._call(
            OPS["respond_like"], tg_id, body=body, path={"like_id": like_id}
        )
        return result

    async def get_match(self, tg_id: int, match_id: int) -> MatchResult:
        """GET /matches/{match_id}."""
        result: MatchResult = await self._call(OPS["get_match"], tg_id, path={"match_id": match_id})
        return result

    async def get_contacts(
        self, tg_id: int, cursor: str | None = None, limit: int = 20
    ) -> Page[ContactOut]:
        """GET /contacts."""
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        result: Page[ContactOut] = await self._call(OPS["get_contacts"], tg_id, params=params)
        return result

    async def delete_contact(self, tg_id: int, match_id: int) -> None:
        """DELETE /contacts/{match_id}."""
        await self._call(OPS["delete_contact"], tg_id, path={"match_id": match_id})

    # S10
    async def report(self, tg_id: int, body: ReportIn) -> None:
        """POST /reports."""
        await self._call(OPS["report"], tg_id, body=body)

    async def block(self, tg_id: int, body: BlockIn) -> None:
        """POST /blocks."""
        await self._call(OPS["block"], tg_id, body=body)

    async def unblock(self, tg_id: int, target_id: int) -> None:
        """DELETE /blocks/{target_id}."""
        await self._call(OPS["unblock"], tg_id, path={"target_id": target_id})

    async def admin_queue(self, tg_id: int, kind: AdminQueueKind) -> AdminQueueItem | None:
        """GET /admin/queue."""
        result: AdminQueueItem | None = await self._call(
            OPS["admin_queue"], tg_id, params={"kind": kind.value}
        )
        return result

    async def admin_queue_stats(self, tg_id: int) -> dict[AdminQueueKind, int]:
        """GET /admin/queue/stats."""
        result: dict[AdminQueueKind, int] = await self._call(OPS["admin_queue_stats"], tg_id)
        return result

    async def admin_action(self, tg_id: int, body: AdminActionIn) -> None:
        """POST /admin/actions."""
        await self._call(OPS["admin_action"], tg_id, body=body)

    async def admin_user(self, tg_id: int, user_tg_id: int) -> AdminUserOut:
        """GET /admin/users/{tg_id}."""
        result: AdminUserOut = await self._call(
            OPS["admin_user"], tg_id, path={"tg_id": user_tg_id}
        )
        return result

    async def admin_metrics(self, tg_id: int, days: int = 7) -> MetricsOut:
        """GET /admin/metrics; days in 1..90."""
        result: MetricsOut = await self._call(OPS["admin_metrics"], tg_id, params={"days": days})
        return result

    # S11
    async def captcha_new(self, tg_id: int) -> CaptchaChallenge:
        """POST /users/me/captcha."""
        result: CaptchaChallenge = await self._call(OPS["captcha_new"], tg_id)
        return result

    async def captcha_verify(self, tg_id: int, body: CaptchaAnswerIn) -> UserState:
        """POST /users/me/captcha/verify."""
        result: UserState = await self._call(OPS["captcha_verify"], tg_id, body=body)
        return result

    # S12
    async def verification_start(self, tg_id: int) -> GestureOut:
        """POST /verification/start."""
        result: GestureOut = await self._call(OPS["verification_start"], tg_id)
        return result

    async def verification_submit(self, tg_id: int, body: VerificationIn) -> VerificationOut:
        """POST /verification/submit."""
        result: VerificationOut = await self._call(OPS["verification_submit"], tg_id, body=body)
        return result

    async def verification_status(self, tg_id: int) -> VerificationOut:
        """GET /verification/status."""
        result: VerificationOut = await self._call(OPS["verification_status"], tg_id)
        return result

    # S13, bot-worker only
    async def mark_bot_blocked(self, user_tg_id: int) -> None:
        """POST /internal/users/{tg_id}/bot-blocked."""
        await self._call(OPS["mark_bot_blocked"], None, path={"tg_id": user_tg_id})

    async def mark_notification_sent(self, dedupe_key: str) -> None:
        """POST /internal/notifications/{dedupe_key}/sent."""
        await self._call(OPS["mark_notification_sent"], None, path={"dedupe_key": dedupe_key})

    # S14
    async def get_referral(self, tg_id: int) -> ReferralOut:
        """GET /referral."""
        result: ReferralOut = await self._call(OPS["get_referral"], tg_id)
        return result
