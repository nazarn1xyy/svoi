"""/kitchen_sink shows every primitive at once; svoi_bot.main mounts it only in local and test."""

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from svoi_contracts.cards import Counters, InterestChip, ProfileCard, PromptAnswer
from svoi_contracts.enums import DistanceBucket, Gender, GoalCode, OnboardingStep
from svoi_contracts.errors import ApiError, ErrorCode

from svoi_bot.ui import cards, keyboards, progress
from svoi_bot.ui.errors import render_api_error
from svoi_bot.ui.i18n import _

SAMPLE = ProfileCard(
    user_id=0,
    name="Назар",
    age=18,
    verified=True,
    gender=Gender.male,
    city_name="Могилів-Подільський",
    distance=DistanceBucket.km5,
    goals=[GoalCode.friends, GoalCode.sport],
    interests=[InterestChip(id=1, title="CS2", common=True), InterestChip(id=2, title="Футбол")],
    institution_name="МПМЕФК",
    height_cm=182,
    prompts=[PromptAnswer(prompt_id=1, title="🌅 Ідеальні вихідні — це…", text="катка з друзями")],
    media=[],
    common=None,
    completeness=80,
)


async def kitchen_sink(message: Message, bot: Bot) -> None:
    """Every primitive of tech.md section 9, one message each."""
    chat = message.chat.id
    options = [keyboards.Option(str(i), f"{_('kitchen.option')} {i}") for i in range(1, 15)]
    await bot.send_message(
        chat,
        progress.step_header(OnboardingStep.gender),
        reply_markup=keyboards.inline_choice(options[:3], "ks", back=True, skip=True),
    )
    await bot.send_message(
        chat,
        _("kitchen.multi"),
        reply_markup=keyboards.multi_select(
            options, {"1", "2", "3"}, "ks", min_count=3, max_count=15
        ),
    )
    await bot.send_message(
        chat, _("kitchen.confirm"), reply_markup=keyboards.confirm("✅", "❌", "ks")
    )
    await bot.send_message(
        chat, render_api_error(ApiError(code=ErrorCode.rate_limited, message="demo"))
    )
    await cards.send_card(bot, chat, cards.render_card(SAMPLE, "own"), None)
    await bot.send_message(
        chat, _("kitchen.location"), reply_markup=keyboards.location_request(_("kitchen.option"))
    )
    await bot.send_message(chat, _("kitchen.feed"), reply_markup=keyboards.feed_keyboard())
    await bot.send_message(
        chat, _("kitchen.menu"), reply_markup=keyboards.main_menu(Counters(incoming_likes=3))
    )


def make_router() -> Router:
    """Fresh router mounted by svoi_bot.main in local and test."""
    router = Router(name="kitchen_sink")
    router.message.register(kitchen_sink, Command("kitchen_sink"))
    return router
