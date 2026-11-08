"""Core v2 acceptance: one Telegram bot, one environment (docs/adr/0001-single-bot.md)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / "docs/tech.md",
    ROOT / "docs/FRONTEND.md",
    ROOT / "docs/BACKEND.md",
    ROOT / "CLAUDE.md",
)


def _tech() -> str:
    return (ROOT / "docs/tech.md").read_text()


def test_core_header_is_v2() -> None:
    assert re.search(r"^\*\*Версія ядра: v2\*\*", _tech(), re.MULTILINE)


def test_changelog_explains_v2_and_keeps_v1() -> None:
    changelog = _tech().split("## Changelog", 1)[1].split("##", 1)[0]
    assert "- v1 —" in changelog
    assert "- v2 —" in changelog
    assert "0001-single-bot" in changelog


def test_role_guides_reference_core_v2() -> None:
    for name in ("FRONTEND.md", "BACKEND.md"):
        assert "поточна версія **v2**" in (ROOT / "docs" / name).read_text(), name


def test_adr_records_the_decision() -> None:
    adr = (ROOT / "docs/adr/0001-single-bot.md").read_text()
    for section in ("## Статус", "## Контекст", "## Рішення", "## Наслідки"):
        assert section in adr, section


def test_no_second_bot_or_second_environment_remains() -> None:
    banned = (
        "admin-bot",
        "ADMIN_BOT_TOKEN",
        "адмін-бот",
        "svoi_bot.admin.main",
        "тестовий VPS",
        "тестовому VPS",
        "прод VPS",
        "тестовому боті",
    )
    for doc in DOCS:
        text = doc.read_text()
        # the changelog has to name what v2 removed
        if "## Changelog" in text:
            head, rest = text.split("## Changelog", 1)
            text = head + rest.split("\n## ", 1)[1]
        for phrase in banned:
            assert phrase not in text, f"{doc.name}: {phrase}"


def test_admin_section_is_gated_by_is_admin() -> None:
    assert "UserState.is_admin" in _tech()


def test_every_contracts_module_is_listed_in_the_repo_tree() -> None:
    tech = _tech()
    tree = tech[tech.index("### 3.2.") : tech.index("### 3.3.")]
    package = ROOT / "packages/contracts/svoi_contracts"
    for module in sorted(package.rglob("*.py")):
        assert f"── {module.name}" in tree, module.relative_to(ROOT)


def test_skeleton_checklist_tracks_the_current_core_version() -> None:
    assert "`CORE_VERSION = 1`" not in _tech()
