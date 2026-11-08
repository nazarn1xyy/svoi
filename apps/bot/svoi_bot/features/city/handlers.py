"""City step handlers: text search, location, confirmation; works in onboarding and edit."""

from aiogram.types import CallbackQuery, Message
from svoi_contracts.api.catalog import CityOut
from svoi_contracts.api.profile import CityIn
from svoi_contracts.enums import OnboardingStep
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiException
from svoi_bot.features.city import views
from svoi_bot.features.city.states import CitySG
from svoi_bot.features.onboarding.registry import StepContext, advance, register
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import PickCb

_CITIES, _LOCATED, _COORDS = "city_results", "city_located", "city_coords"
SEARCH_LIMIT = 5
CITY_ID_KEY = "city_id"


@register(OnboardingStep.city)
async def show_city(step: StepContext) -> None:
    """Reply keyboard with the location button; a reply keyboard needs a new message."""
    await step.state.set_state(CitySG.input)
    await step.screen.clear()
    await step.screen.show(*views.ask())


async def on_text(message: Message, step: StepContext) -> None:
    """Search by name; under 2 characters never reaches the API."""
    query = (message.text or "").strip()
    if query == views.type_instead_label():
        await message.answer(views.type_hint())
        return
    if len(query) < views.QUERY_MIN:
        await message.answer(views.too_short())
        return
    cities = await step.api.search_cities(step.tg_user.id, query, limit=SEARCH_LIMIT)
    if not cities:
        await message.answer(views.not_found())
        return
    await step.state.update_data({_CITIES: [c.model_dump(mode="json") for c in cities]})
    await step.state.set_state(CitySG.confirm)
    await step.screen.show(*views.results(cities))


async def on_location(message: Message, step: StepContext) -> None:
    """Nearest city for the shared point."""
    if message.location is None:
        return
    lat, lon = message.location.latitude, message.location.longitude
    try:
        city = await step.api.city_by_location(step.tg_user.id, lat, lon)
    except ApiException as exc:
        if exc.err.code is ErrorCode.not_found:
            await message.answer(views.location_failed())
            return
        raise
    await step.state.update_data({_LOCATED: city.model_dump(mode="json"), _COORDS: [lat, lon]})
    await step.state.set_state(CitySG.confirm)
    await step.screen.show(*views.located(city))


async def _save(step: StepContext, city: CityOut, body: CityIn) -> None:
    new_state = await step.api.set_city(step.tg_user.id, body)
    # UserState has no city_id, and S4 needs it for institution search (CONTRACT GAP)
    await step.state.update_data({CITY_ID_KEY: city.id})
    await step.screen.clear()
    await step.bot.send_message(
        step.tg_user.id, views.saved(city.name), reply_markup=keyboards.remove()
    )
    await advance(step, new_state)


async def on_pick(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """A search result; coordinates are never sent for typed cities."""
    if callback_data.value == views.OTHER:
        await query.answer()
        await step.state.set_state(CitySG.input)
        await step.screen.replace(views.type_hint())
        return
    data = await step.state.get_data()
    cities = [CityOut.model_validate(c) for c in data.get(_CITIES, [])]
    city = next((c for c in cities if str(c.id) == callback_data.value), None)
    await query.answer()
    if city is not None:
        await _save(step, city, CityIn(city_id=city.id))


async def on_geo(query: CallbackQuery, callback_data: PickCb, step: StepContext) -> None:
    """Coordinates go to the API only when the user confirms the located city."""
    await query.answer()
    if callback_data.value == views.NO:
        await step.state.set_state(CitySG.input)
        await step.screen.replace(views.type_hint())
        return
    data = await step.state.get_data()
    city = CityOut.model_validate(data[_LOCATED])
    lat, lon = data[_COORDS]
    await _save(step, city, CityIn(city_id=city.id, lat=lat, lon=lon))
