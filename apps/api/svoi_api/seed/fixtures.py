"""Exports seed data to packages/contracts/fixtures for FakeApiClient (K10).

Rows keep every language (title_uk/_ru/_en); the fake localizes them like the API does.
"""

import json
from pathlib import Path
from typing import Any

from svoi_api.seed import catalog
from svoi_api.seed.profiles import DemoUser, generate

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "fixtures"
FILES = (
    "cities.json",
    "interest_categories.json",
    "interests.json",
    "goals.json",
    "prompts.json",
    "clarifications.json",
    "institutions.json",
    "profiles.json",
)


def _titles(row: Any, prefix: str = "title") -> dict[str, str]:
    return {f"{prefix}_{lang}": getattr(row, f"{prefix}_{lang}") for lang in ("uk", "ru", "en")}


def _cities() -> list[dict[str, Any]]:
    return [
        {
            "id": c.geonames_id,  # cities.id equals geonames_id so re-imports keep references
            "geonames_id": c.geonames_id,
            **_titles(c, "name"),
            **_titles(c, "region"),
            "country_code": c.country_code,
            "lat": c.lat,
            "lon": c.lon,
            "population": c.population,
        }
        for c in catalog.load_cities()
    ]


def _profile(user: DemoUser) -> dict[str, Any]:
    return {
        "user": {
            "id": user.id,
            "tg_id": user.tg_id,
            "tg_username": user.tg_username,
            "tg_first_name": user.tg_first_name,
            "lang": user.lang,
            "status": user.status,
            "onboarding_step": user.onboarding_step,
            "referral_code": user.referral_code,
        },
        "profile": {
            "name": user.name,
            "age": user.age,
            "gender": user.gender,
            "pool": user.pool,
            "city_id": user.city_geonames_id,
            "institution_id": user.institution_id,
            "height_cm": user.height_cm,
        },
        "goals": list(user.goals),
        "interests": [
            {"interest_id": i.interest_id, "note_key": i.note_key} for i in user.interests
        ],
        "prompts": [{"prompt_id": p.prompt_id, "text": p.text} for p in user.prompts],
    }


def build() -> dict[str, list[dict[str, Any]]]:
    """Fixture name to rows, in FILES order."""
    category_ids = {c.code: c.id for c in catalog.CATEGORIES}
    interest_ids = {i.code: i.id for i in catalog.INTERESTS}
    return {
        "cities.json": _cities(),
        "interest_categories.json": [
            {
                "id": c.id,
                "code": c.code,
                "emoji": c.emoji,
                **_titles(c),
                "position": c.position,
                "hidden": c.hidden,
            }
            for c in catalog.CATEGORIES
        ],
        "interests.json": [
            {"id": i.id, "category_id": category_ids[i.category_code], "code": i.code, **_titles(i)}
            for i in catalog.INTERESTS
        ],
        "goals.json": [{"code": g.code, "emoji": g.emoji, **_titles(g)} for g in catalog.GOALS],
        "prompts.json": [{"id": p.id, "code": p.code, **_titles(p)} for p in catalog.PROMPTS],
        "clarifications.json": [
            {
                "id": c.id,
                "interest_id": interest_ids[c.interest_code],
                "question_key": c.question_key,
                "priority": c.priority,
                "options": [{"key": o.key, **_titles(o)} for o in c.options],
            }
            for c in catalog.CLARIFICATIONS
        ],
        "institutions.json": [
            {
                "id": i.id,
                "city_id": i.city_geonames_id,
                "name": i.name,
                "short_name": i.short_name,
                "type": i.type,
                "source_id": i.source_id,
            }
            for i in catalog.INSTITUTIONS
        ],
        "profiles.json": [_profile(u) for u in generate()],
    }


def export(directory: Path = FIXTURES_DIR) -> None:
    """Write every fixture file; output is byte-for-byte stable."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in build().items():
        text = json.dumps(rows, ensure_ascii=False, indent=2)
        (directory / name).write_text(text + "\n", encoding="utf-8")
