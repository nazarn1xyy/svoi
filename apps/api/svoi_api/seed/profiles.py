"""Deterministic demo profiles: 40 adult and 10 minor in the three seed cities (K7)."""

import random
from dataclasses import dataclass

from svoi_contracts.constants import ADULT_AGE, GOALS_COUNT, HEIGHT_CM, INTERESTS_COUNT
from svoi_contracts.enums import Gender, GoalCode, Lang, OnboardingStep, Pool, UserStatus

from svoi_api.seed.catalog import CLARIFICATIONS, INSTITUTIONS, INTERESTS, PROMPTS

SEED = 20261108
ADULTS, MINORS = 40, 10
# Mohyliv-Podilskyi first: the launch town gets the most profiles
CITIES = (700918, 689558, 703448)
FIRST_USER_ID = 900_000_001  # far above real ids so local signups never collide
FIRST_TG_ID = 9_000_000_001  # not a real Telegram account range used by the bot in tests
# shares of demo profiles that fill optional steps
P_INSTITUTION, P_HEIGHT, P_NOTE = 0.7, 0.5, 0.6

_MALE = ("Назар", "Максим", "Артем", "Олександр", "Дмитро", "Іван", "Богдан", "Денис", "Марк")
_FEMALE = ("Софія", "Анна", "Марія", "Вікторія", "Дарина", "Олена", "Ірина", "Юлія", "Катерина")
_PROMPT_TEXTS: dict[int, tuple[str, ...]] = {
    1: (
        "катка з друзями і вечір біля річки",
        "велопрогулянка за місто і кава в термосі",
        "виспатися, а потім настолки до ночі",
    ),
    2: (
        "піде на концерт без довгих роздумів",
        "любить гори так само, як я",
        "не боїться дурних мемів о третій ночі",
    ),
    3: (
        "можу навчити грати на гітарі, хочу навчитися малювати",
        "можу підтягнути з математики, хочу вивчити англійську",
    ),
    4: ("Kalush, Jerry Heil і трохи лоу-фаю", "Океан Ельзи на повторі", "подкасти про космос"),
}


@dataclass(frozen=True)
class ChosenInterest:
    interest_id: int
    note_key: str | None


@dataclass(frozen=True)
class PromptText:
    prompt_id: int
    text: str


@dataclass(frozen=True)
class DemoUser:
    id: int
    tg_id: int
    tg_username: str | None
    tg_first_name: str
    lang: Lang
    status: UserStatus
    onboarding_step: OnboardingStep
    referral_code: str
    name: str
    age: int
    gender: Gender
    pool: Pool
    city_geonames_id: int
    institution_id: int | None
    height_cm: int | None
    goals: tuple[GoalCode, ...]
    interests: tuple[ChosenInterest, ...]
    prompts: tuple[PromptText, ...]


def generate(seed: int = SEED) -> list[DemoUser]:
    """Same seed, same users: ids, cities and pools never depend on randomness."""
    rng = random.Random(seed)  # noqa: S311 - demo data, not security
    ages = [rng.randint(16, ADULT_AGE - 1) for _ in range(MINORS)]
    ages += [rng.randint(ADULT_AGE, 25) for _ in range(ADULTS)]
    return [_user(rng, index, age) for index, age in enumerate(ages)]


def _user(rng: random.Random, index: int, age: int) -> DemoUser:
    gender = rng.choices((Gender.male, Gender.female, Gender.hidden), (45, 45, 10))[0]
    first_name = rng.choice(_FEMALE if gender is Gender.female else _MALE)
    city = CITIES[index % len(CITIES)]
    institutions = [i.id for i in INSTITUTIONS if i.city_geonames_id == city]
    return DemoUser(
        id=FIRST_USER_ID + index,
        tg_id=FIRST_TG_ID + index,
        tg_username=None if index % 7 == 0 else f"svoi_demo_{index:02d}",
        tg_first_name=first_name,
        lang=rng.choices((Lang.uk, Lang.ru, Lang.en), (80, 15, 5))[0],
        status=UserStatus.active,
        onboarding_step=OnboardingStep.done,
        referral_code=f"DEMO{index:03d}",
        name=first_name,
        age=age,
        gender=gender,
        pool=Pool.adult if age >= ADULT_AGE else Pool.minor,
        city_geonames_id=city,
        institution_id=rng.choice(institutions) if rng.random() < P_INSTITUTION else None,
        height_cm=rng.randint(HEIGHT_CM[0] + 35, HEIGHT_CM[1] - 35)
        if rng.random() < P_HEIGHT
        else None,
        goals=_goals(rng),
        interests=_interests(rng),
        prompts=_prompts(rng),
    )


def _goals(rng: random.Random) -> tuple[GoalCode, ...]:
    count = rng.randint(GOALS_COUNT[0], 3)
    picked = set(rng.sample(list(GoalCode), count))
    return tuple(g for g in GoalCode if g in picked)


def _interests(rng: random.Random) -> tuple[ChosenInterest, ...]:
    options = {c.interest_code: [o.key for o in c.options] for c in CLARIFICATIONS}
    picked = rng.sample(INTERESTS, rng.randint(INTERESTS_COUNT[0], 8))
    return tuple(
        ChosenInterest(
            i.id,
            rng.choice(options[i.code]) if i.code in options and rng.random() < P_NOTE else None,
        )
        for i in sorted(picked, key=lambda i: i.id)
    )


def _prompts(rng: random.Random) -> tuple[PromptText, ...]:
    chosen = rng.sample(PROMPTS, rng.randint(0, 2))
    return tuple(
        PromptText(p.id, rng.choice(_PROMPT_TEXTS[p.id]))
        for p in sorted(chosen, key=lambda p: p.id)
    )
