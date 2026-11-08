"""Emoji captcha; after success the user continues from the exact FSM state they were in."""

from typing import Any

from aiogram.filters import Filter
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, TelegramObject
from svoi_contracts.api.safety import CaptchaAnswerIn
from svoi_contracts.cards import UserState
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.feed import handlers as feed
from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.middlewares import remember_state
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import PickCb
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option

CAPTCHA = "captcha"
_CHALLENGE, _RETURN = "captcha_id", "captcha_return"


class CaptchaSG(StatesGroup):
    """Solving a captcha."""

    solve = State()


class NeedsCaptcha(Filter):
    """UserState says so and the user is not already solving one."""

    async def __call__(
        self,
        event: TelegramObject,
        user_state: UserState | None = None,
        raw_state: str | None = None,
        **_: Any,
    ) -> bool:
        return (
            user_state is not None
            and user_state.captcha_required
            and raw_state != CaptchaSG.solve.state
        )


async def show_captcha(step: StepContext, prefix: str = "") -> None:
    """New challenge; remember where to return only the first time."""
    current = await step.state.get_state()
    if current != CaptchaSG.solve.state:
        await step.state.update_data({_RETURN: current})
    challenge = await step.api.captcha_new(step.tg_user.id)
    await step.state.update_data({_CHALLENGE: challenge.challenge_id})
    await step.state.set_state(CaptchaSG.solve)
    options = [Option(e, e) for e in challenge.options]
    text = (prefix + "\n\n" if prefix else "") + _("captcha.ask", emoji=challenge.target_emoji)
    await step.bot.send_message(
        step.tg_user.id, text, reply_markup=keyboards.inline_choice(options, CAPTCHA, columns=3)
    )


feed.captcha_screen.append(show_captcha)


async def gate(event: TelegramObject, step: StepContext) -> None:
    """Any update from a flagged user brings the captcha first."""
    if isinstance(event, CallbackQuery):
        await event.answer()
    await show_captcha(step)


async def on_answer(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Right → back to the saved state; wrong → a new one; expired → a new one."""
    await query.answer()
    challenge_id = (await step.state.get_data()).get(_CHALLENGE, "")
    try:
        new_state = await step.api.captcha_verify(
            step.tg_user.id, CaptchaAnswerIn(challenge_id=challenge_id, answer=callback_data.value)
        )
    except ApiException as exc:
        if exc.err.code is ErrorCode.validation_error:
            await show_captcha(step, _("captcha.wrong"))
            return
        if exc.err.code is ErrorCode.not_found:
            await show_captcha(step)
            return
        raise
    await remember_state(step.state, new_state)
    saved = (await step.state.get_data()).get(_RETURN)
    await step.state.set_state(saved)
    await step.bot.send_message(step.tg_user.id, _("captcha.ok"))
