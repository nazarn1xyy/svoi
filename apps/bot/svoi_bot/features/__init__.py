"""Feature routers in dispatch order; each slice exposes make_router() and is listed here."""

from aiogram import Router

from svoi_bot.features.about import router as about
from svoi_bot.features.captcha import router as captcha
from svoi_bot.features.city import router as city
from svoi_bot.features.contacts import router as contacts
from svoi_bot.features.feed import router as feed
from svoi_bot.features.interests import router as interests
from svoi_bot.features.likes import router as likes
from svoi_bot.features.my_profile import router as my_profile
from svoi_bot.features.onboarding import router as onboarding
from svoi_bot.features.referral import router as referral
from svoi_bot.features.report import router as report
from svoi_bot.features.settings import router as settings
from svoi_bot.features.start import router as start
from svoi_bot.features.verification import router as verification


def routers() -> list[Router]:
    """Fresh user-facing routers per dispatcher (admin and dev routes are added in main)."""
    return [
        # first: suspicious accounts solve the captcha before anything else (S11)
        captcha.make_router(),
        start.make_router(),
        onboarding.make_router(),
        city.make_router(),
        interests.make_router(),
        about.make_router(),
        verification.make_router(),
        my_profile.make_router(),
        settings.make_router(),
        feed.make_router(),
        likes.make_router(),
        contacts.make_router(),
        report.make_router(),
        referral.make_router(),
        # keep last: catches anything else from users who have not finished onboarding
        onboarding.make_resume_router(),
    ]
