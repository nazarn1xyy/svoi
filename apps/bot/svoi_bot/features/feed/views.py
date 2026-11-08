"""Texts and keyboards of the feed (FRONTEND.md S7/S8)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from svoi_contracts.enums import Pool, RadiusMode, ReportContext

from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import ReactCb, ReportCb
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import nav_button

LIKE, MESSAGE, SKIP, PAUSE = "❤️", "💌", "👎", "💤"
FEED = "feed"
EXPAND_KEYS = {
    RadiusMode.km50: "feed.expand.km50",
    RadiusMode.region: "feed.expand.region",
    RadiusMode.country: "feed.expand.country",
    RadiusMode.any_online: "feed.expand.any_online",
}


def card_buttons(target_id: int, can_undo: bool) -> InlineKeyboardMarkup:
    """⚠️ under every card, ↩️ when undo is possible (1.1)."""
    report = ReportCb(target_id=target_id, reason="", context=ReportContext.feed.value).pack()
    row = [InlineKeyboardButton(text=_("feed.report"), callback_data=report)]
    if can_undo:
        row.append(
            InlineKeyboardButton(
                text=_("feed.undo"),
                callback_data=ReactCb(action="undo", target_id=target_id).pack(),
            )
        )
    return keyboards.markup([row])


def keyboard_hint() -> str:
    """Sent once with the reaction keyboard."""
    return _("feed.keyboard")


def ask_message(name: str, pool: Pool | None) -> tuple[str, InlineKeyboardMarkup]:
    """💌 prompt; minors are not offered voice or round videos."""
    key = "feed.message.minor" if pool is Pool.minor else "feed.message.adult"
    cancel = nav_button(_("feed.message.cancel"), FEED, "cancel")
    return _(key, name=name), keyboards.markup([[cancel]])


def message_sent() -> str:
    """After a like with a message."""
    return _("feed.message.sent")


def too_long_media() -> str:
    """Voice or round video over 30 s."""
    return _("feed.message.too_long_media")


def too_long_text() -> str:
    """Text over LIKE_MESSAGE_MAX."""
    return _("feed.message.too_long_text")


def contacts_later() -> str:
    """Links, @ or phones in a like message."""
    return _("feed.message.contacts_later")


def username_hint() -> str:
    """Once per session after the first like without a username."""
    return _("about.preview.username")


def paused() -> str:
    """💤 or /pause."""
    return _("feed.paused")


def no_candidates(options: list[RadiusMode]) -> tuple[str, InlineKeyboardMarkup]:
    """Offer only the expansions the API returned, plus «⏰ Пізніше»."""
    rows = [
        [nav_button(_(EXPAND_KEYS[o]), FEED, f"expand-{o.value}")]
        for o in options
        if o in EXPAND_KEYS
    ]
    rows.append([nav_button(_("feed.later"), FEED, "later")])
    return _("feed.empty.no_candidates"), keyboards.markup(rows)


def limit_reached() -> tuple[str, InlineKeyboardMarkup]:
    """Daily limit with the invite button (S14)."""
    return _("errors.limit_reached"), keyboards.markup(
        [[nav_button(_("feed.invite"), "referral", "open")]]
    )


def profile_hidden() -> tuple[str, InlineKeyboardMarkup]:
    """Feed is off while the own profile is hidden."""
    return _("feed.empty.hidden"), keyboards.markup(
        [[nav_button(_("feed.unhide"), FEED, "unhide")]]
    )


def banned() -> str:
    """FeedEmpty(banned)."""
    return _("feed.empty.banned")
