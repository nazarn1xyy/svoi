"""States of the optional onboarding steps."""

from aiogram.fsm.state import State, StatesGroup


class AboutSG(StatesGroup):
    """One state per optional step, plus the preview."""

    clarify = State()
    institution = State()
    height = State()
    prompt_pick = State()
    prompt_text = State()
    prompt_more = State()
    media = State()
    preview = State()
