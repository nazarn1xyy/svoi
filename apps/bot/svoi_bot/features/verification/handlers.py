"""/verify: show a gesture, accept only a round video, report conflicts in plain words."""

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.verification import VerificationIn
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.ui.format import gesture_label
from svoi_bot.ui.i18n import _

_ID = "verification_id"
CONFLICT_REASONS = ("already_verified", "pending", "no_photo")


class VerifySG(StatesGroup):
    """Waiting for the round video."""

    video = State()


async def start(step: StepContext) -> None:
    """POST /verification/start; conflicts get their own text."""
    try:
        gesture = await step.api.verification_start(step.tg_user.id)
    except ApiException as exc:
        reason = (exc.err.details or {}).get("reason")
        if exc.err.code is ErrorCode.conflict and reason in CONFLICT_REASONS:
            await step.bot.send_message(step.tg_user.id, _(f"verify.conflict.{reason}"))
            return
        raise
    await step.state.update_data({_ID: gesture.verification_id})
    await step.state.set_state(VerifySG.video)
    await step.bot.send_message(
        step.tg_user.id, _("verify.ask", gesture=gesture_label(gesture.gesture))
    )


async def on_command(message: Message, step: StepContext) -> None:
    """/verify."""
    await start(step)


async def on_button(query: CallbackQuery, step: StepContext) -> None:
    """✅ Верифікація in «Моя анкета»."""
    await query.answer()
    await start(step)


async def on_video_note(message: Message, step: StepContext) -> None:
    """Submit the round video."""
    if message.video_note is None:
        await message.answer(_("verify.round_only"))
        return
    verification_id = int((await step.state.get_data())[_ID])
    try:
        await step.api.verification_submit(
            step.tg_user.id,
            VerificationIn(
                verification_id=verification_id, video_note_file_id=message.video_note.file_id
            ),
        )
    except ApiException as exc:
        reason = (exc.err.details or {}).get("reason")
        if exc.err.code is ErrorCode.conflict and reason in CONFLICT_REASONS:
            await message.answer(_(f"verify.conflict.{reason}"))
            await step.state.set_state(None)
            return
        raise
    await step.state.set_state(None)
    await message.answer(_("verify.sent"))
