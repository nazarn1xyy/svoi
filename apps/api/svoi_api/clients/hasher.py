"""ImageHasher: perceptual hash for duplicate photos (local, not an external service)."""

import io
from typing import Protocol

import imagehash
from PIL import Image


class ImageHasher(Protocol):
    """pHash as a hex string."""

    def phash(self, image: bytes) -> str:
        """64-bit perceptual hash."""


class PHasher:
    """imagehash.phash."""

    def phash(self, image: bytes) -> str:
        """Hex pHash of the decoded image."""
        with Image.open(io.BytesIO(image)) as img:
            return str(imagehash.phash(img))


def distance(a: str, b: str) -> int:
    """Hamming distance between two hex hashes."""
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))
