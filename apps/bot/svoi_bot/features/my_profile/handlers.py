"""«Моя анкета»: card, field edits through the step registry, photos, hide, delete, reset."""

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.profile import MediaOrderIn
from svoi_contracts.enums import ModerationStatus, OnboardingStep, UserStatus

from svoi_bot.features.about.states import AboutSG
from svoi_bot.features.about.views import media as media_screen
from svoi_bot.features.my_profile import views
from svoi_bot.features.my_profile.states import MyProfileSG
from svoi_bot.features.onboarding import registry
from svoi_bot.features.onboarding.registry import MODE_KEY, StepContext, open_edit, show_step
from svoi_bot.middlewares import remember_state
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.cards import render_card, send_card


async def show_profile(step: StepContext) -> None:
    """Own card with completeness and the edit buttons."""
    await step.state.set_state(MyProfileSG.view)
    await step.screen.clear()
    card = await step.api.get_my_card(step.tg_user.id)
    me = await step.api.get_me(step.tg_user.id)
    await remember_state(step.state, me)
    await send_card(
        step.bot, step.tg_user.id, render_card(card, "own"), views.profile_buttons(me.status)
    )


async def after_edit(step: StepContext) -> None:
    """Back to «Моя анкета» (or to the preview while still onboarding)."""
    if step.user_state.status is UserStatus.onboarding:
        await show_step(step, OnboardingStep.preview)
        return
    card = await step.api.get_my_card(step.tg_user.id)
    if any(m.moderation_status is ModerationStatus.pending for m in card.media):
        await step.bot.send_message(step.tg_user.id, views.pending_note())
    await show_profile(step)


registry.after_edit.append(after_edit)
registry.profile_menu.append(show_profile)


async def on_open(message: Message, step: StepContext) -> None:
    """«👤 Моя анкета» or /profile."""
    await show_profile(step)


async def on_action(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Field edits, photos, restart, hide or show, delete."""
    await query.answer()
    action = callback_data.arg
    if action in views.EDIT_STEPS:
        await step.screen.clear()
        await open_edit(step, views.EDIT_STEPS[action])
    elif action == "photos":
        await show_photos(step)
    elif action == "delete":
        await step.state.set_state(MyProfileSG.confirm_delete)
        await step.screen.show(*views.confirm_delete())
    elif action == "reset":
        await step.state.set_state(MyProfileSG.confirm_reset)
        await step.screen.show(*views.confirm_reset())
    elif action == "hide":
        await remember_state(step.state, await step.api.hide_profile(step.tg_user.id))
        await step.bot.send_message(step.tg_user.id, views.hidden())
        await show_profile(step)
    elif action == "unhide":
        await remember_state(step.state, await step.api.unhide_profile(step.tg_user.id))
        await step.bot.send_message(step.tg_user.id, views.shown())
        await show_profile(step)


async def show_photos(step: StepContext) -> None:
    """Photo manager."""
    card = await step.api.get_my_card(step.tg_user.id)
    await step.state.set_state(MyProfileSG.photos)
    await step.screen.clear()
    await step.screen.show(*views.photos(card.media))


async def on_photos(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Delete one, add one, make one first, or go back."""
    await query.answer()
    action, _, raw_id = callback_data.arg.partition("-")  # ":" separates CallbackData fields
    if action == "del":
        await step.api.delete_media(step.tg_user.id, int(raw_id))
        await show_photos(step)
    elif action == "first":
        card = await step.api.get_my_card(step.tg_user.id)
        ids = [m.id for m in card.media]
        ids.remove(int(raw_id))
        await step.api.reorder_media(step.tg_user.id, MediaOrderIn(ids=[int(raw_id), *ids]))
        await show_photos(step)
    elif action == "add":
        await step.state.update_data({MODE_KEY: "edit"})
        await step.state.set_state(AboutSG.media)
        await step.screen.clear()
        await step.screen.show(*media_screen())
    else:
        await show_profile(step)


async def on_confirm_delete(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Second tap deletes; the other button returns."""
    await query.answer()
    if callback_data.value != views.YES:
        await show_profile(step)
        return
    await step.api.delete_me(step.tg_user.id)
    await step.state.clear()
    await step.bot.send_message(step.tg_user.id, views.deleted(), reply_markup=keyboards.remove())


async def on_confirm_reset(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Restart onboarding from the age step."""
    await query.answer()
    if callback_data.value != views.YES:
        await show_profile(step)
        return
    new_state = await step.api.reset_profile(step.tg_user.id)
    await remember_state(step.state, new_state)
    step.user_state = new_state
    await step.state.update_data({MODE_KEY: "onboarding"})
    await step.screen.clear()
    await show_step(step, new_state.onboarding_step)
