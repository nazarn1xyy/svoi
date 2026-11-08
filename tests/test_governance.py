"""K4 acceptance: CODEOWNERS and main protection follow FRONTEND.md section 6."""

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEAD = "@nazarn1xyy"
BACKEND = "@Aryliadoch"
LEAD_PATHS = (
    "/docs/",
    "/CLAUDE.md",
    "/packages/contracts/",
    "/apps/api/svoi_api/db/",
    "/apps/api/migrations/",
    "/apps/api/svoi_api/seed/",
    "/apps/api/svoi_api/core/",
    "/apps/api/svoi_api/clients/",
    "/apps/api/svoi_api/config.py",
    "/apps/bot/svoi_bot/ui/",
    "/apps/bot/svoi_bot/api_client/",
    "/apps/bot/svoi_bot/middlewares/",
    "/infra/",
    "/.github/",
)
BACKEND_PATHS = ("/apps/api/svoi_api/domains/", "/apps/bot/svoi_bot/features/")


def _owners() -> list[tuple[str, list[str]]]:
    rules = []
    for line in (ROOT / ".github/CODEOWNERS").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            path, *owners = line.split()
            rules.append((path, owners))
    return rules


def _json(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / ".github/settings" / name).read_text())
    return data


def test_codeowners_matches_section_6_in_order() -> None:
    # GitHub applies the last matching rule, so order is part of the contract
    expected = [("*", [LEAD, BACKEND])]
    expected += [(path, [LEAD]) for path in LEAD_PATHS]
    expected += [(path, [BACKEND]) for path in BACKEND_PATHS]
    assert _owners() == expected


def test_main_needs_one_code_owner_approval() -> None:
    reviews = _json("branch-protection.json")["required_pull_request_reviews"]
    assert reviews["required_approving_review_count"] == 1
    assert reviews["require_code_owner_reviews"] is True
    assert reviews["dismiss_stale_reviews"] is True


def test_required_checks_are_exactly_the_pr_gate_jobs() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/pr.yml").read_text())
    checks = _json("branch-protection.json")["required_status_checks"]
    assert sorted(checks["contexts"]) == sorted(workflow["jobs"])
    assert checks["strict"] is True


def test_main_is_linear_and_cannot_be_force_pushed_or_deleted() -> None:
    protection = _json("branch-protection.json")
    assert protection["required_linear_history"] is True
    assert protection["allow_force_pushes"] is False
    assert protection["allow_deletions"] is False


def test_admins_cannot_bypass_pull_requests() -> None:
    # "only through PR" holds for the repo owner too
    assert _json("branch-protection.json")["enforce_admins"] is True


def test_repo_allows_squash_merge_only() -> None:
    repo = _json("repo.json")
    assert repo["allow_squash_merge"] is True
    assert repo["allow_merge_commit"] is False
    assert repo["allow_rebase_merge"] is False
    # deleting merged heads lets GitHub retarget stacked PRs onto main
    assert repo["delete_branch_on_merge"] is True


def test_apply_script_targets_main_protection_and_repo_settings() -> None:
    script = (ROOT / "infra/github-settings.sh").read_text()
    assert "branches/main/protection" in script
    assert ".github/settings/branch-protection.json" in script
    assert ".github/settings/repo.json" in script
