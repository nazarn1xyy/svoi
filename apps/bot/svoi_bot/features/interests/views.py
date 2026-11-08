"""Texts and keyboards of goals and interests (FRONTEND.md S3)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from svoi_contracts.api.catalog import CategoryOut, GoalOut, InterestOut
from svoi_contracts.constants import GOALS_COUNT, INTERESTS_COUNT
from svoi_contracts.enums import OnboardingStep

from svoi_bot.features.onboarding.views import titled
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import DoneCb
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option, nav_button

GOALS, INTERESTS = "goals", "interests"
CATEGORY_SCREEN = "cat"
CUSTOM, BACK = "custom", "back"


def goals(options: list[GoalOut], selected: tuple[str, ...]) -> tuple[str, InlineKeyboardMarkup]:
    """Goal multi-select."""
    text = titled(OnboardingStep.goals, _("interests.goals.ask"))
    buttons = [Option(g.code.value, f"{g.emoji} {g.title}") for g in options]
    return text, keyboards.multi_select(
        buttons,
        set(selected),
        GOALS,
        min_count=GOALS_COUNT[0],
        max_count=GOALS_COUNT[1],
        columns=1,
        page_size=len(buttons) or 1,
    )


def goals_hint() -> str:
    """Tapped an inactive «Готово»."""
    return _("interests.goals.min")


def categories(items: list[CategoryOut], count: int) -> tuple[str, InlineKeyboardMarkup]:
    """Categories in 2 columns, counter, custom tag, «Готово» from 3."""
    text = (
        titled(OnboardingStep.interests, _("interests.ask"))
        + "\n"
        + _("interests.counter", count=count)
    )
    buttons = [nav_button(f"{c.emoji} {c.title}", CATEGORY_SCREEN, str(c.id)) for c in items]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([nav_button(_("interests.custom"), INTERESTS, CUSTOM)])
    ready = INTERESTS_COUNT[0] <= count <= INTERESTS_COUNT[1]
    done = (
        InlineKeyboardButton(
            text=_("ui.button.done", count=count), callback_data=DoneCb(field=INTERESTS).pack()
        )
        if ready
        else nav_button(_("ui.button.done", count=count), INTERESTS, keyboards.NOOP)
    )
    rows.append([done])
    return text, keyboards.markup(rows)


def category(
    title: str, items: list[InterestOut], selected: tuple[str, ...], page: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Tags of one category, 12 per page, with a way back."""
    options = [Option(str(i.id), i.title) for i in items]
    markup = keyboards.multi_select(
        options,
        set(selected),
        INTERESTS,
        min_count=INTERESTS_COUNT[0],
        max_count=INTERESTS_COUNT[1],
        page=page,
    )
    rows = [*markup.inline_keyboard, [nav_button(_("ui.button.back"), INTERESTS, BACK)]]
    return f"{title}\n" + _("interests.counter", count=len(selected)), keyboards.markup(rows)


def too_many() -> str:
    """Alert on the 16th interest."""
    return _("interests.max")


def too_few() -> str:
    """Tapped an inactive «Готово»."""
    return _("interests.min")


def custom_ask() -> str:
    """Prompt for a custom tag."""
    return _("interests.custom_ask")


def custom_matched(title: str) -> str:
    """The tag already exists and joined the selection."""
    return _("interests.custom_matched", title=title)


def custom_pending(title: str) -> str:
    """A new tag waits for moderation."""
    return _("interests.custom_pending", title=title)


def custom_length() -> str:
    """Custom tag outside CUSTOM_INTEREST_LEN."""
    return _("interests.custom_length")
