"""Incoming likes: shown before the feed; answering never notifies a declined author."""

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.likes import IncomingLike, RespondIn
from svoi_contracts.enums import LikeDecision, MessageMediaKind

from svoi_bot.features.feed import handlers as feed
from svoi_bot.features.likes import views
from svoi_bot.features.likes.match import send_match
from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.ui.callbacks import LikeCb, NavCb
from svoi_bot.ui.cards import render_card, send_card


async def show_next(step: StepContext) -> bool:
    """Next incoming like; False when there is none."""
    response = await step.api.incoming_next(step.tg_user.id)
    if not isinstance(response, IncomingLike):
        return False
    chat = step.tg_user.id
    await send_card(
        step.bot,
        chat,
        render_card(response.card, "incoming"),
        views.answer_buttons(response.like_id, response.card.user_id),
    )
    if response.message:
        await step.bot.send_message(chat, views.message_for_you(response.message))
    if response.media is not None:
        if response.media.kind is MessageMediaKind.voice:
            await step.bot.send_voice(chat, response.media.file_id)
        else:
            await step.bot.send_video_note(chat, response.media.file_id)
    return True


async def incoming_first(step: StepContext) -> bool:
    """Feed hook: incoming likes come before the feed."""
    if (await step.api.incoming_count(step.tg_user.id)).count == 0:
        return False
    return await show_next(step)


feed.incoming_first.append(incoming_first)


async def _show_or_done(step: StepContext) -> None:
    if not await show_next(step):
        text, markup = views.no_more()
        await step.bot.send_message(step.tg_user.id, text, reply_markup=markup)


async def on_open(message: Message, step: StepContext) -> None:
    """❤️ Мене лайкнули or /likes."""
    await step.state.set_state(None)
    await _show_or_done(step)


async def on_answer(query: CallbackQuery, callback_data: LikeCb, step: StepContext) -> None:
    """Accept → match screen; decline → next like, the author is never told."""
    decision = LikeDecision.accept if callback_data.action == "accept" else LikeDecision.decline
    result = await step.api.respond_like(
        step.tg_user.id, callback_data.like_id, RespondIn(decision=decision)
    )
    await query.answer()
    if result.match is not None:
        await send_match(step.bot, step.tg_user.id, result.match)
    await _show_or_done(step)


async def on_nav(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """👀 from the notification opens the likes; ⏰ just closes the alert."""
    await query.answer()
    if callback_data.arg == "open":
        await _show_or_done(step)


async def on_open_after_report(step: StepContext) -> None:
    """After reporting a liker: the next incoming like or «Це всі»."""
    await _show_or_done(step)
