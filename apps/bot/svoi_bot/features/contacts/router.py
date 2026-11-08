"""Contacts router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.contacts import handlers
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import NavCb, PageCb
from svoi_bot.ui.i18n import all_translations


def make_router() -> Router:
    """Menu button, /contacts, pages and actions."""
    router = Router(name="contacts")
    context.attach(router)
    router.message.register(handlers.on_open, Command("contacts"))
    router.message.register(handlers.on_open, F.text.in_(all_translations("ui.menu.contacts")))
    router.callback_query.register(handlers.on_page, PageCb.filter(F.field == handlers.CONTACTS))
    router.callback_query.register(handlers.on_contact, NavCb.filter(F.screen == handlers.CONTACTS))
    return router
