"""Preview: the user's own card from GET /profile/me/card, then POST /onboarding/complete."""

from aiogram.types import CallbackQuery
from svoi_contracts.enums import OnboardingStep
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.about import views
from svoi_bot.features.about.states import AboutSG
from svoi_bot.features.onboarding.registry import StepContext, profile_menu, register, show_step
from svoi_bot.features.start.menu import send_menu
from svoi_bot.middlewares import remember_state
from svoi_bot.ui.callbacks import PickCb
from svoi_bot.ui.cards import render_card, send_card


@register(OnboardingStep.preview)
async def show_preview(step: StepContext) -> None:
    """«Так тебе побачать інші:» and exactly the card the API returns."""
    await step.state.set_state(AboutSG.preview)
    await step.screen.clear()
    card = await step.api.get_my_card(step.tg_user.id)
    await step.bot.send_message(step.tg_user.id, views.preview_head(step.user_state.needs_username))
    await send_card(step.bot, step.tg_user.id, render_card(card, "own"), views.preview_buttons())


async def on_preview(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """✅ completes onboarding; ✏️ opens the edit menu (S5)."""
    await query.answer()
    if callback_data.value == views.EDIT:
        for menu in profile_menu:
            await menu(step)
        if not profile_menu:
            await show_preview(step)
        return
    try:
        new_state = await step.api.complete_onboarding(step.tg_user.id)
    except ApiException as exc:
        missing = (exc.err.details or {}).get("missing") or []
        if exc.err.code is ErrorCode.profile_incomplete and missing:
            await show_step(step, OnboardingStep(missing[0]))
            return
        raise
    await remember_state(step.state, new_state)
    await step.state.set_state(None)
    await send_menu(step.bot, step.api, step.tg_user.id, views.finished())
