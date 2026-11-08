"""S4 router: optional steps and the preview."""

from aiogram import F, Router

from svoi_bot.features.about import handlers, views
from svoi_bot.features.about.states import AboutSG
from svoi_bot.features.onboarding import context, preview
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.keyboards import SKIP


def make_router() -> Router:
    """Handlers by state."""
    router = Router(name="about")
    context.attach(router)
    cq, msg = router.callback_query, router.message
    cq.register(handlers.on_clarify, AboutSG.clarify, PickCb.filter(F.field == views.CLARIFY))
    cq.register(
        handlers.on_institution, AboutSG.institution, PickCb.filter(F.field == views.INSTITUTION)
    )
    msg.register(handlers.on_institution_search, AboutSG.institution, F.text)
    msg.register(handlers.on_height, AboutSG.height, F.text)
    cq.register(
        handlers.on_prompt_pick, AboutSG.prompt_pick, PickCb.filter(F.field == views.PROMPT)
    )
    msg.register(handlers.on_prompt_text, AboutSG.prompt_text, F.text)
    cq.register(handlers.on_prompt_more, AboutSG.prompt_more, PickCb.filter(F.field == views.MORE))
    cq.register(handlers.on_media_done, AboutSG.media, PickCb.filter(F.field == views.MEDIA))
    msg.register(handlers.on_media, AboutSG.media)
    cq.register(handlers.nav_skip, NavCb.filter(F.arg == SKIP))
    cq.register(preview.on_preview, AboutSG.preview, PickCb.filter(F.field == views.PREVIEW))
    return router
