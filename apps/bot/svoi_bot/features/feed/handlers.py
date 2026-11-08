"""Feed: one card at a time; the reply buttons always act on the card on screen."""

from collections.abc import Awaitable, Callable

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.feed import ExpandIn, FeedEmpty, FeedItem, FeedResponse
from svoi_contracts.api.reactions import MessageMedia, ReactionIn, ReactionOut
from svoi_contracts.constants import LIKE_MEDIA_MAX_SECONDS, LIKE_MESSAGE_MAX
from svoi_contracts.enums import (
    FeedEmptyReason,
    MessageMediaKind,
    RadiusMode,
    ReactionType,
)
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.feed import views
from svoi_bot.features.feed.states import FeedSG
from svoi_bot.features.likes.match import send_match
from svoi_bot.features.onboarding.registry import StepContext, show_step
from svoi_bot.features.start.menu import send_menu
from svoi_bot.middlewares import remember_state
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import NavCb, ReactCb
from svoi_bot.ui.cards import render_card, send_card
from svoi_bot.ui.errors import render_api_error

TARGET, NAME, KEYBOARD, USERNAME_HINTED = "feed_target", "feed_name", "feed_kb", "feed_hinted"
# S9 puts «incoming likes first» here; S11 puts the captcha screen in captcha_screen
incoming_first: list[Callable[[StepContext], Awaitable[bool]]] = []
captcha_screen: list[Callable[[StepContext], Awaitable[None]]] = []


async def _render(step: StepContext, response: FeedResponse) -> None:
    if isinstance(response, FeedItem):
        await _show_item(step, response)
    else:
        await _show_empty(step, response)


async def _show_item(step: StepContext, item: FeedItem) -> None:
    data = await step.state.get_data()
    if not data.get(KEYBOARD):
        await step.bot.send_message(
            step.tg_user.id, views.keyboard_hint(), reply_markup=keyboards.feed_keyboard()
        )
    await step.state.update_data({TARGET: item.card.user_id, NAME: item.card.name, KEYBOARD: True})
    await step.state.set_state(FeedSG.viewing)
    await send_card(
        step.bot,
        step.tg_user.id,
        render_card(item.card, "feed"),
        views.card_buttons(item.card.user_id, item.can_undo),
    )


async def _show_empty(step: StepContext, empty: FeedEmpty) -> None:
    await step.state.update_data({TARGET: None, KEYBOARD: False})
    await step.state.set_state(None)
    tg = step.tg_user.id
    if empty.reason is FeedEmptyReason.no_candidates:
        text, markup = views.no_candidates(empty.expand_options)
    elif empty.reason is FeedEmptyReason.limit_reached:
        text, markup = views.limit_reached()
    elif empty.reason is FeedEmptyReason.profile_hidden:
        text, markup = views.profile_hidden()
    elif empty.reason is FeedEmptyReason.profile_incomplete:
        me = await step.api.get_me(tg)
        await show_step(step, me.onboarding_step)
        return
    else:
        # banned: FeedEmpty carries no date, so the neutral text without one
        await step.bot.send_message(tg, views.banned(), reply_markup=keyboards.remove())
        return
    await step.bot.send_message(tg, text, reply_markup=keyboards.remove())
    await step.bot.send_message(tg, "👇", reply_markup=markup)


async def next_card(step: StepContext) -> None:
    """GET /feed/next and show the result."""
    await _render(step, await step.api.feed_next(step.tg_user.id))


async def open_feed(step: StepContext) -> None:
    """Incoming likes first (S9), otherwise the feed."""
    for handler in incoming_first:
        if await handler(step):
            return
    await next_card(step)


async def on_open(message: Message, step: StepContext) -> None:
    """🔍 Дивитися анкети or /search."""
    await step.state.update_data({KEYBOARD: False})
    await open_feed(step)


async def _react(step: StepContext, body: ReactionIn) -> ReactionOut | None:
    """POST /reactions with the error rules of S8; None means «show the next card»."""
    try:
        return await step.api.react(step.tg_user.id, body)
    except ApiException as exc:
        code = exc.err.code
        if code is ErrorCode.conflict:
            return None
        if code is ErrorCode.captcha_required and captcha_screen:
            await captcha_screen[0](step)
            raise
        if code is ErrorCode.limit_reached:
            text, markup = views.limit_reached()
            await step.bot.send_message(step.tg_user.id, text, reply_markup=markup)
            raise
        raise


async def _after_like(step: StepContext, result: ReactionOut | None) -> None:
    if result is not None and result.match is not None:
        await send_match(step.bot, step.tg_user.id, result.match)
    data = await step.state.get_data()
    if step.user_state.needs_username and not data.get(USERNAME_HINTED):
        await step.state.update_data({USERNAME_HINTED: True})
        await step.bot.send_message(step.tg_user.id, views.username_hint())
    await next_card(step)


async def _take_target(step: StepContext) -> int | None:
    """Clear the current card before calling the API, so a double tap reacts once."""
    target = (await step.state.get_data()).get(TARGET)
    if target is not None:
        await step.state.update_data({TARGET: None})
    return int(target) if target is not None else None


async def on_like(message: Message, step: StepContext) -> None:
    """❤️"""
    target = await _take_target(step)
    if target is None:
        return
    result = await _react(step, ReactionIn(target_id=target, type=ReactionType.like))
    await _after_like(step, result)


async def on_skip(message: Message, step: StepContext) -> None:
    """👎"""
    target = await _take_target(step)
    if target is None:
        return
    await _react(step, ReactionIn(target_id=target, type=ReactionType.skip))
    await next_card(step)


async def on_message_start(message: Message, step: StepContext) -> None:
    """💌 asks for a text, voice or round video."""
    data = await step.state.get_data()
    if data.get(TARGET) is None:
        return
    await step.state.set_state(FeedSG.message)
    text, markup = views.ask_message(str(data.get(NAME, "")), step.user_state.pool)
    await step.bot.send_message(step.tg_user.id, text, reply_markup=markup)


def _media(message: Message) -> MessageMedia | None:
    if message.voice is not None:
        return MessageMedia(
            kind=MessageMediaKind.voice,
            file_id=message.voice.file_id,
            duration_s=message.voice.duration,
        )
    if message.video_note is not None:
        return MessageMedia(
            kind=MessageMediaKind.video_note,
            file_id=message.video_note.file_id,
            duration_s=message.video_note.duration,
        )
    return None


async def on_message_content(message: Message, step: StepContext) -> None:
    """Text, voice or round video becomes a like with a message."""
    recording = message.voice or message.video_note
    duration = recording.duration if recording is not None else 0
    if duration > LIKE_MEDIA_MAX_SECONDS:
        await message.answer(views.too_long_media())
        return
    text = (message.text or "").strip() or None
    if text is not None and len(text) > LIKE_MESSAGE_MAX:
        await message.answer(views.too_long_text())
        return
    media = _media(message)
    if text is None and media is None:
        return
    data = await step.state.get_data()
    target = data.get(TARGET)
    if target is None:
        return
    body = ReactionIn(target_id=int(target), type=ReactionType.like_msg, message=text, media=media)
    try:
        result = await step.api.react(step.tg_user.id, body)
    except ApiException as exc:
        if exc.err.code is ErrorCode.content_blocked:
            await message.answer(views.contacts_later())
            return
        if exc.err.code is ErrorCode.media_forbidden:
            await message.answer(render_api_error(exc.err))
            return
        raise
    await step.state.update_data({TARGET: None})
    await step.state.set_state(FeedSG.viewing)
    await message.answer(views.message_sent())
    await _after_like(step, result)


async def on_pause(message: Message, step: StepContext) -> None:
    """💤 or /pause: back to the menu."""
    await step.state.set_state(None)
    await step.state.update_data({TARGET: None, KEYBOARD: False})
    await send_menu(step.bot, step.api, step.tg_user.id, views.paused())


async def on_nav(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Expand search, later, unhide, cancel a message."""
    await query.answer()
    arg = callback_data.arg
    if arg.startswith("expand-"):
        radius = RadiusMode(arg.removeprefix("expand-"))
        await step.state.update_data({KEYBOARD: False})
        await _render(step, await step.api.feed_expand(step.tg_user.id, ExpandIn(radius=radius)))
    elif arg == "later":
        await send_menu(step.bot, step.api, step.tg_user.id, views.paused())
    elif arg == "unhide":
        await remember_state(step.state, await step.api.unhide_profile(step.tg_user.id))
        await step.state.update_data({KEYBOARD: False})
        await next_card(step)
    elif arg == "cancel":
        await step.state.set_state(FeedSG.viewing)
        await step.bot.send_message(
            step.tg_user.id, views.keyboard_hint(), reply_markup=keyboards.feed_keyboard()
        )


async def on_undo(query: CallbackQuery, callback_data: ReactCb, step: StepContext) -> None:
    """↩️ (1.1): the skipped card comes back while UNDO_WINDOW_SECONDS lasts."""
    try:
        item = await step.api.undo_reaction(step.tg_user.id)
    except ApiException as exc:
        if exc.err.code is ErrorCode.undo_unavailable:
            await query.answer(render_api_error(exc.err), show_alert=True)
            return
        raise
    await query.answer()
    await _show_item(step, item)
