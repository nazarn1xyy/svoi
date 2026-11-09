"""Pick the localized column of a catalog row (title_uk / title_ru / title_en)."""

from typing import Any

from svoi_contracts.enums import Lang


def local(row: Any, prefix: str, lang: Lang) -> str:
    """row.<prefix>_<lang>, for ORM rows and dicts alike."""
    key = f"{prefix}_{lang.value}"
    value = row[key] if isinstance(row, dict) else getattr(row, key)
    return str(value)
