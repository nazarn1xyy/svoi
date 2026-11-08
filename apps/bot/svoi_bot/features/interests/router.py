"""Goals and interests router."""

from aiogram import F, Router

from svoi_bot.features.interests import handlers, views
from svoi_bot.features.interests.states import InterestsSG
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import DoneCb, NavCb, PageCb, ToggleCb
from svoi_bot.ui.keyboards import NOOP


def make_router() -> Router:
    """Handlers by state; the same screens serve onboarding and editing."""
    router = Router(name="interests")
    context.attach(router)
    goals, interests = views.GOALS, views.INTERESTS
    router.callback_query.register(
        handlers.on_goal_toggle, InterestsSG.goals, ToggleCb.filter(F.field == goals)
    )
    router.callback_query.register(
        handlers.on_goals_done, InterestsSG.goals, DoneCb.filter(F.field == goals)
    )
    router.callback_query.register(
        handlers.on_goals_noop,
        InterestsSG.goals,
        NavCb.filter((F.screen == goals) & (F.arg == NOOP)),
    )
    in_lists = InterestsSG.categories, InterestsSG.category, InterestsSG.custom
    router.callback_query.register(
        handlers.on_open_category,
        InterestsSG.categories,
        NavCb.filter(F.screen == views.CATEGORY_SCREEN),
    )
    router.callback_query.register(
        handlers.on_interest_toggle, InterestsSG.category, ToggleCb.filter(F.field == interests)
    )
    router.callback_query.register(
        handlers.on_page, InterestsSG.category, PageCb.filter(F.field == interests)
    )
    for state in in_lists:
        router.callback_query.register(
            handlers.on_interests_nav, state, NavCb.filter(F.screen == interests)
        )
        router.callback_query.register(
            handlers.on_interests_done, state, DoneCb.filter(F.field == interests)
        )
    router.message.register(handlers.on_custom, InterestsSG.custom, F.text)
    return router
