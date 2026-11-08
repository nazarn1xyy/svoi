"""Texts and keyboards of S4 (FRONTEND.md S4)."""

from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.api.catalog import InstitutionOut, PromptOut
from svoi_contracts.api.profile import ClarificationOut
from svoi_contracts.constants import HEIGHT_CM, MEDIA_MAX
from svoi_contracts.enums import OnboardingStep

from svoi_bot.features.onboarding.views import titled
from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option

CLARIFY, INSTITUTION, HEIGHT, PROMPT, MORE, MEDIA, PREVIEW = (
    "clarify",
    "institution",
    "height",
    "prompt",
    "more",
    "media",
    "preview",
)
ADD, ENOUGH, DONE, OK, EDIT = "add", "enough", "done", "ok", "edit"
INSTITUTION_BUTTONS = 8


def clarification(item: ClarificationOut) -> tuple[str, InlineKeyboardMarkup]:
    """Question by question_key with the interest name, options and skip."""
    text = _(f"clarify.{item.question_key}", interest=item.interest_title)
    options = [Option(o.key, o.title) for o in item.options]
    return text, keyboards.inline_choice(options, CLARIFY, skip=True)


def institutions(items: list[InstitutionOut], searched: bool) -> tuple[str, InlineKeyboardMarkup]:
    """Up to 8 institutions of the city, a search hint and skip."""
    head = (
        _("about.institution.results")
        if searched
        else titled(OnboardingStep.institution, _("about.institution.ask"))
    )
    text = head + "\n\n" + _("about.institution.search_hint")
    options = [Option(str(i.id), i.short_name or i.name) for i in items[:INSTITUTION_BUTTONS]]
    return text, keyboards.inline_choice(options, INSTITUTION, columns=2, skip=True)


def institution_none() -> str:
    """Search found nothing."""
    return _("about.institution.none")


def height() -> tuple[str, InlineKeyboardMarkup]:
    """Typed height with skip."""
    text = titled(OnboardingStep.height, _("about.height.ask"))
    return text, keyboards.inline_choice([], HEIGHT, skip=True)


def height_range() -> str:
    """Outside HEIGHT_CM."""
    return _("about.height.range", low=HEIGHT_CM[0], high=HEIGHT_CM[1])


def prompts(items: list[PromptOut]) -> tuple[str, InlineKeyboardMarkup]:
    """Prompt list with skip."""
    text = titled(OnboardingStep.prompts, _("about.prompts.ask"))
    options = [Option(str(p.id), p.title) for p in items]
    return text, keyboards.inline_choice(options, PROMPT, columns=1, skip=True)


def prompt_answer(title: str) -> str:
    """Ask for the answer text."""
    return _("about.prompts.answer", title=title)


def prompt_too_long() -> str:
    """Over PROMPT_TEXT_MAX; nothing is sent."""
    return _("about.prompts.too_long")


def prompt_more() -> tuple[str, InlineKeyboardMarkup]:
    """Second prompt or done."""
    options = [Option(ADD, _("about.prompts.add")), Option(ENOUGH, _("about.prompts.enough"))]
    return _("about.prompts.more"), keyboards.inline_choice(options, MORE)


def media() -> tuple[str, InlineKeyboardMarkup]:
    """Photos or a short video, or none."""
    text = titled(OnboardingStep.media, _("about.media.ask"))
    return text, keyboards.inline_choice([Option(DONE, _("about.media.none"))], MEDIA)


def media_added(count: int) -> tuple[str, InlineKeyboardMarkup]:
    """Counter and «Готово»."""
    text = _("about.media.added", count=count, total=MEDIA_MAX)
    return text, keyboards.inline_choice([Option(DONE, _("about.media.done"))], MEDIA)


def media_wrong_type() -> str:
    """Not a photo or video."""
    return _("about.media.wrong_type")


def preview_head(needs_username: bool) -> str:
    """Above the own card."""
    head = _("about.preview.head")
    return (_("about.preview.username") + "\n\n" + head) if needs_username else head


def preview_buttons() -> InlineKeyboardMarkup:
    """Confirm or edit."""
    options = [Option(OK, _("about.preview.ok")), Option(EDIT, _("about.preview.edit"))]
    return keyboards.inline_choice(options, PREVIEW, columns=1)


def finished() -> str:
    """After POST /onboarding/complete."""
    return _("about.preview.finished")
