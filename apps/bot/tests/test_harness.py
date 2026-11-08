"""K11 acceptance: BotHarness drives the real dispatcher and records what the bot sends."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from harness import BotHarness
from svoi_bot.api_client import ApiClient
from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import PickCb


class _Probe(StatesGroup):
    picked = State()


def _probe_router() -> Router:
    router = Router(name="probe")

    @router.message(F.text == "ping")
    async def ping(message: Message) -> None:
        await message.answer("pong", reply_markup=keyboards.confirm("Yes", "No", "probe"))

    @router.callback_query(PickCb.filter(F.field == "probe"))
    async def picked(query: CallbackQuery, callback_data: PickCb, state: FSMContext) -> None:
        await state.set_state(_Probe.picked)
        await state.update_data(choice=callback_data.value)
        await query.answer("saved")

    @router.message(F.text == "me")
    async def me(message: Message, api: ApiClient) -> None:
        state = await api.get_me(message.chat.id)
        await message.answer(f"step {state.onboarding_step}")

    @router.message(F.photo | F.voice | F.video_note | F.location)
    async def media(message: Message) -> None:
        kind = next(
            k
            for k in ("photo", "voice", "video_note", "location")
            if getattr(message, k) is not None
        )
        await message.answer(kind)

    return router


async def test_kitchen_sink_shows_every_primitive() -> None:
    harness = BotHarness()
    await harness.send_command("kitchen_sink")
    texts = harness.texts()
    assert "Крок 3 з 10" in texts
    assert any("<b>Назар, 18</b>" in t for t in texts)
    assert len(harness.shown()) >= 8


async def test_text_button_press_and_state() -> None:
    harness = BotHarness(routers=[_probe_router()])
    await harness.send_text("ping")
    assert harness.last_text() == "pong"
    assert harness.buttons() == ["Yes", "No"]
    await harness.tap("Yes")
    assert await harness.state() == _Probe.picked.state
    assert (await harness.data())["choice"] == "yes"
    assert harness.alerts() == ["saved"]


async def test_first_update_registers_the_user_through_start() -> None:
    harness = BotHarness(routers=[_probe_router()])
    await harness.send_text("me")
    assert [c.name for c in harness.api.calls][:2] == ["start", "get_me"]
    assert harness.last_text() == "step lang"


async def test_timeout_shows_retry_text_and_keeps_state() -> None:
    harness = BotHarness(routers=[_probe_router()])
    await harness.send_text("ping")
    await harness.tap("No")
    harness.api.timeout_next("get_me")
    await harness.send_text("me")
    assert harness.last_text() == "Щось пішло не так. Спробуй ще раз за хвилину."
    assert await harness.state() == _Probe.picked.state


async def test_throttle_never_drops_sequential_test_input() -> None:
    harness = BotHarness(routers=[_probe_router()])
    for _ in range(10):
        await harness.send_text("ping")
    assert harness.texts().count("pong") == 10


async def test_media_and_location_reach_handlers() -> None:
    harness = BotHarness(routers=[_probe_router()])
    await harness.send_photo()
    await harness.send_voice(12)
    await harness.send_video_note(7)
    await harness.send_location(48.44, 27.80)
    assert harness.texts() == ["photo", "voice", "video_note", "location"]


async def test_language_follows_telegram_until_the_user_picks_one() -> None:
    harness = BotHarness(language_code="en")
    await harness.send_command("kitchen_sink")
    assert "Step 3 of 10" in harness.texts()
