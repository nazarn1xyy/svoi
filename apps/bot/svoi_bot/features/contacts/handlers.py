"""Contacts: 10 per page by the API cursor; a contact offers write, delete, report."""

from typing import Any

from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from svoi_contracts.api.likes import ContactOut
from svoi_contracts.enums import ReportContext

from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import NavCb, PageCb, ReportCb
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import nav_button, url_button

CONTACTS, PAGE_SIZE = "contacts", 10
_CURSORS, _ITEMS = "contact_cursors", "contact_items"


async def _show_page(step: StepContext, page: int) -> None:
    data: dict[str, Any] = await step.state.get_data()
    cursors: list[str | None] = data.get(_CURSORS) or [None]
    result = await step.api.get_contacts(step.tg_user.id, cursor=cursors[page], limit=PAGE_SIZE)
    if result.next_cursor is not None and len(cursors) == page + 1:
        cursors.append(result.next_cursor)
    items = {str(c.match_id): c.model_dump(mode="json") for c in result.items}
    await step.state.update_data({_CURSORS: cursors, _ITEMS: items})
    if not result.items and page == 0:
        await step.screen.replace(_("contacts.empty"))
        return
    rows = [
        [
            nav_button(
                _("contacts.row", name=c.partner.name, age=c.partner.age, city=c.partner.city_name),
                CONTACTS,
                str(c.match_id),
            )
        ]
        for c in result.items
    ]
    pager = []
    if page > 0:
        pager.append(
            InlineKeyboardButton(
                text="◀️", callback_data=PageCb(field=CONTACTS, page=page - 1).pack()
            )
        )
    if result.next_cursor is not None:
        pager.append(
            InlineKeyboardButton(
                text="▶️", callback_data=PageCb(field=CONTACTS, page=page + 1).pack()
            )
        )
    if pager:
        rows.append(pager)
    await step.screen.replace(_("contacts.title"), keyboards.markup(rows))


async def on_open(message: Message, step: StepContext) -> None:
    """🤝 Мої контакти or /contacts."""
    await step.state.set_state(None)
    await step.state.update_data({_CURSORS: [None]})
    await step.screen.clear()
    await _show_page(step, 0)


async def on_page(query: CallbackQuery, callback_data: PageCb, step: StepContext) -> None:
    """◀️ ▶️"""
    await query.answer()
    await _show_page(step, callback_data.page)


async def on_contact(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """One contact, or its delete action."""
    await query.answer()
    arg = callback_data.arg
    if arg.startswith("del-"):
        await step.api.delete_contact(step.tg_user.id, int(arg.removeprefix("del-")))
        await step.state.update_data({_CURSORS: [None]})
        await _show_page(step, 0)
        return
    if arg == "back":
        await _show_page(step, 0)
        return
    raw = (await step.state.get_data()).get(_ITEMS, {}).get(arg)
    if raw is None:
        return
    contact = ContactOut.model_validate(raw)
    url = (
        f"https://t.me/{contact.partner_username}"
        if contact.partner_username
        else f"tg://user?id={contact.partner_tg_id}"
    )
    report = ReportCb(
        target_id=contact.partner.user_id, reason="", context=ReportContext.contact.value
    ).pack()
    rows = [
        [url_button(_("match.write"), url)],
        [nav_button(_("contacts.delete"), CONTACTS, f"del-{contact.match_id}")],
        [InlineKeyboardButton(text=_("feed.report"), callback_data=report)],
        [nav_button(_("ui.button.back"), CONTACTS, "back")],
    ]
    title = _(
        "contacts.row",
        name=contact.partner.name,
        age=contact.partner.age,
        city=contact.partner.city_name,
    )
    await step.screen.replace(title, keyboards.markup(rows))
