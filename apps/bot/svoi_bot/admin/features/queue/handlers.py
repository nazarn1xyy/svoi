"""Moderation queues: one item at a time, one POST /admin/actions per decision."""

from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.admin import AdminActionIn
from svoi_contracts.enums import AdminAction, AdminQueueKind, MediaKind

from svoi_bot.admin.features.queue import views
from svoi_bot.api_client import ApiClient, ApiException
from svoi_bot.ui.callbacks import AdminCb
from svoi_bot.ui.cards import render_card, send_card
from svoi_bot.ui.errors import render_api_error
from svoi_bot.ui.i18n import _

METRICS_DEFAULT_DAYS = 7


async def show_home(bot: Bot, api: ApiClient, tg_id: int) -> None:
    """«Черги модерації» with counters."""
    stats = await api.admin_queue_stats(tg_id)
    text, markup = views.home(stats)
    await bot.send_message(tg_id, text, reply_markup=markup)


async def show_next(bot: Bot, api: ApiClient, tg_id: int, kind: AdminQueueKind) -> None:
    """Oldest item of a queue, or «Черга порожня 🎉»."""
    item = await api.admin_queue(tg_id, kind)
    if item is None:
        await bot.send_message(tg_id, views.empty())
        await show_home(bot, api, tg_id)
        return
    if item.kind is AdminQueueKind.photos and item.media is not None:
        send = bot.send_video if item.media.kind is MediaKind.video else bot.send_photo
        await send(tg_id, item.media.file_id)
    if item.kind is AdminQueueKind.verifications and item.verification_file_id:
        await bot.send_video_note(tg_id, item.verification_file_id)
    await send_card(bot, tg_id, render_card(item.target_card, "admin"), None)
    await bot.send_message(
        tg_id, views.item_text(item) or "—", reply_markup=views.item_buttons(item)
    )


async def on_home(message: Message, bot: Bot, api: ApiClient) -> None:
    """/admin."""
    assert message.from_user is not None  # noqa: S101 - private chats always have a sender
    await show_home(bot, api, message.from_user.id)


async def on_callback(
    query: CallbackQuery, callback_data: AdminCb, bot: Bot, api: ApiClient
) -> None:
    """Open a queue, ask to confirm, or apply an action and show the next item."""
    tg_id, kind = query.from_user.id, AdminQueueKind(callback_data.kind)
    await query.answer()
    action = callback_data.action
    if action == "home":
        await show_home(bot, api, tg_id)
        return
    if action == "queue":
        await show_next(bot, api, tg_id, kind)
        return
    confirmed = action.startswith("y_")
    decision = AdminAction(action.removeprefix("y_"))
    if decision in views.NEEDS_CONFIRM and not confirmed:
        text, markup = views.confirm(decision, callback_data)
        await bot.send_message(tg_id, text, reply_markup=markup)
        return
    try:
        await api.admin_action(
            tg_id, AdminActionIn(kind=kind, item_id=callback_data.item_id, action=decision)
        )
    except ApiException as exc:
        await bot.send_message(tg_id, render_api_error(exc.err))
    await show_next(bot, api, tg_id, kind)


async def on_user(message: Message, command: CommandObject, api: ApiClient) -> None:
    """/user <tg_id>."""
    assert message.from_user is not None  # noqa: S101 - private chats always have a sender
    raw = (command.args or "").strip()
    if not raw.isdecimal():
        await message.answer(_("admin.user_usage"))
        return
    try:
        out = await api.admin_user(message.from_user.id, int(raw))
    except ApiException as exc:
        await message.answer(render_api_error(exc.err))
        return
    await message.answer(views.user(out))


async def on_metrics(message: Message, command: CommandObject, api: ApiClient) -> None:
    """/metrics [days], 7 by default, 1..90."""
    assert message.from_user is not None  # noqa: S101 - private chats always have a sender
    raw = (command.args or "").strip()
    days = int(raw) if raw.isdecimal() else METRICS_DEFAULT_DAYS
    days = min(max(days, 1), 90)
    await message.answer(views.metrics(await api.admin_metrics(message.from_user.id, days)))
