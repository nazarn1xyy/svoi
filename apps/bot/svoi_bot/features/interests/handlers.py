"""Goals and interests: selection lives in FSM data until «Готово»."""

from typing import Any

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.catalog import CustomInterestIn
from svoi_contracts.api.profile import GoalsIn, InterestsIn
from svoi_contracts.constants import CUSTOM_INTEREST_LEN, GOALS_COUNT, INTERESTS_COUNT
from svoi_contracts.enums import GoalCode, OnboardingStep, UserStatus
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.interests import views
from svoi_bot.features.interests.selection import can_finish, toggle
from svoi_bot.features.interests.states import InterestsSG
from svoi_bot.features.onboarding.registry import StepContext, advance, register
from svoi_bot.ui.callbacks import NavCb, PageCb, ToggleCb
from svoi_bot.ui.errors import render_api_error

_GOALS, _INTERESTS, _CATEGORY, _PAGE = "sel_goals", "sel_interests", "sel_category", "sel_page"


async def _data(step: StepContext) -> dict[str, Any]:
    return await step.state.get_data()


async def _current_card_values(step: StepContext) -> tuple[list[str], list[str]]:
    """Goals and interests already saved, for edit mode."""
    if step.user_state.status is UserStatus.onboarding:
        return [], []
    card = await step.api.get_my_card(step.tg_user.id)
    return [g.value for g in card.goals], [str(i.id) for i in card.interests]


# ---- goals --------------------------------------------------------------------------------


async def _render_goals(step: StepContext) -> None:
    selected = tuple((await _data(step)).get(_GOALS, []))
    goals = await step.api.get_goals(step.tg_user.id)
    await step.screen.replace(*views.goals(goals, selected))


@register(OnboardingStep.goals)
async def show_goals(step: StepContext) -> None:
    """Goal multi-select, preselected with saved goals when editing."""
    saved, _ = await _current_card_values(step)
    await step.state.update_data({_GOALS: saved})
    await step.state.set_state(InterestsSG.goals)
    await _render_goals(step)


async def on_goal_toggle(query: CallbackQuery, callback_data: ToggleCb, step: StepContext) -> None:
    """Tick or untick a goal."""
    result = toggle(tuple((await _data(step)).get(_GOALS, [])), callback_data.value, GOALS_COUNT[1])
    await step.state.update_data({_GOALS: list(result.selected)})
    await query.answer()
    await _render_goals(step)


async def on_goals_done(query: CallbackQuery, step: StepContext) -> None:
    """PUT /profile/goals."""
    selected = (await _data(step)).get(_GOALS, [])
    if not can_finish(len(selected), GOALS_COUNT):
        await query.answer(views.goals_hint(), show_alert=True)
        return
    new_state = await step.api.set_goals(
        step.tg_user.id, GoalsIn(codes=[GoalCode(v) for v in selected])
    )
    await query.answer()
    await advance(step, new_state)


async def on_goals_noop(query: CallbackQuery) -> None:
    """Inactive «Готово»."""
    await query.answer(views.goals_hint(), show_alert=True)


# ---- interests ----------------------------------------------------------------------------


async def _render_categories(step: StepContext) -> None:
    selected = (await _data(step)).get(_INTERESTS, [])
    items = await step.api.get_categories(step.tg_user.id)
    await step.state.set_state(InterestsSG.categories)
    await step.screen.replace(*views.categories(items, len(selected)))


async def _render_category(step: StepContext) -> None:
    data = await _data(step)
    category_id, page = int(data[_CATEGORY]), int(data.get(_PAGE, 0))
    items = await step.api.get_interests(step.tg_user.id, category_id)
    categories = await step.api.get_categories(step.tg_user.id)
    title = next((f"{c.emoji} {c.title}" for c in categories if c.id == category_id), "")
    await step.state.set_state(InterestsSG.category)
    await step.screen.replace(*views.category(title, items, tuple(data.get(_INTERESTS, [])), page))


@register(OnboardingStep.interests)
async def show_interests(step: StepContext) -> None:
    """Category list; editing starts from the saved interests."""
    _, saved = await _current_card_values(step)
    await step.state.update_data({_INTERESTS: saved})
    await _render_categories(step)


async def on_open_category(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Show one category's tags."""
    await step.state.update_data({_CATEGORY: callback_data.arg, _PAGE: 0})
    await query.answer()
    await _render_category(step)


async def on_interest_toggle(
    query: CallbackQuery, callback_data: ToggleCb, step: StepContext
) -> None:
    """Tick or untick a tag; the 16th is refused with an alert."""
    result = toggle(
        tuple((await _data(step)).get(_INTERESTS, [])), callback_data.value, INTERESTS_COUNT[1]
    )
    if result.rejected:
        await query.answer(views.too_many(), show_alert=True)
        return
    await step.state.update_data({_INTERESTS: list(result.selected)})
    await query.answer()
    await _render_category(step)


async def on_page(query: CallbackQuery, callback_data: PageCb, step: StepContext) -> None:
    """Next or previous 12 tags."""
    await step.state.update_data({_PAGE: callback_data.page})
    await query.answer()
    await _render_category(step)


async def on_interests_nav(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Back to categories, custom tag prompt, or the inactive «Готово»."""
    if callback_data.arg == views.BACK:
        await query.answer()
        await _render_categories(step)
    elif callback_data.arg == views.CUSTOM:
        await query.answer()
        await step.state.set_state(InterestsSG.custom)
        await step.screen.replace(views.custom_ask())
    else:
        await query.answer(views.too_few(), show_alert=True)


async def on_interests_done(query: CallbackQuery, step: StepContext) -> None:
    """One PUT /profile/interests with every selected id."""
    selected = (await _data(step)).get(_INTERESTS, [])
    if not can_finish(len(selected), INTERESTS_COUNT):
        await query.answer(views.too_few(), show_alert=True)
        return
    body = InterestsIn(interest_ids=[int(v) for v in selected])
    new_state = await step.api.set_interests(step.tg_user.id, body)
    await query.answer()
    await advance(step, new_state)


async def on_custom(message: Message, step: StepContext) -> None:
    """Own tag: matched joins the selection, pending waits for moderation."""
    title = (message.text or "").strip()
    if not CUSTOM_INTEREST_LEN[0] <= len(title) <= CUSTOM_INTEREST_LEN[1]:
        await message.answer(views.custom_length())
        return
    try:
        result = await step.api.custom_interest(step.tg_user.id, CustomInterestIn(title=title))
    except ApiException as exc:
        if exc.err.code in {ErrorCode.content_blocked, ErrorCode.validation_error}:
            await message.answer(render_api_error(exc.err))
            return
        raise
    if result.matched is not None:
        selected = tuple((await _data(step)).get(_INTERESTS, []))
        added = toggle(selected, str(result.matched.id), INTERESTS_COUNT[1])
        if str(result.matched.id) not in selected and not added.rejected:
            await step.state.update_data({_INTERESTS: list(added.selected)})
        await message.answer(views.custom_matched(result.matched.title))
    else:
        await message.answer(views.custom_pending(title))
    await step.screen.clear()
    await _render_categories(step)
