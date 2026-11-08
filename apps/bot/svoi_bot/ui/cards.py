"""Profile card rendering in the format of tech.md section 9."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from typing import Literal

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyKeyboardMarkup,
)
from svoi_contracts.cards import MediaRef, ProfileCard
from svoi_contracts.enums import MediaKind, ModerationStatus

from svoi_bot.ui.format import distance_label, goal_label
from svoi_bot.ui.i18n import _

CardMode = Literal["own", "feed", "incoming", "match", "admin"]
CAPTION_MAX = 1024
Markup = InlineKeyboardMarkup | ReplyKeyboardMarkup | None


@dataclass(frozen=True)
class RenderedCard:
    """Card text (HTML) and the media to send with it."""

    text: str
    media: list[MediaRef] = field(default_factory=list)
    parse_mode: str = "HTML"


def _lower(title: str) -> str:
    # "Футбол" reads "футбол" inside a sentence; acronyms such as CS2 keep their case
    return title[0].lower() + title[1:] if len(title) > 1 and title[1].islower() else title


def _completeness(card: ProfileCard) -> str:
    n = card.completeness or 0
    if not card.media:
        hint = "cards.hint.photo"
    elif not card.prompts:
        hint = "cards.hint.prompt"
    elif not card.institution_name:
        hint = "cards.hint.institution"
    else:
        return _("cards.completeness", n=n)
    return _("cards.completeness_hint", n=n, hint=_(hint))


def render_card(card: ProfileCard, mode: CardMode) -> RenderedCard:
    """Text and media of a card; empty fields are skipped, shared interests come first."""
    head = f"<b>{escape(card.name)}, {card.age}</b>"
    if card.verified:
        head += " ✅"
    head += f" · {escape(card.city_name)}"
    if card.distance is not None:
        head += f" · {distance_label(card.distance)}"
    lines = [head]
    if card.goals:
        lines.append(_("cards.seeks", goals=", ".join(goal_label(g) for g in card.goals)))
    if card.interests:
        chips = sorted(card.interests, key=lambda c: not c.common)
        lines.append(
            "🏷 "
            + " · ".join(
                escape(_lower(c.title)) + (f" ({escape(c.note)})" if c.note else "") for c in chips
            )
        )
    if card.institution_name:
        lines.append(f"🎓 {escape(card.institution_name)}")
    if card.height_cm:
        lines.append(_("cards.height", cm=card.height_cm))
    for prompt in card.prompts:
        lines.append(f"{escape(prompt.title.rstrip('…').rstrip())} {escape(prompt.text)}")
    if mode in ("own", "admin") and any(
        m.moderation_status is ModerationStatus.pending for m in card.media
    ):
        lines.append(_("cards.pending_media"))
    if mode in ("feed", "incoming") and card.common is not None:
        items = [escape(_lower(t)) for t in card.common.interest_titles]
        if card.common.same_institution:
            items.append(_("cards.same_institution"))
        if items:
            lines += [
                "",
                _("cards.common", items=", ".join(items), percent=card.common.match_percent),
            ]
    if mode == "own":
        lines += ["", _completeness(card)]
    media = (
        list(card.media)
        if mode in ("own", "admin")
        else [m for m in card.media if m.moderation_status is ModerationStatus.approved]
    )
    return RenderedCard(text="\n".join(lines), media=media)


def caption(rendered: RenderedCard) -> str:
    """Text cut to Telegram's caption limit by whole lines, so HTML stays valid."""
    lines = rendered.text.split("\n")
    while len(lines) > 1 and len("\n".join(lines)) > CAPTION_MAX:
        lines.pop()
    text = "\n".join(lines).rstrip()
    return text if len(text) <= CAPTION_MAX else text[: CAPTION_MAX - 1] + "…"


async def send_card(
    bot: Bot, chat_id: int, rendered: RenderedCard, markup: Markup
) -> list[Message]:
    """One media: caption under it. Several: album, then the text with the buttons."""
    media = rendered.media
    if not media:
        return [
            await bot.send_message(
                chat_id, rendered.text, parse_mode=rendered.parse_mode, reply_markup=markup
            )
        ]
    if len(media) == 1:
        send = bot.send_video if media[0].kind is MediaKind.video else bot.send_photo
        return [
            await send(
                chat_id,
                media[0].file_id,
                caption=caption(rendered),
                parse_mode=rendered.parse_mode,
                reply_markup=markup,
            )
        ]
    album: Sequence[InputMediaPhoto | InputMediaVideo] = [
        InputMediaVideo(media=m.file_id)
        if m.kind is MediaKind.video
        else InputMediaPhoto(media=m.file_id)
        for m in media
    ]
    sent = list(await bot.send_media_group(chat_id, list(album)))
    sent.append(
        await bot.send_message(
            chat_id, rendered.text, parse_mode=rendered.parse_mode, reply_markup=markup
        )
    )
    return sent
