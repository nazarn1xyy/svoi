"""Admin texts and keyboards (FRONTEND.md S10, S10b)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from svoi_contracts.api.admin import AdminQueueItem, AdminUserOut, MetricsOut
from svoi_contracts.enums import AdminAction, AdminQueueKind, Pool, UserStatus

from svoi_bot.ui import keyboards
from svoi_bot.ui.callbacks import AdminCb
from svoi_bot.ui.format import gesture_label, reason_label
from svoi_bot.ui.i18n import _

ACTIONS: dict[AdminQueueKind, list[AdminAction]] = {
    AdminQueueKind.reports: [
        AdminAction.ok,
        AdminAction.delete_media,
        AdminAction.delete_text,
        AdminAction.ban_7d,
        AdminAction.ban_forever,
        AdminAction.move_to_minor_pool,
    ],
    AdminQueueKind.photos: [AdminAction.approve, AdminAction.reject],
    AdminQueueKind.verifications: [AdminAction.approve, AdminAction.reject],
    AdminQueueKind.custom_tags: [AdminAction.approve, AdminAction.reject],
    AdminQueueKind.texts: [AdminAction.ok, AdminAction.delete_text, AdminAction.ban_7d],
}
NEEDS_CONFIRM = {
    AdminAction.ban_7d,
    AdminAction.ban_forever,
    AdminAction.delete_media,
    AdminAction.delete_text,
}


def _btn(text: str, action: str, kind: str, item_id: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, callback_data=AdminCb(action=action, kind=kind, item_id=item_id).pack()
    )


def home(stats: dict[AdminQueueKind, int]) -> tuple[str, InlineKeyboardMarkup]:
    """Queue counters."""
    rows = [
        [_btn(_(f"admin.queue.{k.value}", n=stats.get(k, 0)), "queue", k.value)]
        for k in AdminQueueKind
    ]
    return _("admin.home.title"), keyboards.markup(rows)


def item_text(item: AdminQueueItem) -> str:
    """Reports list or the flagged content."""
    lines = []
    for report in item.reports:
        line = f"{reason_label(report.reason)} · {report.created_at:%d.%m.%Y}"
        lines.append(line + (f" · {report.text}" if report.text else ""))
    if item.kind is AdminQueueKind.verifications and item.verification_gesture is not None:
        lines.append(_("admin.gesture", gesture=gesture_label(item.verification_gesture)))
    if item.custom_interest_title:
        lines.append(f"«{item.custom_interest_title}»")
    if item.flagged_text:
        lines.append(item.flagged_text)
    return "\n".join(lines)


def item_buttons(item: AdminQueueItem) -> InlineKeyboardMarkup:
    """Actions of this queue kind."""
    rows = [
        [_btn(_(f"admin.action.{a.value}"), a.value, item.kind.value, item.item_id)]
        for a in ACTIONS[item.kind]
    ]
    rows.append([_btn(_("ui.button.back"), "home", item.kind.value)])
    return keyboards.markup(rows)


def confirm(action: AdminAction, item: AdminCb) -> tuple[str, InlineKeyboardMarkup]:
    """Bans and deletions ask twice."""
    rows = [
        [
            _btn(_("admin.confirm.yes"), f"y_{action.value}", item.kind, item.item_id),
            _btn(_("admin.confirm.no"), "queue", item.kind),
        ]
    ]
    return _("admin.confirm.ask", action=_(f"admin.action.{action.value}")), keyboards.markup(rows)


def empty() -> str:
    """No items left."""
    return _("admin.empty")


def user(out: AdminUserOut) -> str:
    """/user <tg_id>."""
    until = f"{out.banned_until:%d.%m.%Y}" if out.banned_until else "—"
    return _(
        "admin.user",
        user_id=out.user_id,
        tg_id=out.tg_id,
        status=out.status.value,
        shadow=_("settings.on") if out.shadow_banned else _("settings.off"),
        until=until,
        risk=out.risk_score,
        reports=out.reports_total,
    )


def metrics(m: MetricsOut) -> str:
    """S10b: /metrics [days]; rates are already 0 when the API divides by zero."""
    status, pool = m.users_by_status, m.users_by_pool
    return _(
        "admin.metrics",
        start=f"{m.period_from:%d.%m}",
        end=f"{m.period_to:%d.%m}",
        users_total=m.users_total,
        active=status.get(UserStatus.active, 0),
        onboarding=status.get(UserStatus.onboarding, 0),
        hidden=status.get(UserStatus.hidden, 0),
        banned=status.get(UserStatus.banned, 0),
        adult=pool.get(Pool.adult, 0),
        minor=pool.get(Pool.minor, 0),
        verified=m.verified_total,
        shadow=m.shadow_banned_total,
        bot_blocked=m.bot_blocked_total,
        today=m.active_today,
        week=m.active_7d,
        month=m.active_30d,
        starts=m.starts,
        completed=m.onboarding_completed,
        rate=round(m.onboarding_rate * 100),
        d1=round(m.d1_retention * 100),
        d7=round(m.d7_retention * 100),
        views=m.views_total,
        likes=m.likes_total,
        likes_msg=m.likes_with_message,
        skips=m.skips_total,
        matches=m.matches_total,
        mutual=round(m.mutual_rate * 100),
        reports=m.reports_total,
        per1000=f"{m.reports_per_1000_views:.1f}",
        confirmed=round(m.confirmed_reports_rate * 100),
        likes_all=m.likes_all_time,
        matches_all=m.matches_all_time,
        pending=m.likes_pending,
    )
