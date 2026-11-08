"""K7 acceptance: catalog sizes, translations and limits from FRONTEND.md and tech.md."""

from collections import Counter

from svoi_api.seed import catalog
from svoi_contracts.enums import GoalCode, InstitutionType

SEED_CITIES = {700918: "Могилів-Подільський", 689558: "Вінниця", 703448: "Київ"}


def _filled(*titles: str) -> bool:
    return all(t.strip() for t in titles)


def test_twelve_visible_categories_and_hidden_other() -> None:
    visible = [c for c in catalog.CATEGORIES if not c.hidden]
    hidden = [c for c in catalog.CATEGORIES if c.hidden]
    assert len(visible) == 12
    assert [c.code for c in hidden] == ["other"]
    assert len({c.id for c in catalog.CATEGORIES}) == len(catalog.CATEGORIES)
    assert len({c.position for c in visible}) == 12
    for c in catalog.CATEGORIES:
        assert _filled(c.title_uk, c.title_ru, c.title_en, c.emoji)
        assert max(len(c.title_uk), len(c.title_ru), len(c.title_en)) <= 40  # DB String(40)


def test_about_120_interests_spread_over_visible_categories() -> None:
    assert 110 <= len(catalog.INTERESTS) <= 130
    per_category = Counter(i.category_code for i in catalog.INTERESTS)
    visible = {c.code for c in catalog.CATEGORIES if not c.hidden}
    assert set(per_category) == visible  # "other" only receives custom tags
    assert min(per_category.values()) >= 6
    assert len({i.id for i in catalog.INTERESTS}) == len(catalog.INTERESTS)
    assert len({i.code for i in catalog.INTERESTS}) == len(catalog.INTERESTS)
    for i in catalog.INTERESTS:
        assert _filled(i.title_uk, i.title_ru, i.title_en)
        assert max(len(i.title_uk), len(i.title_ru), len(i.title_en)) <= 30  # DB String(30)


def test_titles_are_unique_per_language() -> None:
    for lang in ("uk", "ru", "en"):
        titles = [getattr(i, f"title_{lang}").casefold() for i in catalog.INTERESTS]
        assert len(set(titles)) == len(titles), lang


def test_goals_cover_every_goal_code_in_frontend_order() -> None:
    assert [g.code for g in catalog.GOALS] == list(GoalCode)
    assert catalog.GOALS[0].emoji == "👫"
    assert catalog.GOALS[0].title_uk == "Знайти друзів"
    for g in catalog.GOALS:
        assert _filled(g.title_uk, g.title_ru, g.title_en, g.emoji)


def test_four_prompts_from_frontend_s4() -> None:
    assert [p.title_uk for p in catalog.PROMPTS] == [
        "🌅 Ідеальні вихідні — це…",
        "🔍 Шукаю людину, яка…",
        "🎓 Можу навчити / хочу навчитися…",
        "🎧 Зараз слухаю…",
    ]
    for p in catalog.PROMPTS:
        assert _filled(p.title_ru, p.title_en, p.code)
        assert max(len(p.title_uk), len(p.title_ru), len(p.title_en)) <= 80


def test_at_least_ten_clarifications_with_unique_keys() -> None:
    clarifications = catalog.CLARIFICATIONS
    assert len(clarifications) >= 10
    assert len({c.question_key for c in clarifications}) == len(clarifications)
    interest_codes = {i.code for i in catalog.INTERESTS}
    assert len({c.interest_code for c in clarifications}) == len(clarifications)  # unique in DB
    for c in clarifications:
        assert c.interest_code in interest_codes
        assert len(c.question_key) <= 48
        assert 2 <= len(c.options) <= 4
        keys = [o.key for o in c.options]
        assert len(set(keys)) == len(keys)
        for o in c.options:
            assert len(o.key) <= 32  # profile_interests.note_key String(32)
            assert _filled(o.title_uk, o.title_ru, o.title_en)


def test_each_seed_city_has_institutions() -> None:
    # S4 shows up to 8 institutions as buttons; a town may have fewer
    per_city = Counter(i.city_geonames_id for i in catalog.INSTITUTIONS)
    assert set(per_city) == set(SEED_CITIES)
    assert min(per_city.values()) >= 3
    assert per_city[703448] >= 8
    for inst in catalog.INSTITUTIONS:
        assert inst.type in InstitutionType
        assert len(inst.name) <= 200
        assert inst.short_name is None or len(inst.short_name) <= 40
    assert len({i.id for i in catalog.INSTITUTIONS}) == len(catalog.INSTITUTIONS)


def test_seed_cities_are_in_the_city_catalog() -> None:
    cities = {c.geonames_id: c for c in catalog.load_cities()}
    assert len(cities) > 700
    for geonames_id, name in SEED_CITIES.items():
        assert cities[geonames_id].name_uk == name
    assert cities[700918].region_uk == "Вінницька область"
