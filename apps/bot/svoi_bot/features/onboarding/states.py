"""FSM states of onboarding steps that wait for typed input or a button."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingSG(StatesGroup):
    """One state per step; slices S2-S4 add theirs."""

    lang = State()
    consent = State()
    age = State()
    name = State()
    gender = State()
