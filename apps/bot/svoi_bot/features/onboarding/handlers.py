"""S1 steps: language, consent, age, name, gender; resume from the saved step."""

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.profile import AgeIn, GenderIn, NameIn
from svoi_contracts.api.users import LangIn
from svoi_contracts.enums import Gender, Lang, OnboardingStep
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.onboarding import views
from svoi_bot.features.onboarding.registry import StepContext, advance, register, show_step
from svoi_bot.features.onboarding.states import OnboardingSG
from svoi_bot.ui.callbacks import PickCb
from svoi_bot.ui.errors import render_api_error

# ---- screens ------------------------------------------------------------------------------


@register(OnboardingStep.lang)
async def show_lang(step: StepContext) -> None:
    """Choose your language."""
    await step.state.set_state(OnboardingSG.lang)
    await step.screen.replace(*views.language())


@register(OnboardingStep.consent)
async def show_consent(step: StepContext) -> None:
    """Greeting and terms."""
    await step.state.set_state(OnboardingSG.consent)
    await step.screen.replace(*views.consent())


@register(OnboardingStep.age)
async def show_age(step: StepContext) -> None:
    """Typed age."""
    await step.state.set_state(OnboardingSG.age)
    await step.screen.replace(views.age())


@register(OnboardingStep.name)
async def show_name(step: StepContext) -> None:
    """Typed name or the Telegram one."""
    await step.state.set_state(OnboardingSG.name)
    await step.screen.replace(*views.name(step.tg_user.first_name))


@register(OnboardingStep.gender)
async def show_gender(step: StepContext) -> None:
    """Gender buttons."""
    await step.state.set_state(OnboardingSG.gender)
    await step.screen.replace(*views.gender())


# ---- handlers -----------------------------------------------------------------------------


async def on_lang(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """PUT /users/me/lang; every later text uses the chosen language."""
    new_state = await step.api.set_lang(step.tg_user.id, LangIn(lang=Lang(callback_data.value)))
    await query.answer()
    await advance(step, new_state)


async def on_consent(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """«Поїхали» accepts; «Як це працює» explains and comes back."""
    if callback_data.value == views.HOW:
        await query.answer()
        await step.screen.replace(*views.how_it_works())
        return
    if callback_data.value == views.BACK:
        await query.answer()
        await step.screen.replace(*views.consent())
        return
    new_state = await step.api.consent(step.tg_user.id)
    await query.answer()
    await advance(step, new_state)


async def on_age(message: Message, step: StepContext) -> None:
    """Digits only; refusal and lock texts come from the API error."""
    age = views.parse_age(message.text or "")
    if age is None:
        await message.answer(views.age_not_a_number())
        return
    try:
        new_state = await step.api.set_age(step.tg_user.id, AgeIn(age=age))
    except ApiException as exc:
        await message.answer(render_api_error(exc.err))
        return
    await step.screen.clear()
    await advance(step, new_state)


_NAME_REJECTED = {ErrorCode.content_blocked, ErrorCode.validation_error}


async def _save_name(step: StepContext, name: str, typed: bool) -> str | None:
    """PUT /profile/name; returns the rejection text, if any."""
    try:
        new_state = await step.api.set_name(step.tg_user.id, NameIn(name=name))
    except ApiException as exc:
        if exc.err.code in _NAME_REJECTED:
            return views.name_rules()
        raise
    if typed:
        await step.screen.clear()
    await advance(step, new_state)
    return None


async def on_name_typed(message: Message, step: StepContext) -> None:
    """Typed name."""
    rejected = await _save_name(step, (message.text or "").strip(), typed=True)
    if rejected:
        await message.answer(rejected)


async def on_name_button(query: CallbackQuery, step: StepContext) -> None:
    """Telegram first name in one tap."""
    rejected = await _save_name(step, (step.tg_user.first_name or "").strip(), typed=False)
    await query.answer(rejected, show_alert=bool(rejected))


async def on_gender(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """PUT /profile/gender."""
    body = GenderIn(gender=Gender(callback_data.value))
    new_state = await step.api.set_gender(step.tg_user.id, body)
    await query.answer()
    await advance(step, new_state)


async def resume_message(message: Message, step: StepContext) -> None:
    """Any message during onboarding brings back the saved step."""
    await step.screen.clear()
    await show_step(step, step.user_state.onboarding_step)


async def resume_callback(query: CallbackQuery, step: StepContext) -> None:
    """A button from an old screen: show the saved step instead."""
    await query.answer()
    await step.screen.clear()
    await show_step(step, step.user_state.onboarding_step)
