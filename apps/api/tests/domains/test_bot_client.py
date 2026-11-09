"""The bot's real HttpApiClient against the real API: paths, encoding and models agree."""

from typing import Any

import httpx
from apihelp import ADMIN_TG, TOKEN
from svoi_api.main import create_app
from svoi_bot.api_client import HttpApiClient
from svoi_contracts.api.feed import FeedItem
from svoi_contracts.api.likes import IncomingLike, RespondIn
from svoi_contracts.api.profile import (
    AgeIn,
    CityIn,
    GenderIn,
    GoalsIn,
    InterestsIn,
    MediaIn,
    NameIn,
    SkipIn,
)
from svoi_contracts.api.reactions import ReactionIn
from svoi_contracts.api.users import LangIn, StartIn
from svoi_contracts.enums import (
    AdminQueueKind,
    Gender,
    GoalCode,
    Lang,
    LikeDecision,
    MediaKind,
    OnboardingStep,
    ReactionType,
)


def _client(env: dict[str, Any]) -> HttpApiClient:
    app = create_app(
        env["settings"],
        sessionmaker=env["maker"],
        redis=env["redis"],
        queue=env["queue"],
        clients=env["clients"],
    )
    return HttpApiClient("http://api/v1", TOKEN, transport=httpx.ASGITransport(app=app))


async def _onboard(api: HttpApiClient, tg_id: int, name: str) -> None:
    await api.start(
        tg_id,
        StartIn(
            tg_username=name.lower(),
            tg_first_name=name,
            tg_language_code="uk",
            has_tg_profile_photo=True,
        ),
    )
    await api.set_lang(tg_id, LangIn(lang=Lang.uk))
    await api.consent(tg_id)
    await api.set_age(tg_id, AgeIn(age=19))
    await api.set_name(tg_id, NameIn(name=name))
    await api.set_gender(tg_id, GenderIn(gender=Gender.female))
    city = (await api.search_cities(tg_id, "Вінниця"))[0]
    await api.set_city(tg_id, CityIn(city_id=city.id))
    await api.set_goals(tg_id, GoalsIn(codes=[GoalCode.friends]))
    cats = await api.get_categories(tg_id)
    ids = [i.id for i in await api.get_interests(tg_id, cats[0].id)][:3]
    await api.set_interests(tg_id, InterestsIn(interest_ids=ids))
    for step in (
        OnboardingStep.clarify,
        OnboardingStep.institution,
        OnboardingStep.height,
        OnboardingStep.prompts,
    ):
        await api.skip_step(tg_id, SkipIn(step=step))
    await api.add_media(
        tg_id, MediaIn(kind=MediaKind.photo, file_id=f"f{tg_id}", file_unique_id=f"u{tg_id}")
    )
    await api.skip_step(tg_id, SkipIn(step=OnboardingStep.media))
    state = await api.complete_onboarding(tg_id)
    assert state.onboarding_step is OnboardingStep.done


async def test_bot_client_full_journey(env: dict[str, Any]) -> None:
    api = _client(env)
    try:
        await _onboard(api, 1, "Ira")
        await _onboard(api, 2, "Max")
        await _onboard(api, ADMIN_TG, "Admin")
        card = await api.feed_next(1)
        assert isinstance(card, FeedItem)
        out = await api.react(1, ReactionIn(target_id=card.card.user_id, type=ReactionType.like))
        assert out.match is None
        tg_of = {(await api.get_me(t)).user_id: t for t in (2, ADMIN_TG)}
        tg = tg_of[card.card.user_id]
        liked = await api.incoming_next(tg)
        assert isinstance(liked, IncomingLike)
        result = await api.respond_like(tg, liked.like_id, RespondIn(decision=LikeDecision.accept))
        assert result.match is not None
        assert (await api.get_match(1, result.match.match_id)).partner_tg_id == tg
        assert len((await api.get_contacts(1)).items) == 1
        assert (await api.get_my_card(1)).completeness is not None
        stats = await api.admin_queue_stats(ADMIN_TG)
        assert set(stats) == set(AdminQueueKind)
        await api.mark_notification_sent(
            f"match:{result.match.match_id}:{(await api.get_me(1)).user_id}"
        )
        await api.mark_bot_blocked(2)
        assert (await api.get_referral(1)).bonus_per_invite == 20
    finally:
        await api.aclose()
