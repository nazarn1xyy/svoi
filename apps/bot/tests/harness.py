"""BotHarness: the real Dispatcher on FakeApiClient, with a Bot session that records requests.

Methods follow tech.md section 11: send_text, send_command, press, send_location, send_photo,
send_voice, send_video_note, last_message, sent, state.
"""

import itertools
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, cast

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    EditMessageCaption,
    EditMessageText,
    SendMediaGroup,
    SendMessage,
    SendPhoto,
    SendVideo,
    SendVideoNote,
    SendVoice,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ErrorEvent,
    InlineKeyboardMarkup,
    Location,
    Message,
    PhotoSize,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    User,
    UserProfilePhotos,
    VideoNote,
    Voice,
)
from svoi_bot.api_client import FakeApiClient
from svoi_bot.config import Settings
from svoi_bot.main import build_dispatcher

BOT_ID = 42  # the id aiogram reads from the "42:TEST" token
BOT_USER = User(id=BOT_ID, is_bot=True, first_name="Svoi", username="svoi_test_bot")
_SENDS = (SendMessage, SendPhoto, SendVideo, SendVoice, SendVideoNote)
_SHOWN = (*_SENDS, EditMessageText, EditMessageCaption)


class _Clock:
    """Virtual time: each update moves it 0.5 s so the throttle never drops test input."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def tick(self, seconds: float = 0.5) -> None:
        self.now += seconds


class RecordingSession(BaseSession):
    """Answers every Bot API call locally and keeps the requests."""

    def __init__(self, chat: Chat, profile_photos: int = 0) -> None:
        super().__init__()
        self.chat = chat
        self.profile_photos = profile_photos
        self.requests: list[TelegramMethod[Any]] = []
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        """Nothing to close."""

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109 - signature of aiogram BaseSession
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        """No downloads in tests."""
        if False:  # pragma: no cover - an async generator that yields nothing
            yield b""

    def _message(self, method: TelegramMethod[Any]) -> Message:
        fields = method.model_dump()
        return Message(
            message_id=next(self._ids),
            date=datetime.now(UTC),
            chat=self.chat,
            from_user=BOT_USER,
            text=fields.get("text"),
            caption=fields.get("caption"),
            reply_markup=fields.get("reply_markup")
            if isinstance(fields.get("reply_markup"), dict)
            and "inline_keyboard" in fields["reply_markup"]
            else None,
        )

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,  # noqa: ASYNC109 - signature of aiogram BaseSession
    ) -> TelegramType:
        """Record the call and return a plausible result of the right type."""
        self.requests.append(method)
        returning = method.__returning__
        result: Any
        if returning is Message:
            result = self._message(method)
        elif returning == list[Message]:
            result = [self._message(method)]
        elif returning is UserProfilePhotos:
            photo = [PhotoSize(file_id="p", file_unique_id="p", width=1, height=1)]
            result = UserProfilePhotos(
                total_count=self.profile_photos, photos=[photo] * self.profile_photos
            )
        elif returning is User:
            result = BOT_USER
        elif isinstance(method, EditMessageText):
            result = self._message(method)
        else:
            result = True
        return cast(TelegramType, result)


class BotHarness:
    """One private chat with the bot."""

    def __init__(  # noqa: PLR0913 - keyword options of one chat
        self,
        api: FakeApiClient | None = None,
        *,
        user_id: int = 100,
        first_name: str = "Ira",
        username: str | None = "ira",
        language_code: str = "uk",
        profile_photos: int = 1,
        routers: list[Router] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.api = api or FakeApiClient()
        self.user = User(
            id=user_id,
            is_bot=False,
            first_name=first_name,
            username=username,
            language_code=language_code,
        )
        self.chat = Chat(id=user_id, type="private", first_name=first_name)
        self.session = RecordingSession(self.chat, profile_photos)
        self.bot = Bot(
            "42:TEST", session=self.session, default=DefaultBotProperties(parse_mode="HTML")
        )
        self.storage = MemoryStorage()
        self.clock = _Clock()
        self.settings = settings or Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings kwarg
        self.dp: Dispatcher = build_dispatcher(
            self.api, self.storage, self.settings, extra_routers=routers, clock=self.clock
        )
        self.errors: list[BaseException] = []
        catcher = Router(name="harness_errors")
        catcher.errors.register(self._record_error)
        self.dp.include_router(catcher)
        self._update_ids = itertools.count(1)
        self._message_ids = itertools.count(1)

    # ---- input -------------------------------------------------------------------------

    def _incoming(self, **fields: Any) -> Message:
        return Message(
            message_id=next(self._message_ids),
            date=datetime.now(UTC),
            chat=self.chat,
            from_user=self.user,
            **fields,
        )

    async def _record_error(self, event: ErrorEvent) -> bool:
        self.errors.append(event.exception)
        return True

    async def _feed(self, **update: Any) -> None:
        self.clock.tick()
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), **update))
        if self.errors:
            # a handler crashed and aiogram would only log it; fail the test instead
            raise self.errors.pop()

    async def send_text(self, text: str) -> None:
        """User types a message."""
        await self._feed(message=self._incoming(text=text))

    async def send_command(self, command: str, args: str = "") -> None:
        """User sends /command [args]."""
        text = f"/{command.lstrip('/')}" + (f" {args}" if args else "")
        await self._feed(message=self._incoming(text=text))

    async def press(self, data: str | CallbackData) -> None:
        """User taps an inline button with this callback data (on the last bot message)."""
        packed = data.pack() if isinstance(data, CallbackData) else data
        shown = self.last_message_object()
        message = Message(
            message_id=shown.message_id if shown else 1,
            date=datetime.now(UTC),
            chat=self.chat,
            from_user=BOT_USER,
            text="",
        )
        query = CallbackQuery(
            id=str(next(self._update_ids)),
            from_user=self.user,
            chat_instance="ci",
            message=message,
            data=packed,
        )
        await self._feed(callback_query=query)

    async def send_location(self, latitude: float, longitude: float) -> None:
        """User shares a location."""
        await self._feed(
            message=self._incoming(location=Location(latitude=latitude, longitude=longitude))
        )

    async def send_photo(self, file_id: str = "photo1", media_group_id: str | None = None) -> None:
        """User sends a photo (album items share media_group_id)."""
        photo = [PhotoSize(file_id=file_id, file_unique_id=f"u_{file_id}", width=640, height=640)]
        await self._feed(message=self._incoming(photo=photo, media_group_id=media_group_id))

    async def send_voice(self, duration: int = 5, file_id: str = "voice1") -> None:
        """User records a voice message."""
        await self._feed(
            message=self._incoming(
                voice=Voice(file_id=file_id, file_unique_id=f"u_{file_id}", duration=duration)
            )
        )

    async def send_video_note(self, duration: int = 5, file_id: str = "note1") -> None:
        """User records a round video."""
        await self._feed(
            message=self._incoming(
                video_note=VideoNote(
                    file_id=file_id, file_unique_id=f"u_{file_id}", length=240, duration=duration
                )
            )
        )

    # ---- output ------------------------------------------------------------------------

    def sent(self) -> list[TelegramMethod[Any]]:
        """Every Bot API call so far."""
        return list(self.session.requests)

    def clear(self) -> None:
        """Forget recorded calls (keeps chat state)."""
        self.session.requests.clear()

    def shown(self) -> list[TelegramMethod[Any]]:
        """Calls that show text to the user: sends and edits."""
        return [m for m in self.session.requests if isinstance(m, _SHOWN)]

    def last_message(self) -> TelegramMethod[Any]:
        """The latest send or edit."""
        shown = self.shown()
        if not shown:
            raise AssertionError("the bot has not shown anything")
        return shown[-1]

    def last_text(self) -> str:
        """Text or caption of the latest send or edit."""
        method = self.last_message()
        fields = method.model_dump()
        return str(fields.get("text") or fields.get("caption") or "")

    def texts(self) -> list[str]:
        """Texts and captions of every send and edit, in order."""
        out = []
        for m in self.shown():
            fields = m.model_dump()
            out.append(str(fields.get("text") or fields.get("caption") or ""))
        return out

    def last_markup(
        self,
    ) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None:
        """Keyboard of the latest send or edit (None when it has none)."""
        shown = self.shown()
        if not shown:
            return None
        markup = getattr(shown[-1], "reply_markup", None)
        return cast(InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None, markup)

    def buttons(self) -> list[str]:
        """Button labels of the latest keyboard, row by row flattened."""
        markup = self.last_markup()
        if isinstance(markup, InlineKeyboardMarkup):
            return [b.text for row in markup.inline_keyboard for b in row]
        if isinstance(markup, ReplyKeyboardMarkup):
            return [b.text for row in markup.keyboard for b in row]
        return []

    def callback(self, label: str) -> str:
        """Callback data of the inline button with this label on the latest keyboard."""
        for method in reversed(self.shown()):
            markup = getattr(method, "reply_markup", None)
            if isinstance(markup, InlineKeyboardMarkup):
                for row in markup.inline_keyboard:
                    for button in row:
                        if button.text == label and button.callback_data:
                            return button.callback_data
        raise AssertionError(f"no inline button {label!r}; have {self.buttons()}")

    async def tap(self, label: str) -> None:
        """Press the inline button with this label."""
        await self.press(self.callback(label))

    def alerts(self) -> list[str]:
        """Texts of callback answers shown as alerts or toasts."""
        return [
            str(m.model_dump().get("text"))
            for m in self.session.requests
            if type(m).__name__ == "AnswerCallbackQuery" and m.model_dump().get("text")
        ]

    def last_message_object(self) -> Message | None:
        """A Message standing for the latest bot output (for pressing its buttons)."""
        return (
            Message(message_id=1, date=datetime.now(UTC), chat=self.chat) if self.shown() else None
        )

    def media_groups(self) -> list[SendMediaGroup]:
        """Albums sent."""
        return [m for m in self.session.requests if isinstance(m, SendMediaGroup)]

    async def state(self) -> str | None:
        """Current FSM state name."""
        return await self._context().get_state()

    async def data(self) -> dict[str, Any]:
        """Current FSM data."""
        return await self._context().get_data()

    def _context(self) -> FSMContext:
        return FSMContext(
            self.storage, StorageKey(bot_id=BOT_ID, chat_id=self.chat.id, user_id=self.user.id)
        )
