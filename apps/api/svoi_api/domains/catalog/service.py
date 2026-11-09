"""Catalog: cities, goals, categories, interests, custom tags, institutions, prompts (S2-S4)."""

import hashlib

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_GeogFromText
from sqlalchemy import case, func, or_, select
from svoi_contracts.api.catalog import (
    CategoryOut,
    CityOut,
    CustomInterestOut,
    GoalOut,
    InstitutionOut,
    InterestOut,
    PromptOut,
)
from svoi_contracts.constants import CUSTOM_INTEREST_LEN
from svoi_contracts.enums import ContentField, ModerationStatus
from svoi_contracts.errors import ErrorCode

from svoi_api.core.errors import DomainError
from svoi_api.core.i18n import local
from svoi_api.db.models import (
    City,
    Institution,
    Interest,
    InterestCategory,
    Profile,
    Prompt,
    User,
)
from svoi_api.deps import Ctx
from svoi_api.domains.catalog import rules

HIDDEN_CATEGORY = "other"
MIN_QUERY = 2


def city_out(city: City, user: User) -> CityOut:
    """Localized city."""
    return CityOut(
        id=city.id,
        name=local(city, "name", user.lang),
        region=local(city, "region", user.lang),
        country_code=city.country_code,
    )


async def search_cities(ctx: Ctx, user: User, q: str, limit: int) -> list[CityOut]:
    """Trigram search over the three names, tolerant to typos."""
    query = rules.normalize_query(q)
    if len(query) < MIN_QUERY:
        raise DomainError(ErrorCode.validation_error, message="q: at least 2 characters")
    names = (City.name_uk, City.name_ru, City.name_en)
    sim = func.greatest(*(func.similarity(func.lower(n), query) for n in names))
    starts = or_(*(func.lower(n).startswith(query) for n in names))
    rows = await ctx.session.scalars(
        select(City)
        .where(or_(sim >= rules.CITY_SIMILARITY, starts))
        .order_by(case((starts, 0), else_=1), sim.desc(), City.population.desc())
        .limit(limit)
    )
    return [city_out(c, user) for c in rows]


async def city_by_location(ctx: Ctx, user: User, lat: float, lon: float) -> CityOut:
    """Nearest city within 30 km."""
    point = ST_GeogFromText(f"SRID=4326;POINT({lon} {lat})")
    city = await ctx.session.scalar(
        select(City)
        .where(ST_DWithin(City.location, point, rules.NEAREST_CITY_KM * 1000))
        .order_by(ST_Distance(City.location, point))
        .limit(1)
    )
    if city is None:
        raise DomainError(ErrorCode.not_found, message="no city nearby")
    return city_out(city, user)


def goals(user: User) -> list[GoalOut]:
    """All seven goals with emoji."""
    return [
        GoalOut(code=g.code, title=local(g.__dict__, "title", user.lang), emoji=g.emoji)
        for g in rules.GOAL_BY_CODE.values()
    ]


async def categories(ctx: Ctx, user: User) -> list[CategoryOut]:
    """Visible categories by position."""
    rows = await ctx.session.scalars(
        select(InterestCategory)
        .where(InterestCategory.code != HIDDEN_CATEGORY)
        .order_by(InterestCategory.position)
    )
    return [
        CategoryOut(id=c.id, code=c.code, emoji=c.emoji, title=local(c, "title", user.lang))
        for c in rows
    ]


def interest_out(row: Interest, user: User) -> InterestOut:
    """Localized interest."""
    return InterestOut(id=row.id, category_id=row.category_id, title=local(row, "title", user.lang))


async def interests(ctx: Ctx, user: User, category_id: int) -> list[InterestOut]:
    """Approved tags of one category."""
    category = await ctx.session.get(InterestCategory, category_id)
    if category is None or category.code == HIDDEN_CATEGORY:
        raise DomainError(ErrorCode.not_found)
    rows = await ctx.session.scalars(
        select(Interest)
        .where(
            Interest.category_id == category_id,
            Interest.moderation_status == ModerationStatus.approved,
        )
        .order_by(Interest.id)
    )
    return [interest_out(r, user) for r in rows]


async def custom_interest(ctx: Ctx, user: User, title: str) -> CustomInterestOut:
    """Existing similar tag, or a new one under moderation."""
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

    title = " ".join(title.split())
    if not CUSTOM_INTEREST_LEN[0] <= len(title) <= CUSTOM_INTEREST_LEN[1]:
        raise DomainError(ErrorCode.validation_error, message="title length")
    await safety.check_field(ctx, user, title, ContentField.custom_interest)
    column = getattr(Interest, f"title_{user.lang.value}")
    sim = func.similarity(func.lower(column), title.lower())
    match = await ctx.session.scalar(
        select(Interest)
        .where(
            Interest.moderation_status == ModerationStatus.approved,
            sim >= rules.CUSTOM_TAG_SIMILARITY,
        )
        .order_by(sim.desc())
        .limit(1)
    )
    if match is not None:
        return CustomInterestOut(matched=interest_out(match, user), pending=False)
    other = await ctx.session.scalar(
        select(InterestCategory.id).where(InterestCategory.code == HIDDEN_CATEGORY)
    )
    digest = hashlib.sha1(title.lower().encode()).hexdigest()[:12]  # noqa: S324 - not security
    code = f"custom_{user.id}_{digest}"
    exists = await ctx.session.scalar(select(Interest.id).where(Interest.code == code))
    if exists is None:
        ctx.session.add(
            Interest(
                category_id=other,
                code=code,
                title_uk=title,
                title_ru=title,
                title_en=title,
                is_custom=True,
                moderation_status=ModerationStatus.pending,
                created_by_id=user.id,
            )
        )
        await ctx.session.commit()
    return CustomInterestOut(matched=None, pending=True)


async def search_institutions(ctx: Ctx, city_id: int, q: str, limit: int) -> list[InstitutionOut]:
    """Institutions of a city: by popularity without q, by similarity with it."""
    query = select(Institution).where(Institution.city_id == city_id)
    text = rules.normalize_query(q)
    if text:
        sim = func.greatest(
            func.similarity(func.lower(Institution.name), text),
            func.similarity(func.lower(func.coalesce(Institution.short_name, "")), text),
        )
        query = query.where(
            (sim > 0.1)  # noqa: PLR2004 - loose match, the list is short
            | func.lower(Institution.name).contains(text)
            | func.lower(func.coalesce(Institution.short_name, "")).contains(text)
        ).order_by(sim.desc(), Institution.name)
    else:
        members = (
            select(func.count())
            .where(Profile.institution_id == Institution.id)
            .correlate(Institution)
            .scalar_subquery()
        )
        query = query.order_by(members.desc(), Institution.name)
    rows = await ctx.session.scalars(query.limit(limit))
    return [
        InstitutionOut(id=i.id, name=i.name, short_name=i.short_name, type=i.type) for i in rows
    ]


async def prompts(ctx: Ctx, user: User) -> list[PromptOut]:
    """Active prompts."""
    rows = await ctx.session.scalars(select(Prompt).where(Prompt.active).order_by(Prompt.id))
    return [PromptOut(id=p.id, title=local(p, "title", user.lang)) for p in rows]
