"""Every text key used in the bot exists in uk; ru and en carry the same keys (CI bot job)."""

import re
from pathlib import Path

from svoi_bot.ui.i18n import catalog
from svoi_contracts.enums import Lang

SRC = Path(__file__).resolve().parents[1] / "svoi_bot"
KEY = re.compile(r"""\b(?:_|lazy_|n_|all_translations)\(\s*["']([a-z0-9_.]+)["']""")


def _used_keys() -> set[str]:
    return {k for path in SRC.rglob("*.py") for k in KEY.findall(path.read_text("utf-8"))}


def test_every_used_key_is_translated_in_uk() -> None:
    missing = _used_keys() - set(catalog(Lang.uk))
    assert not missing


def test_ru_and_en_have_exactly_the_uk_keys() -> None:
    uk = set(catalog(Lang.uk))
    for lang in (Lang.ru, Lang.en):
        assert set(catalog(lang)) == uk, lang
