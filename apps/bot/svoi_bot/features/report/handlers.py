"""Report flow from the feed, incoming likes and contacts; «Інше» needs a text."""

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from svoi_contracts.api.moderation import BlockIn, ReportIn
from svoi_contracts.constants import REPORT_TEXT_MAX
from svoi_contracts.enums import ReportContext, ReportReason
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.contacts import handlers as contacts
from svoi_bot.features.feed import handlers as feed
from svoi_bot.features.likes import handlers as likes
from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import ReportCb
from svoi_bot.ui.errors import render_api_error
from svoi_bot.ui.format import reason_label
from svoi_bot.ui.i18n import _

BLOCK, CANCEL = "block", "cancel"
_PENDING = "report_pending"


class ReportSG(StatesGroup):
    """Waiting for the «Інше» description."""

    text = State()


def _button(text: str, target: int, reason: str, context: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, callback_data=ReportCb(target_id=target, reason=reason, context=context).pack()
    )


async def _back(step: StepContext, context: ReportContext) -> None:
    """Feed → next card; incoming → next like; contacts → the list."""
    if context is ReportContext.feed:
        await feed.next_card(step)
    elif context is ReportContext.incoming:
        await likes.on_open_after_report(step)
    else:
        await contacts.reopen(step)


async def on_report(query: CallbackQuery, callback_data: ReportCb, step: StepContext) -> None:
    """⚠️ → reasons; a reason → report; block; cancel."""
    await query.answer()
    target, reason, context = callback_data.target_id, callback_data.reason, callback_data.context
    if reason == "":
        rows = [[_button(reason_label(r), target, r.value, context)] for r in ReportReason]
        rows.append([_button(_("report.block"), target, BLOCK, context)])
        rows.append([_button(_("feed.message.cancel"), target, CANCEL, context)])
        await step.bot.send_message(
            step.tg_user.id, _("report.ask"), reply_markup=keyboards.markup(rows)
        )
        return
    if reason == CANCEL:
        await step.bot.send_message(step.tg_user.id, _("report.cancelled"))
        return
    if reason == BLOCK:
        await step.api.block(step.tg_user.id, BlockIn(target_id=target))
        await step.bot.send_message(step.tg_user.id, _("report.blocked"))
        await _back(step, ReportContext(context))
        return
    if reason == ReportReason.other.value:
        await step.state.update_data({_PENDING: [target, context]})
        await step.state.set_state(ReportSG.text)
        await step.bot.send_message(step.tg_user.id, _("report.describe"))
        return
    await _send(step, target, ReportReason(reason), ReportContext(context), None)


async def _send(
    step: StepContext, target: int, reason: ReportReason, context: ReportContext, text: str | None
) -> None:
    try:
        await step.api.report(
            step.tg_user.id, ReportIn(target_id=target, reason=reason, text=text, context=context)
        )
    except ApiException as exc:
        if exc.err.code is ErrorCode.conflict:
            await step.bot.send_message(step.tg_user.id, _("report.already"))
            return
        if exc.err.code is ErrorCode.content_blocked:
            await step.bot.send_message(step.tg_user.id, render_api_error(exc.err))
            return
        raise
    await step.bot.send_message(step.tg_user.id, _("report.thanks"))
    await _back(step, context)


async def on_text(message: Message, step: StepContext) -> None:
    """Description for «Інше»; an empty or too long one is not sent."""
    text = (message.text or "").strip()
    if not text:
        await message.answer(_("report.describe"))
        return
    if len(text) > REPORT_TEXT_MAX:
        await message.answer(_("report.too_long"))
        return
    target, context = (await step.state.get_data())[_PENDING]
    await step.state.set_state(None)
    await _send(step, int(target), ReportReason.other, ReportContext(context), text)
