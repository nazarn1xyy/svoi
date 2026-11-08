"""Gettext catalogs (locales/<lang>/LC_MESSAGES/messages.po) keyed `section.screen.element`.

Untranslated ru/en strings fall back to uk, never to the raw key.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from babel.messages.pofile import read_po
from svoi_contracts.enums import Lang

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
DOMAIN = "messages"
_locale: ContextVar[Lang] = ContextVar("locale", default=Lang.uk)
Entry = str | tuple[str, ...]


@cache
def catalog(lang: Lang) -> dict[str, Entry]:
    """Translated entries of one language; plural keys map to a tuple of forms."""
    path = LOCALES_DIR / lang.value / "LC_MESSAGES" / f"{DOMAIN}.po"
    with path.open("rb") as f:
        po = read_po(f, locale=lang.value)
    entries: dict[str, Entry] = {}
    for message in po:
        if not message.id:
            continue
        key = str(message.id[0] if isinstance(message.id, (tuple, list)) else message.id)
        value = message.string
        if isinstance(value, tuple) and all(value):
            entries[key] = tuple(value)
        elif isinstance(value, str) and value:
            entries[key] = value
    return entries


def set_locale(lang: Lang) -> None:
    """Language for `_` in the current context (one update)."""
    _locale.set(lang)


def get_locale() -> Lang:
    """Language of the current context."""
    return _locale.get()


def _entry(key: str, lang: Lang) -> Entry:
    found = catalog(lang).get(key) or catalog(Lang.uk).get(key)
    if found is None:
        raise KeyError(f"missing translation key {key!r}")
    return found


def _(key: str, **params: object) -> str:
    """Translate `key` into the current language and fill `{params}`."""
    entry = _entry(key, get_locale())
    text = entry if isinstance(entry, str) else entry[0]
    return text.format(**params) if params else text


def _plural_index(lang: Lang, n: int) -> int:
    if lang is Lang.en:
        return 0 if n == 1 else 1
    if n % 10 == 1 and n % 100 != 11:  # noqa: PLR2004 - Slavic plural rule
        return 0
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:  # noqa: PLR2004 - Slavic plural rule
        return 1
    return 2


def n_(key: str, n: int, **params: object) -> str:
    """Plural form of `key` for `n` (1 людині / 2 людям / 5 людям)."""
    lang = get_locale()
    entry = _entry(key, lang)
    forms = (entry,) if isinstance(entry, str) else entry
    index = min(_plural_index(lang, n), len(forms) - 1)
    return forms[index].format(**params)


@dataclass(frozen=True)
class LazyText:
    """Translated on str(), for texts defined at import time."""

    key: str

    def __str__(self) -> str:
        return _(self.key)


def lazy_(key: str) -> LazyText:
    """Defer translation until the text is shown."""
    return LazyText(key)


def all_translations(key: str) -> frozenset[str]:
    """Every language's text of `key`, for reply-button filters."""
    return frozenset(
        e if isinstance(e, str) else e[0] for e in (_entry(key, lang) for lang in Lang)
    )
