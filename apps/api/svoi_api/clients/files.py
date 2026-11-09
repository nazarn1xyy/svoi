"""TelegramFilesClient: bytes of a Telegram file by file_id."""

import hashlib
import io
from typing import Protocol

import httpx
from PIL import Image

from svoi_api.clients._faults import ClientError, ClientTimeout, Faults

TIMEOUT_S = 10.0


class TelegramFilesClient(Protocol):
    """Download a file the user sent to the bot."""

    async def download(self, file_id: str) -> bytes:
        """Raw file bytes."""


class HttpTelegramFiles:
    """Bot API getFile, then the file URL."""

    def __init__(self, bot_token: str) -> None:
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._files = f"https://api.telegram.org/file/bot{bot_token}"

    async def download(self, file_id: str) -> bytes:
        """Two requests: resolve the path, fetch the bytes."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as http:
                meta = await http.get(f"{self._base}/getFile", params={"file_id": file_id})
                meta.raise_for_status()
                path = meta.json()["result"]["file_path"]
                data = await http.get(f"{self._files}/{path}")
                data.raise_for_status()
                return data.content
        except httpx.TimeoutException as exc:
            raise ClientTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ClientError(str(exc)) from exc


def fake_image(file_id: str) -> bytes:
    """A small PNG derived from file_id: the same id gives the same picture and pHash."""
    seed = hashlib.sha256(file_id.encode()).digest()
    img = Image.frombytes("L", (8, 8), (seed * 2)[:64]).resize((64, 64))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


class FakeTelegramFiles(Faults):
    """Serves fake_image(file_id)."""

    async def download(self, file_id: str) -> bytes:
        """Deterministic image bytes."""
        self.hit()
        return fake_image(file_id)
