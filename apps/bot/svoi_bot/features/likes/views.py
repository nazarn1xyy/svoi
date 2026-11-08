"""Texts and keyboards of incoming likes (FRONTEND.md S9)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from svoi_contracts.enums import ReportContext

from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import LikeCb, ReportCb
from svoi_bot.ui.i18n import _, n_
from svoi_bot.ui.keyboards import nav_button

LIKES = "likes"


def answer_buttons(like_id: int, from_user_id: int) -> InlineKeyboardMarkup:
    """Like back, decline, report."""
    report = ReportCb(target_id=from_user_id, reason="", context=ReportContext.incoming.value)
    return keyboards.markup(
        [
            [
                InlineKeyboardButton(
                    text=_("likes.accept"),
                    callback_data=LikeCb(action="accept", like_id=like_id).pack(),
                ),
                InlineKeyboardButton(
                    text=_("likes.decline"),
                    callback_data=LikeCb(action="decline", like_id=like_id).pack(),
                ),
                InlineKeyboardButton(text="⚠️", callback_data=report.pack()),
            ]
        ]
    )


def message_for_you(text: str) -> str:
    """Text attached to the like."""
    return _("likes.message", message=text)


def no_more() -> tuple[str, InlineKeyboardMarkup]:
    """Nothing left; offer the feed."""
    return _("likes.none"), keyboards.markup([[nav_button(_("ui.menu.search"), "feed", "open")]])


def notification(count: int) -> tuple[str, InlineKeyboardMarkup]:
    """bot.notify_likes text with plural forms."""
    text = _("likes.notify", people=n_("ui.people", count, count=count))
    rows = [
        [
            nav_button(_("likes.notify.look"), LIKES, "open"),
            nav_button(_("likes.notify.later"), LIKES, "later"),
        ]
    ]
    return text, keyboards.markup(rows)
