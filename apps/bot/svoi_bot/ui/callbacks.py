"""Callback data factories; short prefixes keep packed data under Telegram's 64 bytes."""

from aiogram.filters.callback_data import CallbackData


class NavCb(CallbackData, prefix="nv"):
    """Navigation: back, skip, noop or a named screen."""

    screen: str
    arg: str = ""


class PickCb(CallbackData, prefix="pk"):
    """Single choice."""

    field: str
    value: str


class ToggleCb(CallbackData, prefix="tg"):
    """Multi-select toggle."""

    field: str
    value: str


class PageCb(CallbackData, prefix="pg"):
    """List pagination."""

    field: str
    page: int


class DoneCb(CallbackData, prefix="dn"):
    """Multi-select confirmation."""

    field: str


class ReactCb(CallbackData, prefix="rc"):
    """Inline action on a feed card (undo)."""

    action: str
    target_id: int


class LikeCb(CallbackData, prefix="lk"):
    """Answer to an incoming like."""

    action: str
    like_id: int


class ReportCb(CallbackData, prefix="rp"):
    """Report flow; reason is empty until chosen."""

    target_id: int
    reason: str
    context: str


class AdminCb(CallbackData, prefix="ad"):
    """Moderator action on a queue item."""

    action: str
    kind: str
    item_id: int
