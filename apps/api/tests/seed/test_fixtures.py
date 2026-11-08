"""K7 acceptance: fixtures for FakeApiClient are deterministic and serve contract models."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from svoi_api.seed.fixtures import FILES, FIXTURES_DIR, export
from svoi_contracts.api.catalog import (
    CategoryOut,
    CityOut,
    GoalOut,
    InstitutionOut,
    InterestOut,
    PromptOut,
)
from svoi_contracts.api.profile import ClarificationOut, OptionOut
from svoi_contracts.enums import Lang


def _digest(directory: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob("*.json")}


def _load(directory: Path, name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((directory / name).read_text())
    return data


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("fixtures")
    export(directory)
    return directory


def test_export_is_byte_for_byte_deterministic(exported: Path, tmp_path: Path) -> None:
    export(tmp_path)
    assert _digest(tmp_path) == _digest(exported)


def test_export_writes_exactly_the_declared_files(exported: Path) -> None:
    assert {p.name for p in exported.glob("*.json")} == set(FILES)


def test_committed_fixtures_are_up_to_date(exported: Path) -> None:
    # regenerate with: uv run python -m svoi_api.seed --fixtures-only
    assert _digest(FIXTURES_DIR) == _digest(exported)


@pytest.mark.parametrize("lang", list(Lang))
def test_fixtures_localize_into_contract_models(exported: Path, lang: Lang) -> None:
    def t(row: dict[str, Any], field: str) -> str:
        value: str = row[f"{field}_{lang}"]
        return value

    for row in _load(exported, "cities.json"):
        CityOut(
            id=row["id"],
            name=t(row, "name"),
            region=t(row, "region"),
            country_code=row["country_code"],
        )
    for row in _load(exported, "goals.json"):
        GoalOut(code=row["code"], title=t(row, "title"), emoji=row["emoji"])
    for row in _load(exported, "interest_categories.json"):
        CategoryOut(id=row["id"], code=row["code"], emoji=row["emoji"], title=t(row, "title"))
    for row in _load(exported, "interests.json"):
        InterestOut(id=row["id"], category_id=row["category_id"], title=t(row, "title"))
    for row in _load(exported, "prompts.json"):
        PromptOut(id=row["id"], title=t(row, "title"))
    for row in _load(exported, "institutions.json"):
        InstitutionOut(
            id=row["id"], name=row["name"], short_name=row["short_name"], type=row["type"]
        )
    interests = {row["id"]: row for row in _load(exported, "interests.json")}
    for row in _load(exported, "clarifications.json"):
        ClarificationOut(
            interest_id=row["interest_id"],
            interest_title=t(interests[row["interest_id"]], "title"),
            question_key=row["question_key"],
            options=[OptionOut(key=o["key"], title=t(o, "title")) for o in row["options"]],
        )


def test_cross_references_resolve(exported: Path) -> None:
    cities = {r["id"] for r in _load(exported, "cities.json")}
    categories = {r["id"] for r in _load(exported, "interest_categories.json")}
    interests = {r["id"] for r in _load(exported, "interests.json")}
    prompts = {r["id"] for r in _load(exported, "prompts.json")}
    institutions = {r["id"]: r["city_id"] for r in _load(exported, "institutions.json")}
    assert {r["category_id"] for r in _load(exported, "interests.json")} <= categories
    assert {r["interest_id"] for r in _load(exported, "clarifications.json")} <= interests
    assert set(institutions.values()) <= cities
    for user in _load(exported, "profiles.json"):
        assert user["profile"]["city_id"] in cities
        assert {i["interest_id"] for i in user["interests"]} <= interests
        assert {p["prompt_id"] for p in user["prompts"]} <= prompts
        if user["profile"]["institution_id"] is not None:
            assert institutions[user["profile"]["institution_id"]] == user["profile"]["city_id"]


def test_hidden_other_category_is_flagged_for_the_fake(exported: Path) -> None:
    other = [r for r in _load(exported, "interest_categories.json") if r["code"] == "other"]
    assert len(other) == 1
    assert other[0]["hidden"] is True
