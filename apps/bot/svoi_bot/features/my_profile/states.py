"""«Моя анкета» states."""

from aiogram.fsm.state import State, StatesGroup


class MyProfileSG(StatesGroup):
    """Profile screen, photo manager and confirmations."""

    view = State()
    photos = State()
    confirm_delete = State()
    confirm_reset = State()
