"""Feature routers in dispatch order; each slice exposes make_router() and is listed here."""

from aiogram import Router


def routers() -> list[Router]:
    """Fresh user-facing routers per dispatcher (admin and dev routes are added in main)."""
    return []
