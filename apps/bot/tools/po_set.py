"""Add or update keys in locales/{uk,ru,en}/LC_MESSAGES/messages.po.

Usage: python apps/bot/tools/po_set.py entries.json
entries.json: {"key": {"uk": "...", "ru": "...", "en": "..."}, "plural.key": {"uk": [..3], ...}}
"""

import json
import sys
from io import BytesIO
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

LOCALES = Path(__file__).resolve().parents[1] / "svoi_bot" / "locales"
LANGS = ("uk", "ru", "en")


def _load(lang: str) -> Catalog:
    path = LOCALES / lang / "LC_MESSAGES" / "messages.po"
    if path.exists():
        with path.open("rb") as f:
            return read_po(f, locale=lang)
    return Catalog(locale=lang, project="svoi", fuzzy=False)


def main(entries_path: str) -> None:
    """Merge entries into every language and write sorted catalogs."""
    entries: dict[str, dict[str, str | list[str]]] = json.loads(Path(entries_path).read_text())
    for lang in LANGS:
        catalog = _load(lang)
        for key, texts in entries.items():
            text = texts.get(lang, "")
            if isinstance(text, list):
                catalog.delete(key)
                catalog.add((key, key), tuple(text))
            else:
                catalog.delete(key)
                catalog.add(key, text)
        path = LOCALES / lang / "LC_MESSAGES" / "messages.po"
        path.parent.mkdir(parents=True, exist_ok=True)
        buffer = BytesIO()
        write_po(buffer, catalog, sort_output=True, width=100, no_location=True)
        # one trailing newline, as the end-of-file-fixer hook expects
        path.write_bytes(buffer.getvalue().rstrip(b"\n") + b"\n")


if __name__ == "__main__":
    main(sys.argv[1])
