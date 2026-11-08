"""K10 acceptance: ApiClient has exactly one operation per endpoint of tech.md section 7.2."""

import re
from pathlib import Path

from svoi_bot.api_client.base import OPS, ApiClient

TECH = (Path(__file__).resolve().parents[4] / "docs/tech.md").read_text()


def _core_endpoints() -> set[tuple[str, str]]:
    rows = re.findall(r"^\| (GET|POST|PUT|DELETE) \| `([^`]+)` \|", TECH, re.MULTILINE)
    return {(method, re.sub(r"\{[^}]+\}", "{}", path)) for method, path in rows}


def test_every_core_endpoint_has_exactly_one_op() -> None:
    ops = [(op.method, re.sub(r"\{[^}]+\}", "{}", op.path)) for op in OPS.values()]
    assert len(ops) == len(set(ops))
    assert set(ops) == _core_endpoints()


def test_every_op_is_a_client_method() -> None:
    for name in OPS:
        assert callable(getattr(ApiClient, name)), name


def test_names_from_tech_md_and_frontend_md_exist() -> None:
    # tech.md 9 names start, get_me, set_lang, consent, set_age, admin_action;
    # FRONTEND.md tests use set_name and feed_next with fail_next/timeout_next
    for name in (
        "start",
        "get_me",
        "set_lang",
        "consent",
        "set_age",
        "set_name",
        "feed_next",
        "admin_action",
    ):
        assert name in OPS
