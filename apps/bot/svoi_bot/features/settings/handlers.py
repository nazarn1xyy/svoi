"""Settings: every change is one PUT with the full model, then the screen redraws."""

from typing import cast

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.prefs import FiltersIn, FiltersOut, SettingsIn, SettingsOut
from svoi_contracts.api.users import LangIn
from svoi_contracts.enums import GenderFilter, Lang, NotifyFrequency, RadiusMode

from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.features.settings import views
from svoi_bot.features.settings.age import AgeAction, adjust, fixed
from svoi_bot.middlewares import remember_state
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.i18n import set_locale
from svoi_bot.ui.keyboards import BACK

AGE_ACTIONS = ("min_down", "min_up", "max_down", "max_up")


def _filters_in(f: FiltersOut, **change: object) -> FiltersIn:
    data = f.model_dump(exclude={"age_bounds"})
    data.update(change)
    return FiltersIn.model_validate(data)


def _settings_in(s: SettingsOut, **change: object) -> SettingsIn:
    data = s.model_dump()
    data.update(change)
    return SettingsIn.model_validate(data)


async def show_home(step: StepContext) -> None:
    """Summary screen."""
    filters = await step.api.get_filters(step.tg_user.id)
    settings = await step.api.get_settings(step.tg_user.id)
    await step.screen.replace(*views.main(filters, settings, step.user_state.lang))


async def on_open(message: Message, step: StepContext) -> None:
    """⚙️ Налаштування or /settings."""
    await step.state.set_state(None)
    await step.screen.clear()
    await show_home(step)


async def on_nav(query: CallbackQuery, callback_data: NavCb, step: StepContext) -> None:
    """Sub-screens, age buttons and privacy toggles."""
    await query.answer()
    arg, tg = callback_data.arg, step.tg_user.id
    if arg == "home":
        await show_home(step)
    elif arg == "age" or arg in AGE_ACTIONS:
        f = await step.api.get_filters(tg)
        if arg in AGE_ACTIONS and not fixed(f.age_bounds):
            low, high = adjust(f.age_min, f.age_max, f.age_bounds, cast(AgeAction, arg))
            if (low, high) != (f.age_min, f.age_max):
                f = await step.api.set_filters(tg, _filters_in(f, age_min=low, age_max=high))
        await step.screen.replace(*views.age(f, fixed(f.age_bounds)))
    elif arg == "gender":
        await step.screen.replace(*views.gender())
    elif arg == "radius":
        await step.screen.replace(*views.radius())
    elif arg == "verified":
        f = await step.api.get_filters(tg)
        await step.api.set_filters(tg, _filters_in(f, verified_only=not f.verified_only))
        await show_home(step)
    elif arg == "privacy":
        await step.screen.replace(*views.privacy(await step.api.get_settings(tg)))
    elif arg in ("t_distance", "t_institution"):
        s = await step.api.get_settings(tg)
        change = (
            {"show_distance": not s.show_distance}
            if arg == "t_distance"
            else {"show_institution": not s.show_institution}
        )
        s = await step.api.set_settings(tg, _settings_in(s, **change))
        await step.screen.replace(*views.privacy(s))
    elif arg == "notify":
        await step.screen.replace(*views.notify())
    elif arg == "lang":
        await step.screen.replace(*views.language())
    elif arg == BACK:
        await show_home(step)


async def on_pick(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Choices of the sub-screens."""
    await query.answer()
    tg, field, value = step.tg_user.id, callback_data.field, callback_data.value
    if field == views.GENDER:
        f = await step.api.get_filters(tg)
        await step.api.set_filters(tg, _filters_in(f, gender=GenderFilter(value)))
    elif field == views.RADIUS:
        f = await step.api.get_filters(tg)
        await step.api.set_filters(tg, _filters_in(f, radius=RadiusMode(value)))
    elif field == views.FREQ:
        s = await step.api.get_settings(tg)
        await step.api.set_settings(tg, _settings_in(s, notify_frequency=NotifyFrequency(value)))
    elif field == views.QUIET:
        s = await step.api.get_settings(tg)
        start, end = views.QUIET_OPTIONS[value]
        await step.api.set_settings(tg, _settings_in(s, quiet_from=start, quiet_to=end))
    elif field == views.LANG:
        new_state = await step.api.set_lang(tg, LangIn(lang=Lang(value)))
        await remember_state(step.state, new_state)
        set_locale(new_state.lang)
        step.user_state = new_state
    await show_home(step)


async def on_back(query: CallbackQuery, step: StepContext) -> None:
    """◀️ from a choice sub-screen."""
    await query.answer()
    await show_home(step)
