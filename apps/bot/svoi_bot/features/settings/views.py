"""Texts and keyboards of settings (FRONTEND.md S6)."""

from datetime import time

from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.api.prefs import FiltersOut, SettingsOut
from svoi_contracts.enums import GenderFilter, Lang, NotifyFrequency, RadiusMode

from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option, nav_button

SET, GENDER, RADIUS, FREQ, QUIET, LANG = (
    "set",
    "set_gender",
    "set_radius",
    "set_freq",
    "set_quiet",
    "set_lang",
)
QUIET_OPTIONS: dict[str, tuple[time, time]] = {
    "23-08": (time(23, 0), time(8, 0)),
    "22-09": (time(22, 0), time(9, 0)),
    "off": (time(0, 0), time(0, 0)),  # from == to means no quiet hours
}
LANG_LABELS = {Lang.uk: "🇺🇦 Українська", Lang.en: "🇬🇧 English", Lang.ru: "🇷🇺 Русский"}


def _yes(flag: bool) -> str:
    return _("settings.on") if flag else _("settings.off")


def _quiet(s: SettingsOut) -> str:
    if s.quiet_from == s.quiet_to:
        return _("settings.quiet.off")
    return f"{s.quiet_from:%H:%M}–{s.quiet_to:%H:%M}"


def main(f: FiltersOut, s: SettingsOut, lang: Lang) -> tuple[str, InlineKeyboardMarkup]:
    """Current values with one button per setting."""
    age = _("settings.age", low=f.age_min, high=f.age_max)
    gender = _("settings.gender", value=_(f"settings.gender.{f.gender.value}"))
    radius = _("settings.radius", value=_(f"settings.radius.{f.radius.value}"))
    verified = _("settings.verified", value=_yes(f.verified_only))
    privacy = _(
        "settings.privacy", distance=_yes(s.show_distance), institution=_yes(s.show_institution)
    )
    notify = _(
        "settings.notify", value=_(f"settings.freq.{s.notify_frequency.value}"), quiet=_quiet(s)
    )
    language = _("settings.lang", value=LANG_LABELS[lang])
    text = "\n".join(
        [_("settings.title"), age, gender, radius, verified, privacy, notify, language]
    )
    rows = [
        [nav_button(age, SET, "age")],
        [nav_button(gender, SET, "gender")],
        [nav_button(radius, SET, "radius")],
        [nav_button(verified, SET, "verified")],
        [nav_button(_("settings.privacy_button"), SET, "privacy")],
        [nav_button(_("settings.notify_button"), SET, "notify")],
        [nav_button(_("settings.lang_button"), SET, "lang")],
    ]
    return text, keyboards.markup(rows)


def age(f: FiltersOut, fixed: bool) -> tuple[str, InlineKeyboardMarkup]:
    """Range buttons; the 16-17 pool only gets the explanation."""
    text = _("settings.age", low=f.age_min, high=f.age_max)
    if fixed:
        text += "\n\n" + _("settings.age_fixed")
        return text, keyboards.markup([[nav_button(_("ui.button.back"), SET, "home")]])
    rows = [
        [
            nav_button(_("settings.min_down"), SET, "min_down"),
            nav_button(_("settings.min_up"), SET, "min_up"),
        ],
        [
            nav_button(_("settings.max_down"), SET, "max_down"),
            nav_button(_("settings.max_up"), SET, "max_up"),
        ],
        [nav_button(_("ui.button.back"), SET, "home")],
    ]
    return text, keyboards.markup(rows)


def choice(
    field: str, title: str, values: list[str], prefix: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Single choice sub-screen."""
    options = [Option(v, _(f"{prefix}.{v}")) for v in values]
    return title, keyboards.inline_choice(options, field, columns=1, back=True)


def gender() -> tuple[str, InlineKeyboardMarkup]:
    """Who to talk to."""
    return choice(
        GENDER, _("settings.gender_title"), [g.value for g in GenderFilter], "settings.gender_pick"
    )


def radius() -> tuple[str, InlineKeyboardMarkup]:
    """Where to search."""
    return choice(
        RADIUS, _("settings.radius_title"), [r.value for r in RadiusMode], "settings.radius"
    )


def notify() -> tuple[str, InlineKeyboardMarkup]:
    """Frequency and quiet hours."""
    freq = [Option(f.value, _(f"settings.freq.{f.value}")) for f in NotifyFrequency]
    quiet = [Option(k, _(f"settings.quiet_pick.{k}")) for k in QUIET_OPTIONS]
    a = keyboards.inline_choice(freq, FREQ, columns=3).inline_keyboard
    b = keyboards.inline_choice(quiet, QUIET, columns=1, back=True).inline_keyboard
    return _("settings.notify_title"), keyboards.markup([*a, *b])


def privacy(s: SettingsOut) -> tuple[str, InlineKeyboardMarkup]:
    """Two toggles."""
    rows = [
        [nav_button(_("settings.show_distance", value=_yes(s.show_distance)), SET, "t_distance")],
        [
            nav_button(
                _("settings.show_institution", value=_yes(s.show_institution)), SET, "t_institution"
            )
        ],
        [nav_button(_("ui.button.back"), SET, "home")],
    ]
    return _("settings.privacy_title"), keyboards.markup(rows)


def language() -> tuple[str, InlineKeyboardMarkup]:
    """Language list."""
    options = [Option(lang.value, label) for lang, label in LANG_LABELS.items()]
    return _("onboarding.lang.ask"), keyboards.inline_choice(options, LANG, columns=1, back=True)
