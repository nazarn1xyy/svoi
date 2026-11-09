"""NsfwClassifier: probability that an image is NSFW."""

from typing import Protocol

import httpx

from svoi_api.clients._faults import ClientError, ClientTimeout, Faults

TIMEOUT_S = 10.0


class NsfwClassifier(Protocol):
    """Score in [0, 1]."""

    async def score(self, image: bytes) -> float:
        """NSFW probability."""


class HttpNsfw:
    """The self-hosted model container: POST image bytes, get {"score": float}."""

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    async def score(self, image: bytes) -> float:
        """One POST per image."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as http:
                response = await http.post(f"{self._url}/score", content=image)
                response.raise_for_status()
                return float(response.json()["score"])
        except httpx.TimeoutException as exc:
            raise ClientTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ClientError(str(exc)) from exc


class FakeNsfw(Faults):
    """Score per image bytes set by tests (key: files.fake_image(file_id)), else 0.1."""

    def __init__(self) -> None:
        super().__init__()
        self.scores: dict[bytes, float] = {}

    async def score(self, image: bytes) -> float:
        """Deterministic: tests map image bytes to a score."""
        self.hit()
        return self.scores.get(image, 0.1)
