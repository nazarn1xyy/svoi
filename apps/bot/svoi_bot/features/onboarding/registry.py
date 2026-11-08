"""STEP_SCREENS: OnboardingStep → screen, shared by onboarding and «Моя анкета» (edit mode).

A slice registers its steps with @register(step). After a successful PUT the handler calls
advance(): onboarding shows the next step from UserState; edit returns to «Моя анкета».
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import User
from svoi_contracts.cards import UserState
from svoi_contracts.enums import OnboardingStep

from svoi_bot.api_client import ApiClient
from svoi_bot.middlewares import remember_state
from svoi_bot.ui.i18n import set_locale
from svoi_bot.ui.screen import Screen

Mode = Literal["onboarding", "edit"]
MODE_KEY = "step_mode"


@dataclass
class StepContext:
    """Everything a step screen needs."""

    bot: Bot
    state: FSMContext
    api: ApiClient
    user_state: UserState
    tg_user: User

    @property
    def screen(self) -> Screen:
        """The step's single message."""
        return Screen(self.bot, self.state)

    async def mode(self) -> Mode:
        """onboarding unless «Моя анкета» opened the step."""
        mode: Mode = (await self.state.get_data()).get(MODE_KEY, "onboarding")
        return mode


StepScreen = Callable[[StepContext], Awaitable[None]]
STEP_SCREENS: dict[OnboardingStep, StepScreen] = {}
# set by features/my_profile (S5): where an edit goes after success
after_edit: list[StepScreen] = []


def register(step: OnboardingStep) -> Callable[[StepScreen], StepScreen]:
    """Register the screen of one step."""

    def wrap(screen: StepScreen) -> StepScreen:
        STEP_SCREENS[step] = screen
        return screen

    return wrap


async def show_step(ctx: StepContext, step: OnboardingStep) -> bool:
    """Show a step's screen; False when no slice provides it yet."""
    screen = STEP_SCREENS.get(step)
    if screen is None:
        return False
    await screen(ctx)
    return True


async def open_edit(ctx: StepContext, step: OnboardingStep) -> bool:
    """Open a step from «Моя анкета»."""
    await ctx.state.update_data({MODE_KEY: "edit"})
    return await show_step(ctx, step)


async def advance(ctx: StepContext, new_state: UserState) -> None:
    """After a successful PUT: cache the state, switch language, go on."""
    await remember_state(ctx.state, new_state)
    set_locale(new_state.lang)
    ctx.user_state = new_state
    if await ctx.mode() == "edit":
        await ctx.state.update_data({MODE_KEY: "onboarding"})
        await ctx.state.set_state(None)
        for hook in after_edit:
            await hook(ctx)
        return
    if not await show_step(ctx, new_state.onboarding_step):
        await ctx.state.set_state(None)
