"""Texts and keyboards of «Моя анкета» (FRONTEND.md S5)."""

from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.cards import MediaRef
from svoi_contracts.enums import ModerationStatus, OnboardingStep, UserStatus

from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option, nav_button

ME, PHOTOS, DELETE, RESET = "me", "photos", "me_delete", "me_reset"
EDIT_STEPS: dict[str, OnboardingStep] = {
    "name": OnboardingStep.name,
    "age": OnboardingStep.age,
    "city": OnboardingStep.city,
    "goals": OnboardingStep.goals,
    "interests": OnboardingStep.interests,
    "institution": OnboardingStep.institution,
    "height": OnboardingStep.height,
    "prompts": OnboardingStep.prompts,
}
YES, NO = "yes", "no"


def profile_buttons(status: UserStatus) -> InlineKeyboardMarkup:
    """Every field, then restart, hide or show, delete."""
    labels = [
        ("name", "me.edit.name"),
        ("age", "me.edit.age"),
        ("city", "me.edit.city"),
        ("goals", "me.edit.goals"),
        ("interests", "me.edit.interests"),
        ("institution", "me.edit.institution"),
        ("height", "me.edit.height"),
        ("prompts", "me.edit.prompts"),
        ("photos", "me.edit.photos"),
    ]
    buttons = [nav_button(_(key), ME, arg) for arg, key in labels]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    toggle = ("unhide", "me.unhide") if status is UserStatus.hidden else ("hide", "me.hide")
    rows.append([nav_button(_("me.reset"), ME, "reset")])
    rows.append([nav_button(_(toggle[1]), ME, toggle[0])])
    rows.append([nav_button(_("me.delete"), ME, "delete")])
    return keyboards.markup(rows)


def pending_note() -> str:
    """Shown after an edit that waits for moderation."""
    return _("me.pending")


def photos(media: list[MediaRef]) -> tuple[str, InlineKeyboardMarkup]:
    """Media list with delete per item, add, and «make first»."""
    lines = [_("me.photos.title")]
    for index, item in enumerate(media, start=1):
        kind = _("me.photos.photo") if item.kind.value == "photo" else _("me.photos.video")
        pending = item.moderation_status is ModerationStatus.pending
        lines.append(f"{index}. {kind}" + (f" · {_('me.photos.pending')}" if pending else ""))
    if not media:
        lines.append(_("me.photos.empty"))
    rows = (
        [[nav_button(f"🗑 {i}", PHOTOS, f"del-{m.id}") for i, m in enumerate(media, start=1)]]
        if media
        else []
    )
    if len(media) > 1:
        rows.append(
            [
                nav_button(f"↕️ {i}", PHOTOS, f"first-{m.id}")
                for i, m in enumerate(media, start=1)
                if i > 1
            ]
        )
    rows.append([nav_button(_("me.photos.add"), PHOTOS, "add")])
    rows.append([nav_button(_("ui.button.back"), PHOTOS, "back")])
    return "\n".join(lines), keyboards.markup(rows)


def confirm_delete() -> tuple[str, InlineKeyboardMarkup]:
    """Two taps to delete."""
    options = [Option(YES, _("me.delete.yes")), Option(NO, _("me.delete.no"))]
    return _("me.delete.ask"), keyboards.inline_choice(options, DELETE)


def deleted() -> str:
    """After DELETE /users/me."""
    return _("me.delete.done")


def confirm_reset() -> tuple[str, InlineKeyboardMarkup]:
    """Restart onboarding from the age step."""
    options = [Option(YES, _("me.reset.yes")), Option(NO, _("me.delete.no"))]
    return _("me.reset.ask"), keyboards.inline_choice(options, RESET)


def hidden() -> str:
    """After POST /profile/hide."""
    return _("me.hidden")


def shown() -> str:
    """After POST /profile/unhide."""
    return _("me.shown")
