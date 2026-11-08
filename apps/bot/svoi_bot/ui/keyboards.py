"""Keyboards built only here so every screen looks the same."""

from collections.abc import Sequence
from dataclasses import dataclass

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from svoi_contracts.cards import Counters

from svoi_bot.ui.callbacks import DoneCb, NavCb, PageCb, PickCb, ToggleCb
from svoi_bot.ui.i18n import _

SKIP, BACK, NOOP = "skip", "back", "noop"


@dataclass(frozen=True)
class Option:
    """One choice: callback value and button label."""

    value: str
    label: str


def _rows(buttons: list[InlineKeyboardButton], columns: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + columns] for i in range(0, len(buttons), columns)]


def nav_button(text: str, screen: str, arg: str = "") -> InlineKeyboardButton:
    """Button that sends NavCb(screen, arg)."""
    return InlineKeyboardButton(text=text, callback_data=NavCb(screen=screen, arg=arg).pack())


def url_button(text: str, url: str) -> InlineKeyboardButton:
    """Button that opens a link."""
    return InlineKeyboardButton(text=text, url=url)


def markup(rows: Sequence[Sequence[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Inline markup from prepared rows."""
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def inline_choice(
    options: Sequence[Option],
    field: str,
    columns: int = 2,
    back: bool = False,
    skip: bool = False,
) -> InlineKeyboardMarkup:
    """Single choice; skip and back go in their own rows."""
    buttons = [
        InlineKeyboardButton(text=o.label, callback_data=PickCb(field=field, value=o.value).pack())
        for o in options
    ]
    rows = _rows(buttons, columns)
    if skip:
        rows.append([nav_button(_("ui.button.skip"), field, SKIP)])
    if back:
        rows.append([nav_button(_("ui.button.back"), field, BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def multi_select(  # noqa: PLR0913 - signature fixed by tech.md section 9
    options: Sequence[Option],
    selected: set[str],
    field: str,
    columns: int = 2,
    *,
    min_count: int,
    max_count: int,
    page: int = 0,
    page_size: int = 12,
) -> InlineKeyboardMarkup:
    """Toggles with ✅, pages, and «Готово (N)» that only confirms inside [min, max]."""
    chunk = options[page * page_size : (page + 1) * page_size]
    buttons = [
        InlineKeyboardButton(
            text=f"✅ {o.label}" if o.value in selected else o.label,
            callback_data=ToggleCb(field=field, value=o.value).pack(),
        )
        for o in chunk
    ]
    rows = _rows(buttons, columns)
    pager = []
    if page > 0:
        pager.append(
            InlineKeyboardButton(text="◀️", callback_data=PageCb(field=field, page=page - 1).pack())
        )
    if (page + 1) * page_size < len(options):
        pager.append(
            InlineKeyboardButton(text="▶️", callback_data=PageCb(field=field, page=page + 1).pack())
        )
    if pager:
        rows.append(pager)
    count = len(selected)
    ready = min_count <= count <= max_count
    done_data = DoneCb(field=field).pack() if ready else NavCb(screen=field, arg=NOOP).pack()
    rows.append(
        [InlineKeyboardButton(text=_("ui.button.done", count=count), callback_data=done_data)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu(counters: Counters) -> ReplyKeyboardMarkup:
    """Persistent menu; the likes button shows the incoming count."""
    likes = (
        _("ui.menu.likes_count", count=counters.incoming_likes)
        if counters.incoming_likes > 0
        else _("ui.menu.likes")
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("ui.menu.search")), KeyboardButton(text=likes)],
            [KeyboardButton(text=_("ui.menu.profile")), KeyboardButton(text=_("ui.menu.contacts"))],
            [KeyboardButton(text=_("ui.menu.settings"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


FEED_BUTTONS = ("❤️", "💌", "👎", "💤")


def feed_keyboard() -> ReplyKeyboardMarkup:
    """Reactions under a feed card."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in FEED_BUTTONS]], resize_keyboard=True
    )


def location_request(skip_label: str) -> ReplyKeyboardMarkup:
    """Share-location button plus a text fallback for desktop clients."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("ui.button.send_location"), request_location=True)],
            [KeyboardButton(text=skip_label)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm(yes: str, no: str, field: str) -> InlineKeyboardMarkup:
    """Yes / no in one row."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=yes, callback_data=PickCb(field=field, value="yes").pack()
                ),
                InlineKeyboardButton(text=no, callback_data=PickCb(field=field, value="no").pack()),
            ]
        ]
    )


def remove() -> ReplyKeyboardRemove:
    """Hide the reply keyboard."""
    return ReplyKeyboardRemove(remove_keyboard=True)
