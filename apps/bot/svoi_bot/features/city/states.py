"""City step states."""

from aiogram.fsm.state import State, StatesGroup


class CitySG(StatesGroup):
    """Typing a city or confirming one."""

    input = State()
    confirm = State()
