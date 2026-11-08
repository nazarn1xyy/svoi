"""S4 optional steps; each skip calls POST /onboarding/skip with its own step."""

from typing import Any

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.profile import (
    ClarificationOut,
    HeightIn,
    InstitutionIn,
    MediaIn,
    NoteIn,
    PromptAnswerIn,
    PromptsIn,
    SkipIn,
)
from svoi_contracts.cards import UserState
from svoi_contracts.constants import CLARIFICATIONS_MAX, HEIGHT_CM, PROMPT_TEXT_MAX, PROMPTS_MAX
from svoi_contracts.enums import MediaKind, OnboardingStep
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.about import views
from svoi_bot.features.about.states import AboutSG
from svoi_bot.features.city.handlers import CITY_ID_KEY
from svoi_bot.features.onboarding.registry import StepContext, advance, finish_edit, register
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.errors import render_api_error

_CLARIFY, _ANSWERS, _PROMPT, _MEDIA_COUNT = (
    "clarify_left",
    "prompt_answers",
    "prompt_now",
    "media_n",
)


async def _data(step: StepContext) -> dict[str, Any]:
    return await step.state.get_data()


async def _skip(step: StepContext, which: OnboardingStep) -> None:
    """Onboarding: POST /onboarding/skip; edit: just go back to «Моя анкета»."""
    if await step.mode() == "edit":
        await finish_edit(step)
        return
    await advance(step, await step.api.skip_step(step.tg_user.id, SkipIn(step=which)))


# ---- clarifications -----------------------------------------------------------------------


async def _next_clarification(step: StepContext) -> None:
    left = (await _data(step)).get(_CLARIFY, [])
    if not left:
        await _skip(step, OnboardingStep.clarify)
        return
    await step.state.set_state(AboutSG.clarify)
    await step.screen.replace(*views.clarification(ClarificationOut.model_validate(left[0])))


@register(OnboardingStep.clarify)
async def show_clarify(step: StepContext) -> None:
    """Up to CLARIFICATIONS_MAX questions about chosen interests, no step number."""
    items = await step.api.get_clarifications(step.tg_user.id)
    await step.state.update_data(
        {_CLARIFY: [i.model_dump(mode="json") for i in items[:CLARIFICATIONS_MAX]]}
    )
    await _next_clarification(step)


async def on_clarify(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Save the note and move on."""
    left = (await _data(step)).get(_CLARIFY, [])
    await query.answer()
    if not left:
        return
    current = ClarificationOut.model_validate(left[0])
    await step.api.set_interest_note(
        step.tg_user.id, current.interest_id, NoteIn(option_key=callback_data.value)
    )
    await step.state.update_data({_CLARIFY: left[1:]})
    await _next_clarification(step)


async def on_clarify_skip(query: CallbackQuery, step: StepContext) -> None:
    """Skip the remaining questions."""
    await query.answer()
    await step.state.update_data({_CLARIFY: []})
    await _skip(step, OnboardingStep.clarify)


# ---- institution --------------------------------------------------------------------------


async def _city_id(step: StepContext) -> int | None:
    value = (await _data(step)).get(CITY_ID_KEY)
    return int(value) if value is not None else None


@register(OnboardingStep.institution)
async def show_institution(step: StepContext) -> None:
    """First institutions of the user's city."""
    await step.state.set_state(AboutSG.institution)
    city_id = await _city_id(step)
    items = [] if city_id is None else await step.api.search_institutions(step.tg_user.id, city_id)
    await step.screen.replace(*views.institutions(items, searched=False))


async def on_institution_search(message: Message, step: StepContext) -> None:
    """Typed name searches the city's institutions."""
    city_id = await _city_id(step)
    query = (message.text or "").strip()
    items = (
        []
        if city_id is None
        else await step.api.search_institutions(step.tg_user.id, city_id, query)
    )
    if not items:
        await message.answer(views.institution_none())
        return
    await step.screen.clear()
    await step.screen.show(*views.institutions(items, searched=True))


async def on_institution(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """PUT /profile/institution."""
    new_state = await step.api.set_institution(
        step.tg_user.id, InstitutionIn(institution_id=int(callback_data.value))
    )
    await query.answer()
    await advance(step, new_state)


async def on_institution_skip(query: CallbackQuery, step: StepContext) -> None:
    """Skip the institution."""
    await query.answer()
    await _skip(step, OnboardingStep.institution)


# ---- height -------------------------------------------------------------------------------


@register(OnboardingStep.height)
async def show_height(step: StepContext) -> None:
    """Typed height."""
    await step.state.set_state(AboutSG.height)
    await step.screen.replace(*views.height())


async def on_height(message: Message, step: StepContext) -> None:
    """Range check before the API, which checks again."""
    text = (message.text or "").strip()
    value = int(text) if text.isdecimal() else None
    if value is None or not HEIGHT_CM[0] <= value <= HEIGHT_CM[1]:
        await message.answer(views.height_range())
        return
    try:
        new_state = await step.api.set_height(step.tg_user.id, HeightIn(height_cm=value))
    except ApiException as exc:
        if exc.err.code is ErrorCode.validation_error:
            await message.answer(views.height_range())
            return
        raise
    await step.screen.clear()
    await advance(step, new_state)


async def on_height_skip(query: CallbackQuery, step: StepContext) -> None:
    """Skip the height."""
    await query.answer()
    await _skip(step, OnboardingStep.height)


# ---- prompts ------------------------------------------------------------------------------


async def _show_prompt_list(step: StepContext) -> None:
    answered = {a["prompt_id"] for a in (await _data(step)).get(_ANSWERS, [])}
    items = [p for p in await step.api.get_prompts(step.tg_user.id) if p.id not in answered]
    await step.state.set_state(AboutSG.prompt_pick)
    await step.screen.replace(*views.prompts(items))


@register(OnboardingStep.prompts)
async def show_prompts(step: StepContext) -> None:
    """Prompt list."""
    await step.state.update_data({_ANSWERS: []})
    await _show_prompt_list(step)


async def on_prompt_pick(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Ask for the answer of the chosen prompt."""
    prompts = await step.api.get_prompts(step.tg_user.id)
    prompt = next(p for p in prompts if str(p.id) == callback_data.value)
    await step.state.update_data({_PROMPT: {"id": prompt.id, "title": prompt.title}})
    await step.state.set_state(AboutSG.prompt_text)
    await query.answer()
    await step.screen.replace(views.prompt_answer(prompt.title))


async def on_prompt_text(message: Message, step: StepContext) -> None:
    """Save all answers so far; a blocked text keeps the user on this prompt."""
    text = (message.text or "").strip()
    if len(text) > PROMPT_TEXT_MAX:
        await message.answer(views.prompt_too_long())
        return
    data = await _data(step)
    current = data[_PROMPT]
    answers = [a for a in data.get(_ANSWERS, []) if a["prompt_id"] != current["id"]]
    answers.append({"prompt_id": current["id"], "text": text})
    body = PromptsIn(
        answers=[PromptAnswerIn(prompt_id=a["prompt_id"], text=a["text"]) for a in answers]
    )
    try:
        new_state = await step.api.set_prompts(step.tg_user.id, body)
    except ApiException as exc:
        if exc.err.code in {ErrorCode.content_blocked, ErrorCode.validation_error}:
            await message.answer(render_api_error(exc.err))
            return
        raise
    await step.state.update_data(
        {_ANSWERS: answers, "prompt_state": new_state.model_dump(mode="json")}
    )
    await step.screen.clear()
    if len(answers) >= PROMPTS_MAX:
        await advance(step, new_state)
        return
    await step.state.set_state(AboutSG.prompt_more)
    await step.screen.show(*views.prompt_more())


async def on_prompt_more(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Add one more prompt or finish."""
    await query.answer()
    if callback_data.value == views.ADD:
        await _show_prompt_list(step)
        return
    saved = (await _data(step)).get("prompt_state")
    await advance(step, UserState.model_validate(saved))


async def on_prompts_skip(query: CallbackQuery, step: StepContext) -> None:
    """Skip prompts; if one was already answered, keep it and move on."""
    await query.answer()
    saved = (await _data(step)).get("prompt_state")
    if saved is not None:
        await advance(step, UserState.model_validate(saved))
        return
    await _skip(step, OnboardingStep.prompts)


# ---- media --------------------------------------------------------------------------------


@register(OnboardingStep.media)
async def show_media(step: StepContext) -> None:
    """Up to MEDIA_MAX photos or videos."""
    await step.state.update_data({_MEDIA_COUNT: 0})
    await step.state.set_state(AboutSG.media)
    await step.screen.replace(*views.media())


async def on_media(message: Message, step: StepContext) -> None:
    """Each photo, also inside an album, is one POST /profile/media in arrival order."""
    if message.photo:
        best = message.photo[-1]
        body = MediaIn(
            kind=MediaKind.photo, file_id=best.file_id, file_unique_id=best.file_unique_id
        )
    elif message.video:
        body = MediaIn(
            kind=MediaKind.video,
            file_id=message.video.file_id,
            file_unique_id=message.video.file_unique_id,
        )
    else:
        await message.answer(views.media_wrong_type())
        return
    try:
        await step.api.add_media(step.tg_user.id, body)
    except ApiException as exc:
        await message.answer(render_api_error(exc.err))
        return
    count = int((await _data(step)).get(_MEDIA_COUNT, 0)) + 1
    await step.state.update_data({_MEDIA_COUNT: count})
    await step.screen.clear()
    await step.screen.show(*views.media_added(count))


async def on_media_done(query: CallbackQuery, step: StepContext) -> None:
    """«✅ Готово» or «⏭ Без фото»: the API has no other way to leave the media step."""
    await query.answer()
    await _skip(step, OnboardingStep.media)


async def nav_skip(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """⏭ buttons of the optional steps."""
    handlers = {
        views.CLARIFY: on_clarify_skip,
        views.INSTITUTION: on_institution_skip,
        views.HEIGHT: on_height_skip,
        views.PROMPT: on_prompts_skip,
    }
    handler = handlers.get(callback_data.screen)
    if handler is not None:
        await handler(query, step)
