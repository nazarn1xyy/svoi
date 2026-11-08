"""Feed states."""

from aiogram.fsm.state import State, StatesGroup


class FeedSG(StatesGroup):
    """Looking at cards, or writing a message for a like."""

    viewing = State()
    message = State()
