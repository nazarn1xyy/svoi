"""Texts and keyboards of the city step (FRONTEND.md S2)."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from svoi_contracts.api.catalog import CityOut
from svoi_contracts.enums import OnboardingStep

from svoi_bot.features.onboarding.views import titled
from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option

PICK, GEO = "city", "city_geo"
OTHER, YES, NO = "other", "yes", "no"
QUERY_MIN = 2  # GET /catalog/cities/search requires q of at least 2 characters


def ask() -> tuple[str, ReplyKeyboardMarkup]:
    """Question, privacy note and the share-location button."""
    text = titled(OnboardingStep.city, _("city.ask")) + "\n\n" + _("city.privacy")
    return text, keyboards.location_request(_("city.type_instead"))


def type_instead_label() -> str:
    """Reply button for clients without location sharing."""
    return _("city.type_instead")


def type_hint() -> str:
    """After «напишу назву»."""
    return _("city.type_hint")


def too_short() -> str:
    """Query below QUERY_MIN; nothing is sent."""
    return _("city.too_short")


def not_found() -> str:
    """Search found nothing."""
    return _("city.not_found")


def location_failed() -> str:
    """by-location returned not_found."""
    return _("city.location_failed")


def _label(city: CityOut) -> str:
    return f"{city.name}, {city.region}"


def results(cities: list[CityOut]) -> tuple[str, InlineKeyboardMarkup]:
    """One hit: yes/other; several: a list plus «Інше»."""
    if len(cities) == 1:
        city = cities[0]
        options = [Option(str(city.id), _("city.yes")), Option(OTHER, _("city.other"))]
        return _("city.one", label=_label(city)), keyboards.inline_choice(options, PICK)
    options = [Option(str(c.id), _label(c)) for c in cities]
    options.append(Option(OTHER, _("city.other")))
    return _("city.many"), keyboards.inline_choice(options, PICK, columns=1)


def located(city: CityOut) -> tuple[str, InlineKeyboardMarkup]:
    """Confirm the city found by location."""
    options = [Option(YES, _("city.yes")), Option(NO, _("city.not_this"))]
    return _("city.located", name=city.name), keyboards.inline_choice(options, GEO)


def saved(name: str) -> str:
    """Shown with ReplyKeyboardRemove so the location button disappears."""
    return _("city.saved", name=name)
