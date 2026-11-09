"""K9 acceptance: UI primitives of tech.md section 9 behave as specified."""

from datetime import UTC, datetime

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from hypothesis import given
from hypothesis import strategies as st
from svoi_bot.ui import callbacks, cards, errors, format, i18n, keyboards, progress
from svoi_bot.ui.screen import Screen
from svoi_contracts.cards import (
    CommonBlock,
    Counters,
    InterestChip,
    MediaRef,
    ProfileCard,
    PromptAnswer,
)
from svoi_contracts.enums import (
    ContentBlockReason,
    DistanceBucket,
    Gender,
    GestureCode,
    GoalCode,
    Lang,
    MediaKind,
    ModerationStatus,
    OnboardingStep,
    ReportReason,
)
from svoi_contracts.errors import ApiError, ErrorCode

CARD = ProfileCard(
    user_id=1,
    name="Назар",
    age=18,
    verified=True,
    gender=Gender.male,
    city_name="Могилів-Подільський",
    distance=DistanceBucket.km5,
    goals=[GoalCode.friends, GoalCode.sport],
    interests=[
        InterestChip(id=1, title="CS2", common=True),
        InterestChip(id=2, title="Футбол", note="граю", common=True),
        InterestChip(id=3, title="Гітара", note="граю"),
        InterestChip(id=4, title="Аніме"),
    ],
    institution_name="МПМЕФК",
    height_cm=182,
    prompts=[
        PromptAnswer(
            prompt_id=1,
            title="🌅 Ідеальні вихідні — це…",
            text="катка з друзями і вечір біля річки",
        )
    ],
    media=[],
    common=CommonBlock(interest_titles=["CS2", "Футбол"], same_institution=True, match_percent=78),
    completeness=None,
)


@pytest.fixture(autouse=True)
def _uk() -> None:
    i18n.set_locale(Lang.uk)


def _texts(markup: InlineKeyboardMarkup | ReplyKeyboardMarkup) -> list[list[str]]:
    rows = markup.inline_keyboard if isinstance(markup, InlineKeyboardMarkup) else markup.keyboard
    return [[b.text for b in row] for row in rows]


def test_card_renders_the_tech_md_example() -> None:
    text = cards.render_card(CARD, "feed").text
    assert text.splitlines() == [
        "<b>Назар, 18</b> ✅",
        "📍 Могилів-Подільський · до 5 км",
        "🎓 МПМЕФК · 📏 182 см",
        "",
        "🎯 <b>Шукає:</b> друзів, напарника для спорту",
        "🏷 <b>CS2</b> · <b>футбол <i>(граю)</i></b> · гітара <i>(граю)</i> · аніме",
        "",
        "<i>🌅 Ідеальні вихідні — це…</i>",
        "<blockquote>катка з друзями і вечір біля річки</blockquote>",
        "",
        "✨ <b>Спільне:</b> CS2, футбол, один заклад",
        "📊 Збіг 78%",
    ]


def test_common_block_only_in_feed_and_incoming() -> None:
    for mode in ("own", "match", "admin"):
        assert "Спільне:" not in cards.render_card(CARD, mode).text
    assert "Спільне:" in cards.render_card(CARD, "incoming").text


def test_empty_fields_are_skipped_and_text_is_escaped() -> None:
    bare = CARD.model_copy(
        update={
            "name": "<b>x</b>",
            "verified": False,
            "distance": None,
            "goals": [],
            "interests": [],
            "institution_name": None,
            "height_cm": None,
            "prompts": [],
            "common": None,
        }
    )
    assert (
        cards.render_card(bare, "feed").text
        == "<b>&lt;b&gt;x&lt;/b&gt;, 18</b>\n📍 Могилів-Подільський"
    )


def test_own_card_shows_completeness_hint_and_pending_marker() -> None:
    own = CARD.model_copy(
        update={
            "completeness": 70,
            "common": None,
            "prompts": [],
            "institution_name": None,
            "media": [
                MediaRef(
                    id=1,
                    kind=MediaKind.photo,
                    file_id="f",
                    moderation_status=ModerationStatus.pending,
                )
            ],
        }
    )
    text = cards.render_card(own, "own").text
    assert "Анкета заповнена на 70% — дай відповідь на питання" in text
    assert "🕓 Фото на перевірці" in text


@given(
    st.text(min_size=1, max_size=400),
    st.integers(min_value=16, max_value=99),
    st.lists(st.text(min_size=1, max_size=30), max_size=15),
)
def test_caption_fits_telegram_limit_and_keeps_name_and_age(
    prompt: str, age: int, titles: list[str]
) -> None:
    card = CARD.model_copy(
        update={
            "age": age,
            "interests": [InterestChip(id=i, title=t) for i, t in enumerate(titles)],
            "prompts": [PromptAnswer(prompt_id=1, title="🌅 Ідеальні вихідні — це…", text=prompt)]
            * 2,
            "completeness": 50,
        }
    )
    caption = cards.caption(cards.render_card(card, "own"))
    assert len(caption) <= cards.CAPTION_MAX
    assert f"Назар, {age}" in caption


def test_step_header_numbers_ten_steps() -> None:
    assert progress.step_header(OnboardingStep.age) == "Крок 1 з 10"
    assert progress.step_header(OnboardingStep.media) == "Крок 10 з 10"
    assert progress.step_header(OnboardingStep.clarify) == ""
    assert progress.step_header(OnboardingStep.preview) == ""


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_error_code_has_a_text(code: ErrorCode) -> None:
    details = {"field": "name", "reason": "link"} if code is ErrorCode.content_blocked else None
    text = errors.render_api_error(ApiError(code=code, message="m", details=details))
    assert text and "." not in text.split()[0]  # a sentence, not a raw key


@pytest.mark.parametrize("reason", list(ContentBlockReason))
def test_every_content_block_reason_has_its_own_text(reason: ContentBlockReason) -> None:
    err = ApiError(
        code=ErrorCode.content_blocked,
        message="m",
        details={"field": "prompt", "reason": reason.value},
    )
    texts = {errors.render_api_error(err)}
    assert texts and texts != {
        errors.render_api_error(ApiError(code=ErrorCode.internal, message="m"))
    }


def test_ban_texts() -> None:
    forever = ApiError(code=ErrorCode.banned, message="m", details={"until": None})
    assert errors.render_api_error(forever) == "Твою анкету заблоковано назавжди."
    until = ApiError(
        code=ErrorCode.banned,
        message="m",
        details={"until": datetime(2026, 12, 1, tzinfo=UTC).isoformat()},
    )
    assert errors.render_api_error(until) == "Твою анкету заблоковано до 01.12.2026."


def test_labels_cover_their_enums() -> None:
    for code in GoalCode:
        assert format.goal_label(code)
    for bucket in DistanceBucket:
        assert format.distance_label(bucket)
    for gesture in GestureCode:
        assert format.gesture_label(gesture)
    for reason in ReportReason:
        assert format.reason_label(reason)


def test_language_switch_and_uk_fallback() -> None:
    i18n.set_locale(Lang.en)
    assert progress.step_header(OnboardingStep.age) == "Step 1 of 10"
    i18n.set_locale(Lang.ru)
    assert progress.step_header(OnboardingStep.name) == "Шаг 2 из 10"


@pytest.mark.parametrize(
    ("n", "expected"),
    [(1, "1 людині"), (2, "2 людям"), (5, "5 людям"), (11, "11 людям"), (21, "21 людині")],
)
def test_ukrainian_plurals(n: int, expected: str) -> None:
    assert i18n.n_("ui.people", n, count=n) == expected


def test_inline_choice_layout_with_back_and_skip() -> None:
    options = [keyboards.Option(str(i), f"o{i}") for i in range(3)]
    markup = keyboards.inline_choice(options, "gender", columns=2, back=True, skip=True)
    assert _texts(markup) == [["o0", "o1"], ["o2"], ["⏭ Пропустити"], ["◀️ Назад"]]
    first = markup.inline_keyboard[0][0].callback_data
    assert first == callbacks.PickCb(field="gender", value="0").pack()


def test_multi_select_marks_selection_pages_and_locks_done() -> None:
    options = [keyboards.Option(str(i), f"t{i}") for i in range(14)]
    markup = keyboards.multi_select(options, {"0", "13"}, "interests", min_count=3, max_count=15)
    rows = _texts(markup)
    assert rows[0] == ["✅ t0", "t1"]
    assert ["▶️"] in rows  # 14 options, 12 per page
    done = markup.inline_keyboard[-1][0]
    assert done.text == "Готово ▶️ (2)"
    assert done.callback_data != callbacks.DoneCb(field="interests").pack()  # locked under min
    page2 = keyboards.multi_select(
        options, {"0", "1", "13"}, "interests", min_count=3, max_count=15, page=1
    )
    assert _texts(page2)[0] == ["t12", "✅ t13"]
    assert page2.inline_keyboard[-1][0].callback_data == callbacks.DoneCb(field="interests").pack()


def test_main_menu_shows_like_counter_only_when_positive() -> None:
    assert _texts(keyboards.main_menu(Counters(incoming_likes=3)))[0] == [
        "🔍 Дивитися анкети",
        "❤️ Мене лайкнули (3)",
    ]
    assert _texts(keyboards.main_menu(Counters(incoming_likes=0)))[0][1] == "❤️ Мене лайкнули"


def test_feed_location_confirm_and_remove() -> None:
    assert _texts(keyboards.feed_keyboard()) == [["❤️", "💌", "👎", "💤"]]
    location = keyboards.location_request("✍️ Напишу назву")
    assert location.keyboard[0][0].request_location is True
    assert _texts(keyboards.confirm("Так", "Ні", "delete")) == [["Так", "Ні"]]
    assert keyboards.remove().remove_keyboard is True


@given(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=16),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=32),
    st.integers(min_value=0, max_value=2**53),
)
def test_callbacks_fit_64_bytes(field: str, value: str, number: int) -> None:
    packed = [
        callbacks.NavCb(screen=field, arg=value).pack(),
        callbacks.PickCb(field=field, value=value).pack(),
        callbacks.ToggleCb(field=field, value=value).pack(),
        callbacks.PageCb(field=field, page=number % 1000).pack(),
        callbacks.DoneCb(field=field).pack(),
        callbacks.ReactCb(action=field, target_id=number).pack(),
        callbacks.LikeCb(action=field, like_id=number).pack(),
        callbacks.ReportCb(target_id=number, reason=field, context=field).pack(),
        callbacks.AdminCb(action=field, kind=field, item_id=number).pack(),
    ]
    assert all(len(p.encode()) <= 64 for p in packed)


class _Bot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def send_message(self, **kwargs: object) -> object:
        self.calls.append(("send_message", kwargs))
        return type("M", (), {"message_id": len(self.calls)})()

    async def edit_message_text(self, **kwargs: object) -> object:
        self.calls.append(("edit_message_text", kwargs))
        return True

    async def edit_message_reply_markup(self, **kwargs: object) -> object:
        self.calls.append(("edit_message_reply_markup", kwargs))
        return True


async def test_screen_edits_one_message_per_step() -> None:
    bot = _Bot()
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=5, user_id=5))
    screen = Screen(bot, state)  # type: ignore[arg-type]  # duck-typed bot for the unit test
    await screen.show("a", keyboards.confirm("y", "n", "f"))
    await screen.replace("b", keyboards.confirm("y", "n", "f"))
    await screen.clear()
    await screen.replace("c", None)
    assert [c[0] for c in bot.calls] == [
        "send_message",
        "edit_message_text",
        "edit_message_reply_markup",
        "send_message",
    ]
    assert bot.calls[1][1]["message_id"] == 1
    assert bot.calls[0][1]["chat_id"] == 5
