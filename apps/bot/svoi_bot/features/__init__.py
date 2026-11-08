"""Feature routers in dispatch order; each slice exposes make_router() and is listed here."""

from aiogram import Router

from svoi_bot.features.city import router as city
from svoi_bot.features.onboarding import router as onboarding
from svoi_bot.features.start import router as start


def routers() -> list[Router]:
    """Fresh user-facing routers per dispatcher (admin and dev routes are added in main)."""
    return [
        start.make_router(),
        onboarding.make_router(),
        city.make_router(),
        # keep last: catches anything else from users who have not finished onboarding
        onboarding.make_resume_router(),
    ]
