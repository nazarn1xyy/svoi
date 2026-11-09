"""External clients behind interfaces; fakes for local, test and CI (docs/tech.md section 10)."""

from dataclasses import dataclass

from svoi_api.clients.files import FakeTelegramFiles, HttpTelegramFiles, TelegramFilesClient
from svoi_api.clients.hasher import ImageHasher, PHasher
from svoi_api.clients.nsfw import FakeNsfw, HttpNsfw, ManualReview, NsfwClassifier
from svoi_api.config import Settings


@dataclass
class Clients:
    """One instance of each external client per process."""

    files: TelegramFilesClient
    nsfw: NsfwClassifier
    hasher: ImageHasher


def make_clients(settings: Settings) -> Clients:
    """Fakes when USE_FAKE_CLIENTS=true, real HTTP clients otherwise."""
    if settings.use_fake_clients:
        return Clients(FakeTelegramFiles(), FakeNsfw(), PHasher())
    nsfw: NsfwClassifier = HttpNsfw(settings.nsfw_url) if settings.nsfw_url else ManualReview()
    return Clients(HttpTelegramFiles(settings.bot_token), nsfw, PHasher())


__all__ = [
    "Clients",
    "FakeNsfw",
    "FakeTelegramFiles",
    "ImageHasher",
    "NsfwClassifier",
    "TelegramFilesClient",
    "make_clients",
]
