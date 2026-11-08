"""K5 acceptance: svoi_contracts mirrors docs/tech.md sections 4, 6, 7 and 8 exactly."""

import ast
import importlib
import inspect
import types
import typing
from enum import StrEnum
from typing import Any

import core_spec
import pytest
import svoi_contracts
from pydantic import BaseModel, TypeAdapter
from svoi_contracts import constants, enums, errors, jobs
from svoi_contracts.api import feed, likes

MODEL_MODULES = (
    "svoi_contracts.errors",
    "svoi_contracts.cards",
    "svoi_contracts.jobs",
    *(
        f"svoi_contracts.api.{name}"
        for name in (
            "users",
            "profile",
            "catalog",
            "prefs",
            "feed",
            "reactions",
            "likes",
            "safety",
            "moderation",
            "admin",
            "verification",
            "referral",
        )
    ),
)


def _models() -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for module_name in MODEL_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            is_model = inspect.isclass(obj) and issubclass(obj, BaseModel)
            if is_model and obj.__module__ == module_name:
                assert name not in found, f"{name} defined twice"
                found[name] = obj
    return found


def _fmt(tp: Any) -> str:  # noqa: PLR0911 - one branch per typing form
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is type(None):
        return "None"
    if tp is Any:
        return "Any"
    if origin in (typing.Union, types.UnionType):
        return " | ".join(_fmt(a) for a in args)
    if origin is typing.Literal:
        return f"Literal[{', '.join(repr(a) for a in args)}]"
    if origin is dict and args == (str, Any):
        return "dict"  # tech.md writes untyped JSON objects as bare dict
    if origin is not None:
        return f"{origin.__name__}[{', '.join(_fmt(a) for a in args)}]"
    if isinstance(tp, typing.TypeVar):
        return tp.__name__
    return str(tp.__name__)


def test_core_version_matches_tech_md() -> None:
    assert core_spec.core_version() == svoi_contracts.CORE_VERSION


def test_constants_match_section_4() -> None:
    expected = core_spec.constants()
    actual = {k: v for k, v in vars(constants).items() if k.isupper()}
    assert actual == expected


@pytest.mark.parametrize("name", sorted(core_spec.enums()))
def test_enum_matches_section_6_1(name: str) -> None:
    enum = getattr(enums, name)
    assert issubclass(enum, StrEnum)
    members = core_spec.enums()[name]
    assert [m.name for m in enum] == list(members)
    assert all(m.value == m.name for m in enum)


def test_enums_module_has_no_extra_enums() -> None:
    defined = {
        n for n, o in vars(enums).items() if inspect.isclass(o) and issubclass(o, StrEnum)
    } - {"StrEnum"}
    assert defined == set(core_spec.enums())


def test_error_codes_match_section_6_2() -> None:
    assert [c.name for c in errors.ErrorCode] == list(core_spec.error_codes())
    assert all(c.value == c.name for c in errors.ErrorCode)


def test_every_core_model_exists_once_and_nothing_extra() -> None:
    assert set(_models()) == set(core_spec.classes())


@pytest.mark.parametrize("name", sorted(core_spec.classes()))
def test_model_fields_match_core(name: str) -> None:
    model = _models()[name]
    expected = core_spec.all_fields(name)
    actual = model.model_fields
    assert list(actual) == [f.name for f in expected]
    for spec in expected:
        field = actual[spec.name]
        assert _fmt(field.annotation) == spec.annotation, spec.name
        if spec.default is None:
            assert field.is_required(), spec.name
        elif isinstance(spec.default, ast.Name) and spec.default.id == "CORE_VERSION":
            assert field.default == svoi_contracts.CORE_VERSION
        else:
            assert field.default == ast.literal_eval(spec.default), spec.name


@pytest.mark.parametrize("name", sorted(core_spec.classes()))
def test_models_forbid_extra_are_frozen_and_strict(name: str) -> None:
    config = _models()[name].model_config
    assert config.get("extra") == "forbid"
    assert config.get("frozen") is True
    assert config.get("strict") is True


@pytest.mark.parametrize(
    ("name", "model"),
    [(n, m) for n, m in core_spec.classes().items() if m.topic],
)
def test_job_topics_match_section_8(name: str, model: core_spec.ClassSpec) -> None:
    assert getattr(jobs, name).topic == model.topic


def test_response_unions_discriminate_on_kind() -> None:
    assert set(core_spec.aliases()) == {"FeedResponse", "IncomingResponse"}
    empty = TypeAdapter(feed.FeedResponse).validate_json(
        '{"kind": "empty", "reason": "limit_reached", "expand_options": [], "resets_at": null}'
    )
    assert isinstance(empty, feed.FeedEmpty)
    none = TypeAdapter(likes.IncomingResponse).validate_json('{"kind": "none"}')
    assert isinstance(none, likes.NoIncoming)
