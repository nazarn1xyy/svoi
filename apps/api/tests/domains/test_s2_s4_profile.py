"""S2-S4 acceptance: city, interests, custom tags, clarifications, media, photo moderation."""

import pytest
from apihelp import UserFactory, assert_error, city_id, interest_ids, onboard, start
from arq import Retry
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from svoi_api.clients import Clients, FakeNsfw, FakeTelegramFiles
from svoi_api.clients.files import fake_image
from svoi_api.core.queue import RecordingQueue
from svoi_api.db.models import Media, NotificationOutbox, Profile, ProfileInterest
from svoi_api.deps import Ctx
from svoi_api.domains.moderation.jobs import moderate_photo
from svoi_contracts.api.catalog import CityOut, CustomInterestOut, InstitutionOut
from svoi_contracts.api.profile import ClarificationOut
from svoi_contracts.cards import MediaRef
from svoi_contracts.jobs import ModeratePhoto


@pytest.mark.parametrize("q", ["Могилів", "могилев", "Mohyliv"])
async def test_city_search_tolerates_typos(user: UserFactory, q: str) -> None:
    tg = user(1)
    await start(tg)
    found = await tg.ok("GET", "/catalog/cities/search", list[CityOut], params={"q": q})
    assert any("Могилів-Подільський" in c.name for c in found), found


async def test_city_search_needs_two_letters(user: UserFactory) -> None:
    tg = user(1)
    await start(tg)
    r = await tg.call("GET", "/catalog/cities/search", params={"q": "в"})
    assert_error(r, 422, "validation_error")


async def test_city_by_location(user: UserFactory) -> None:
    tg = user(1)
    await start(tg)
    near = await tg.ok(
        "GET", "/catalog/cities/by-location", CityOut, params={"lat": 49.23, "lon": 28.47}
    )
    assert near.name == "Вінниця"
    far = await tg.call("GET", "/catalog/cities/by-location", params={"lat": 0.0, "lon": 0.0})
    assert_error(far, 404, "not_found")


async def test_geo_is_rounded_and_cleared(user: UserFactory, ctx: Ctx) -> None:
    tg = user(1)
    state = await onboard(tg)
    vinnytsia = await city_id(tg, "Вінниця")
    await tg.ok(
        "PUT", "/profile/city", body={"city_id": vinnytsia, "lat": 49.23456, "lon": 28.46789}
    )
    lat = await ctx.session.scalar(
        select(func.ST_Y(cast(Profile.geo, Geometry))).where(Profile.user_id == state.user_id)
    )
    assert lat == pytest.approx(49.23)
    await tg.ok("PUT", "/profile/city", body={"city_id": vinnytsia})
    ctx.session.expire_all()
    p = await ctx.session.get(Profile, state.user_id)
    assert p is not None and p.geo is None


async def test_far_coordinates_rejected(user: UserFactory) -> None:
    tg = user(1)
    await onboard(tg)
    vinnytsia = await city_id(tg, "Вінниця")
    r = await tg.call(
        "PUT", "/profile/city", body={"city_id": vinnytsia, "lat": 50.45, "lon": 30.52}
    )
    assert_error(r, 422, "validation_error")


@pytest.mark.parametrize("n", [2, 16])
async def test_interest_count_bounds(user: UserFactory, n: int) -> None:
    tg = user(1)
    await onboard(tg, complete=False)
    ids = await interest_ids(tg, n)
    assert_error(
        await tg.call("PUT", "/profile/interests", body={"interest_ids": ids}),
        422,
        "validation_error",
    )


async def test_notes_survive_interest_resave(user: UserFactory, ctx: Ctx) -> None:
    tg = user(1)
    state = await onboard(tg, complete=False)
    guitar = 25  # the seed has a clarification for it
    ids = [guitar, *await interest_ids(tg, 3)]
    await tg.ok("PUT", "/profile/interests", body={"interest_ids": ids})
    await tg.ok("PUT", f"/profile/interests/{guitar}/note", body={"option_key": "plays"})
    open_q = await tg.ok("GET", "/profile/clarifications", list[ClarificationOut])
    assert all(c.interest_id != guitar for c in open_q)
    await tg.ok("PUT", "/profile/interests", body={"interest_ids": list(reversed(ids))})
    note = await ctx.session.scalar(
        select(ProfileInterest.note_key).where(
            ProfileInterest.user_id == state.user_id, ProfileInterest.interest_id == guitar
        )
    )
    assert note == "plays"
    bad = await tg.call("PUT", f"/profile/interests/{guitar}/note", body={"option_key": "nope"})
    assert_error(bad, 422, "validation_error")


async def test_custom_tag_matches_or_waits(user: UserFactory) -> None:
    tg = user(1)
    await onboard(tg)
    found = await tg.ok(
        "POST", "/catalog/interests/custom", CustomInterestOut, body={"title": "шахи"}
    )
    assert found.matched is not None and not found.pending
    new = await tg.ok(
        "POST", "/catalog/interests/custom", CustomInterestOut, body={"title": "лонгборд у парку"}
    )
    assert new.matched is None and new.pending
    blocked = await tg.call("POST", "/catalog/interests/custom", body={"title": "t.me/spam"})
    assert_error(blocked, 400, "content_blocked")


async def test_institutions_of_city(user: UserFactory) -> None:
    tg = user(1)
    await start(tg)
    mp = await city_id(tg, "Могилів-Подільський")
    found = await tg.ok(
        "GET", "/catalog/institutions/search", list[InstitutionOut], params={"city_id": mp}
    )
    assert found


async def test_fourth_media_is_limited(user: UserFactory, queue: RecordingQueue) -> None:
    tg = user(1)
    await onboard(tg)
    refs = [
        await tg.ok(
            "POST",
            "/profile/media",
            MediaRef,
            body={"kind": "photo", "file_id": f"f{i}", "file_unique_id": f"u{i}"},
        )
        for i in range(3)
    ]
    assert all(r.moderation_status.value == "pending" for r in refs)
    assert len(queue.of(ModeratePhoto)) == 3
    r = await tg.call(
        "POST", "/profile/media", body={"kind": "photo", "file_id": "f4", "file_unique_id": "u4"}
    )
    assert_error(r, 400, "media_limit")
    order = await tg.ok(
        "PUT",
        "/profile/media/order",
        list[MediaRef],
        body={"ids": [refs[2].id, refs[0].id, refs[1].id]},
    )
    assert [m.id for m in order] == [refs[2].id, refs[0].id, refs[1].id]
    await tg.ok("DELETE", f"/profile/media/{refs[0].id}")


async def _photo(user: UserFactory, file_id: str) -> int:
    tg = user(1)
    await onboard(tg)
    ref = await tg.ok(
        "POST",
        "/profile/media",
        MediaRef,
        body={"kind": "photo", "file_id": file_id, "file_unique_id": file_id},
    )
    return int(ref.id)


@pytest.mark.parametrize(
    ("score", "status"), [(0.9, "rejected"), (0.6, "pending"), (0.2, "approved")]
)
async def test_photo_moderation_thresholds(
    user: UserFactory, ctx: Ctx, clients: Clients, score: float, status: str
) -> None:
    media_id = await _photo(user, "photo-x")
    assert isinstance(clients.nsfw, FakeNsfw)
    clients.nsfw.scores[fake_image("photo-x")] = score
    await moderate_photo(ctx, ModeratePhoto(dedupe_key=f"photo:{media_id}", media_id=media_id))
    media = await ctx.session.get(Media, media_id)
    assert media is not None and media.moderation_status.value == status


async def test_photo_moderation_is_idempotent(
    user: UserFactory, ctx: Ctx, clients: Clients
) -> None:
    media_id = await _photo(user, "photo-y")
    assert isinstance(clients.nsfw, FakeNsfw)
    clients.nsfw.scores[fake_image("photo-y")] = 0.95
    job = ModeratePhoto(dedupe_key=f"photo:{media_id}", media_id=media_id)
    await moderate_photo(ctx, job)
    await moderate_photo(ctx, job)
    assert clients.nsfw.calls == 1
    outbox = list(await ctx.session.scalars(select(NotificationOutbox)))
    assert len(outbox) == 1


async def test_photo_download_error_retries(user: UserFactory, ctx: Ctx, clients: Clients) -> None:
    media_id = await _photo(user, "photo-z")
    assert isinstance(clients.files, FakeTelegramFiles)
    clients.files.fail_next()
    with pytest.raises(Retry):
        await moderate_photo(ctx, ModeratePhoto(dedupe_key=f"photo:{media_id}", media_id=media_id))
    clients.files.timeout_next()
    with pytest.raises(Retry):
        await moderate_photo(ctx, ModeratePhoto(dedupe_key=f"photo:{media_id}", media_id=media_id))
    media = await ctx.session.get(Media, media_id)
    assert media is not None and media.moderation_status.value == "pending"
