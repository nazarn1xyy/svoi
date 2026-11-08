"""Goals and interests states."""

from aiogram.fsm.state import State, StatesGroup


class InterestsSG(StatesGroup):
    """Goals, category list, one category, custom tag input."""

    goals = State()
    categories = State()
    category = State()
    custom = State()
