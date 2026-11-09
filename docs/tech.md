# tech.md — «Свої»: ядро проєкту

**Версія ядра: v5** · 2026-11-09

## Changelog

- v1 — початкова заморозка: схема БД, контракти API слайсів S1–S14, контракти черги, примітиви UI бота, продуктові константи.
- v2 — один Telegram-бот і одне середовище (`docs/adr/0001-single-bot.md`): прибрано компонент `admin-bot`, точку входу `svoi_bot.admin.main` і змінну `ADMIN_BOT_TOKEN`; модерація, `/user` і `/metrics` — адмін-розділ основного бота за `UserState.is_admin`; один VPS з деплоєм на мердж у `main` замість тестового і прод-VPS. Міграція: у `.env` видалити `ADMIN_BOT_TOKEN`; контракти API, черги, схема БД і константи не змінились.
- v3 — `ck_profiles_pool` обгорнуто в `COALESCE(..., false)`: вираз давав NULL для віку без пулу і пулу без віку, а CHECK пропускає NULL. Міграція `0002` перестворює обмеження; існуючі рядки з віком без пулу треба виправити до неї. Контракти API, черги і константи не змінились.
- v4 — додано dev-only топік `bot.demo` (`DemoPing`), тільки `ENV=local|test`: скелет перевіряє, що джоб від API доходить до `bot-worker` (K12, B0.2). Продуктові топіки не змінились.
- v5 — `MetricsOut` доповнено поточними підсумками для `/metrics`: усього користувачів, розподіл за статусом і пулом, верифіковані, тіньові бани, заблокували бота, активні за день / 7 / 30 днів, покази, пропуски, лайки з повідомленням і скарги за період, лайки й взаємності за весь час, лайки в очікуванні. Поля додано в кінець; старі значення не змінились. Міграції БД немає.

## Правила цього документа

- `tech.md` — єдине джерело істини для всіх сесій нейромережі: тимліда, фронтенду, бекенду.
- Змінює тільки тимлід. Зміни лише append-only: нове поле, новий ендпоінт, новий топік. Видалення або перейменування — тільки з новою версією і рядком у changelog з поясненням міграції.
- Кожна зміна контракту бампає версію (`v1` → `v2`) і додає рядок у changelog у форматі `vN — що змінилось`.
- Константа `svoi_contracts.CORE_VERSION` дорівнює номеру версії в заголовку. Тест `test_core_version_matches_tech_md` у CI парсить заголовок і падає при розбіжності.
- Сесія, якій бракує контракту, типу або поля, не вигадує його. Вона зупиняється і видає блок `CONTRACT GAP` (розділ 16).

---

## 1. Проєкт

«Свої» — Telegram-бот для пошуку друзів і однодумців за інтересами, містом, метою спілкування і навчальним закладом. Не дейтинг: стать вторинна, головне — що в людей спільного.

Для кого: молодь 16+ в Україні, яка шукає компанію, напарників для спорту, ігор, навчання, творчості.

Ціль продукту: людина за 2–3 хвилини заповнює анкету кнопками, бачить у стрічці людей зі спільними інтересами поруч, ставить лайк, при взаємності отримує username і пише в особисті.

Ключові відмінності від Дайвінчика:

- інтереси — теги, а не вільний текст; на картці видно «У вас спільного» і відсоток збігу;
- мета спілкування впливає на підбір (для онлайн-ігор географія майже не важлива);
- навідні запитання замість порожнього «розкажи про себе»;
- айсбрейкер при взаємності;
- захист від ботів і спаму: фільтр контенту, ліміти, ризик-скоринг, капча, верифікація кружком, тіньовий бан;
- пули 16–17 і 18+ повністю розділені;
- анкети не повторюються: кожен показ фіксується.

---

## 2. Стек

| Шар | Технологія |
| --- | --- |
| Мова | Python 3.12, повна типізація |
| Монорепо і залежності | uv workspaces |
| Бот (фронтенд) | aiogram 3.x, FSM на `RedisStorage`, i18n через `aiogram.utils.i18n` (gettext, Babel) |
| API (бекенд) | FastAPI, pydantic v2, uvicorn |
| БД | PostgreSQL 16 + PostGIS 3.4 + розширення `pg_trgm` |
| ORM і міграції | SQLAlchemy 2.0 (async, asyncpg), GeoAlchemy2, Alembic |
| Кеш, стан, ліміти | Redis 7 (redis-py asyncio) |
| Черга | arq (Redis), дві черги: `api` і `bot` |
| Контракти | пакет `svoi_contracts`: pydantic-моделі, енуми, константи — спільний для API і бота |
| Тести | pytest, pytest-asyncio, hypothesis (property-based), httpx `AsyncClient`, власний `BotHarness` для aiogram |
| Лінт і типи | ruff (lint + format), mypy `--strict` |
| Інфраструктура | Docker Compose, Caddy (TLS, webhook), GitHub Actions, GHCR |
| Хостинг | один VPS, автодеплой з `main` (`docs/adr/0001-single-bot.md`) |
| Задачі | Linear (ID задачі в назві гілки і PR) |
| Моніторинг | Sentry (помилки), логи у stdout у форматі JSON, Prometheus-метрики (`/metrics` API і воркерів) + Grafana |
| Бекапи | щоденний `pg_dump` з ротацією 14 днів у зовнішнє сховище, перевірка відновлення раз на місяць |

---

## 3. Архітектура і структура папок

### 3.1. Компоненти

- `bot` — процес єдиного бота. Приймає апдейти Telegram (webhook на VPS), веде FSM, малює клавіатури і картки, ходить в API по HTTP.
- `bot-worker` — arq-воркер черги `bot`. Надсилає користувачам сповіщення (лайки, взаємність, нагадування, результати модерації).
- Адмін-розділ — частина `bot`, не окремий бот: модерація, `/user`, `/metrics` доступні тільки при `UserState.is_admin`, обробляються до маршрутизації в онбординг, бан і капчу. Код — `svoi_bot/admin/features/`, роутери підключаються в `svoi_bot.main`.
- `api` — FastAPI. Уся бізнес-логіка, БД, алгоритм підбору, безпека. Доступний лише у внутрішній мережі Docker.
- `api-worker` — arq-воркер черги `api` + cron-задачі.
- `postgres`, `redis`, `caddy`.

Потоки даних:

- бот → API: HTTP `http://api:8000/v1/...`, заголовки `Authorization: Bearer <INTERNAL_API_TOKEN>` і `X-Tg-User-Id: <tg_id>`;
- API → черга `bot` → `bot-worker` → Telegram: сповіщення;
- API → черга `api` → `api-worker`: модерація фото, перебудова стрічки, cron;
- `bot-worker` → API: `POST /v1/internal/users/{tg_id}/bot-blocked`, коли Telegram повертає 403.

### 3.2. Структура репозиторію

```
svoi/
├── CLAUDE.md
├── docs/
│   ├── tech.md
│   ├── FRONTEND.md
│   ├── BACKEND.md
│   └── adr/                       # ADR-рішення щодо контрактів і нарізки
├── packages/
│   └── contracts/
│       ├── pyproject.toml
│       ├── fixtures/              # JSON-фікстури, генеруються сид-скриптом
│       └── svoi_contracts/
│           ├── __init__.py        # CORE_VERSION
│           ├── base.py            # Contract: базова модель усіх контрактів
│           ├── enums.py
│           ├── constants.py       # продуктові константи (розділ 4)
│           ├── errors.py          # ApiError, ErrorCode
│           ├── api/               # моделі запитів і відповідей по доменах
│           │   ├── users.py
│           │   ├── profile.py
│           │   ├── catalog.py
│           │   ├── prefs.py
│           │   ├── feed.py
│           │   ├── reactions.py
│           │   ├── likes.py
│           │   ├── safety.py
│           │   ├── moderation.py
│           │   ├── admin.py
│           │   ├── verification.py
│           │   └── referral.py
│           ├── cards.py           # ProfileCard, MatchResult та інші спільні типи
│           └── jobs.py            # payload-моделі черги
├── apps/
│   ├── api/
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/            # тільки тимлід
│   │   ├── tests/
│   │   └── svoi_api/
│   │       ├── main.py            # app factory
│   │       ├── config.py          # єдиний конфіг-модуль
│   │       ├── deps.py            # current_user, admin_user, db session
│   │       ├── core/              # redis, queue, errors handler, time
│   │       ├── db/                # base.py, models.py, session.py — тільки тимлід
│   │       ├── clients/           # інтерфейси зовнішніх клієнтів + фейки
│   │       ├── seed/              # сид-скрипт
│   │       ├── jobs/              # worker.py, реєстр хендлерів
│   │       └── domains/
│   │           └── <domain>/
│   │               ├── router.py  # FastAPI-роутер
│   │               ├── service.py # бізнес-логіка
│   │               ├── repo.py    # доступ до БД
│   │               ├── rules.py   # чиста доменна логіка (property-based тести)
│   │               └── jobs.py    # хендлери джобів домену
│   └── bot/
│       ├── pyproject.toml
│       ├── tests/
│       │   └── harness.py         # BotHarness
│       └── svoi_bot/
│           ├── main.py            # точка входу основного бота
│           ├── config.py
│           ├── api_client/        # ApiClient (протокол), HttpApiClient, FakeApiClient
│           ├── ui/                # примітиви UI (розділ 9) — тимлід
│           ├── middlewares/       # user context, throttle, i18n
│           ├── locales/           # uk, ru, en (.po)
│           ├── workers/           # arq-воркер черги bot
│           ├── features/
│           │   └── <slice>/
│           │       ├── router.py
│           │       ├── states.py
│           │       ├── handlers.py
│           │       └── views.py   # тексти + клавіатури екрана
│           └── admin/             # адмін-розділ того самого бота: features/
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── Caddyfile
│   └── deploy.sh
├── .github/
│   ├── CODEOWNERS
│   └── workflows/
│       ├── pr.yml
│       └── deploy.yml
├── .env.example
└── pyproject.toml                 # uv workspace, ruff, mypy
```

### 3.3. Домени бекенду

| Домен | Що робить | Слайси |
| --- | --- | --- |
| `users` | старт, мова, згода, стан онбордингу, видалення, bot-blocked | S1, S5 |
| `profiles` | вік, ім'я, стать, місто, цілі, інтереси, нотатки, заклад, зріст, промпти, медіа, картка, завершення онбордингу | S1–S5 |
| `catalog` | міста, цілі, категорії, інтереси, кастомні теги, уточнення, заклади, промпти | S2–S4 |
| `prefs` | фільтри і налаштування | S6 |
| `matching` | стрічка, скоринг, пачки кандидатів, покази, розширення пошуку | S7 |
| `reactions` | лайк, лайк з повідомленням, пропуск, повернення, ліміти | S8 |
| `likes` | вхідні лайки, відповідь, взаємність, контакти, айсбрейкер | S9 |
| `moderation` | скарги, блоки, черга модерації, дії модератора, модерація фото | S10 |
| `safety` | фільтр контенту, ризик-скоринг, капча, тіньовий бан, перевірка віку в тексті | S11 |
| `verification` | верифікація відеокружком | S12 |
| `notifications` | outbox, батчинг, тихі години, нагадування, дайджести | S13 |
| `referrals` | реферальні коди, бонуси | S14 |
| `metrics` | продуктові метрики для адмін-розділу бота, `user_activity_days` | S10b |

### 3.4. Фічі бота

| Папка `features/` | Слайси |
| --- | --- |
| `start` | S1 |
| `onboarding` (кроки), `city`, `interests`, `about` | S1–S4 |
| `my_profile` | S5 |
| `settings` | S6 |
| `feed` | S7, S8 |
| `likes`, `contacts` | S9 |
| `report` | S10 |
| `captcha` | S11 |
| `verification` | S12 |
| `referral` | S14 |
| `admin/features/queue` | S10, S12 |

---

## 4. Продуктові константи

Живуть у `svoi_contracts/constants.py`. Код не хардкодить ці значення, а імпортує їх. Зміна значення — зміна ядра.

```python
# Вік і пули
AGE_MIN = 16
AGE_MAX = 99
ADULT_AGE = 18                    # pool = adult, якщо age >= 18
AGE_EDIT_WINDOW_HOURS = 24        # вік можна змінити один раз протягом 24 год після першого введення
AGE_REJECT_COOLDOWN_DAYS = 30     # після віку < 16 повторне введення віку заблоковане 30 днів (age_locked)
DEFAULT_AGE_RANGE_DELTA = 3       # фільтр за замовчуванням: свій вік ±3, обрізаний межами пулу

# Анкета
NAME_LEN = (2, 20)
HEIGHT_CM = (120, 230)
GOALS_COUNT = (1, 7)
INTERESTS_COUNT = (3, 15)
CUSTOM_INTEREST_LEN = (2, 30)
PROMPTS_MAX = 2
PROMPT_TEXT_MAX = 300
MEDIA_MAX = 3
CLARIFICATIONS_MAX = 2

# Стрічка і підбір
FEED_BATCH_SIZE = 30
FEED_REFILL_AT = 5
FEED_MIX = (0.70, 0.20, 0.10)     # топ / середні / дослідження
INACTIVE_CUTOFF_DAYS = 14
SKIP_REPEAT_DAYS = 30
NEWBIE_BOOST = 0.10
NEWBIE_BOOST_HOURS = 48
SCORE_WEIGHTS = {
    "interests": 0.35,
    "geo": 0.20,
    "goals": 0.15,
    "institution": 0.10,
    "activity": 0.10,
    "age": 0.05,
    "quality": 0.05,
}
GEO_WEIGHT_ONLINE_GOAL = 0.05     # якщо в обох мета gaming і radius = any_online
CATEGORY_PARTIAL_MATCH = 0.30     # одна категорія, різні теги
SAME_INSTITUTION_TYPE_SCORE = 0.30
AGE_SCORE_SPAN_YEARS = 5
ACTIVITY_SCORE = {24: 1.0, 72: 0.6, 168: 0.3}   # годин з останньої активності → бал

# Реакції і ліміти
REACTIONS_PER_DAY = 100
MESSAGES_PER_DAY = 20
LIKE_MESSAGE_MAX = 300
LIKE_MEDIA_MAX_SECONDS = 30
UNDO_WINDOW_SECONDS = 60
RAPID_REACTION_INTERVAL_S = 1.0
RAPID_REACTION_STREAK_S = 60      # реакції частіше ніж раз на 1 с протягом 60 с → підозра
LIMITS_RESET_TZ = "Europe/Kyiv"   # ліміти скидаються о 00:00 за Києвом

# Лайки
LIKE_EXPIRE_DAYS = 14

# Безпека і модерація
REPORTS_AUTOHIDE = 3              # скарги від різних користувачів → автоприховування
REPORT_TEXT_MAX = 500
RISK_CAPTCHA_THRESHOLD = 50       # risk_score ≥ 50 → капча
CAPTCHA_OPTIONS = 6
CAPTCHA_TTL_SECONDS = 300
DUP_MESSAGE_THRESHOLD = 5         # той самий текст повідомлення 5+ різним людям за добу → shadow
NSFW_REJECT = 0.85                # бал ≥ → фото відхилено автоматично
NSFW_REVIEW = 0.50                # бал у [REVIEW, REJECT) → ручна черга photos
PHASH_DUP_DISTANCE = 6            # відстань Хеммінга ≤ → фото-дублікат з іншого акаунта
FAST_ONBOARDING_SECONDS = 40      # онбординг швидше → +ризик
CAPTCHA_FAILS_RISK = 3            # 3 помилки капчі поспіль → +10 ризику
OUTBOX_REENQUEUE_MINUTES = 30
OUTBOX_MAX_ATTEMPTS = 3
GEO_ROUND_DECIMALS = 2            # ~1 км
DISTANCE_BUCKETS_KM = (5, 25, 100)

# Сповіщення
QUIET_HOURS_DEFAULT = ("23:00", "08:00")
REMINDER_DAYS = (3, 7)
NEW_PEOPLE_DIGEST_PER_DAY = 1
NEW_PEOPLE_MIN = 3                # дайджест тільки якщо нових людей зі спільним інтересом ≥ 3
DAILY_DIGEST_HOUR = 19            # частота daily → о 19:00 за tz користувача

# Рефералка
REFERRAL_BONUS_REACTIONS = 20
```

---

## 5. Схема БД

Файл `apps/api/svoi_api/db/models.py`. Власник — тимлід. Міграції генеруються з моделей (`alembic revision --autogenerate`), застосовуються в кроці деплою. Розширення `postgis` і `pg_trgm` вмикаються першою міграцією.

```python
from datetime import date, datetime, time
from geoalchemy2 import Geography
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, Float,
    ForeignKey, Index, Integer, SmallInteger, String, Text, Time, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from svoi_contracts.enums import *  # енуми з розділу 6.1

class Base(DeclarativeBase): ...

def pg_enum(e):  # усі енуми зберігаються як PostgreSQL ENUM з ім'ям класу в snake_case
    return Enum(e, name=e.__name__.lower(), values_callable=lambda x: [i.value for i in x])

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    tg_username: Mapped[str | None] = mapped_column(String(32))
    tg_first_name: Mapped[str | None] = mapped_column(String(64))
    lang: Mapped[Lang] = mapped_column(pg_enum(Lang), default=Lang.uk)
    status: Mapped[UserStatus] = mapped_column(pg_enum(UserStatus), default=UserStatus.onboarding)
    onboarding_step: Mapped[OnboardingStep] = mapped_column(pg_enum(OnboardingStep), default=OnboardingStep.lang)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    risk_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    captcha_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL + status=banned → назавжди
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    report_weight: Mapped[float] = mapped_column(Float, default=1.0)  # знижується за хибні скарги
    referral_code: Mapped[str] = mapped_column(String(12), unique=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_users_status_active", "status", "last_active_at"),)

class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(SmallInteger)
    age_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_edits: Mapped[int] = mapped_column(SmallInteger, default=0)
    age_incremented_on: Mapped[date | None] = mapped_column(Date)
    age_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # остання спроба віку < AGE_MIN
    gender: Mapped[Gender | None] = mapped_column(pg_enum(Gender))
    pool: Mapped[Pool | None] = mapped_column(pg_enum(Pool))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    geo: Mapped[str | None] = mapped_column(Geography("POINT", srid=4326))  # округлено до GEO_ROUND_DECIMALS
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id", ondelete="SET NULL"))
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    completeness: Mapped[int] = mapped_column(SmallInteger, default=0)  # 0..100
    hidden_by_moderation: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64))  # хеш інтересів + медіа для «анкета змінилась»
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("age IS NULL OR age BETWEEN 16 AND 99", name="ck_profiles_age"),
        CheckConstraint("COALESCE((age IS NULL AND pool IS NULL) OR (age < 18 AND pool = 'minor') OR (age >= 18 AND pool = 'adult'), false)", name="ck_profiles_pool"),
        Index("ix_profiles_pool_city", "pool", "city_id"),
        Index("ix_profiles_geo", "geo", postgresql_using="gist"),
    )

class ProfileGoal(Base):
    __tablename__ = "profile_goals"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    goal: Mapped[GoalCode] = mapped_column(pg_enum(GoalCode), primary_key=True)

class InterestCategory(Base):
    __tablename__ = "interest_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    emoji: Mapped[str] = mapped_column(String(8))
    title_uk: Mapped[str] = mapped_column(String(40))
    title_ru: Mapped[str] = mapped_column(String(40))
    title_en: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(SmallInteger)

class Interest(Base):
    __tablename__ = "interests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("interest_categories.id"))
    code: Mapped[str] = mapped_column(String(48), unique=True)
    title_uk: Mapped[str] = mapped_column(String(30))
    title_ru: Mapped[str] = mapped_column(String(30))
    title_en: Mapped[str] = mapped_column(String(30))
    idf: Mapped[float] = mapped_column(Float, default=1.0)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    moderation_status: Mapped[ModerationStatus] = mapped_column(pg_enum(ModerationStatus), default=ModerationStatus.approved)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (
        Index("ix_interests_title_uk_trgm", "title_uk", postgresql_using="gin", postgresql_ops={"title_uk": "gin_trgm_ops"}),
        Index("ix_interests_title_ru_trgm", "title_ru", postgresql_using="gin", postgresql_ops={"title_ru": "gin_trgm_ops"}),
    )

class ProfileInterest(Base):
    __tablename__ = "profile_interests"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True)
    note_key: Mapped[str | None] = mapped_column(String(32))  # відповідь на уточнення, напр. "plays"
    __table_args__ = (Index("ix_profile_interests_interest", "interest_id"),)

class Clarification(Base):
    __tablename__ = "clarifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey("interests.id", ondelete="CASCADE"), unique=True)
    question_key: Mapped[str] = mapped_column(String(48))     # ключ i18n у боті
    options: Mapped[list[dict]] = mapped_column(JSONB)        # [{"key": "plays", "title_uk": "граю", "title_ru": "...", "title_en": "..."}]
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)

class Prompt(Base):
    __tablename__ = "prompts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title_uk: Mapped[str] = mapped_column(String(80))
    title_ru: Mapped[str] = mapped_column(String(80))
    title_en: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class ProfilePrompt(Base):
    __tablename__ = "profile_prompts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), primary_key=True)
    text: Mapped[str] = mapped_column(String(300))
    moderation_status: Mapped[ModerationStatus] = mapped_column(pg_enum(ModerationStatus), default=ModerationStatus.approved)

class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[MediaKind] = mapped_column(pg_enum(MediaKind))
    file_id: Mapped[str] = mapped_column(String(256))
    file_unique_id: Mapped[str] = mapped_column(String(64))
    phash: Mapped[str | None] = mapped_column(String(32))
    nsfw_score: Mapped[float | None] = mapped_column(Float)
    position: Mapped[int] = mapped_column(SmallInteger)
    moderation_status: Mapped[ModerationStatus] = mapped_column(pg_enum(ModerationStatus), default=ModerationStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "position"), Index("ix_media_phash", "phash"))

class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    geonames_id: Mapped[int] = mapped_column(Integer, unique=True)
    name_uk: Mapped[str] = mapped_column(String(80))
    name_ru: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    region_uk: Mapped[str] = mapped_column(String(80))
    region_ru: Mapped[str] = mapped_column(String(80))
    region_en: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2))
    location: Mapped[str] = mapped_column(Geography("POINT", srid=4326))
    population: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        Index("ix_cities_location", "location", postgresql_using="gist"),
        Index("ix_cities_name_uk_trgm", "name_uk", postgresql_using="gin", postgresql_ops={"name_uk": "gin_trgm_ops"}),
        Index("ix_cities_name_ru_trgm", "name_ru", postgresql_using="gin", postgresql_ops={"name_ru": "gin_trgm_ops"}),
        Index("ix_cities_name_en_trgm", "name_en", postgresql_using="gin", postgresql_ops={"name_en": "gin_trgm_ops"}),
    )

class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(40))
    type: Mapped[InstitutionType] = mapped_column(pg_enum(InstitutionType))
    source_id: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        Index("ix_institutions_city", "city_id"),
        Index("ix_institutions_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )

class Filters(Base):
    __tablename__ = "filters"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    age_min: Mapped[int] = mapped_column(SmallInteger)
    age_max: Mapped[int] = mapped_column(SmallInteger)
    gender: Mapped[GenderFilter] = mapped_column(pg_enum(GenderFilter), default=GenderFilter.all)
    radius: Mapped[RadiusMode] = mapped_column(pg_enum(RadiusMode), default=RadiusMode.city)
    verified_only: Mapped[bool] = mapped_column(Boolean, default=False)

class Settings(Base):
    __tablename__ = "settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notify_frequency: Mapped[NotifyFrequency] = mapped_column(pg_enum(NotifyFrequency), default=NotifyFrequency.instant)
    quiet_from: Mapped[time] = mapped_column(Time, default=time(23, 0))
    quiet_to: Mapped[time] = mapped_column(Time, default=time(8, 0))
    tz: Mapped[str] = mapped_column(String(40), default="Europe/Kyiv")
    show_distance: Mapped[bool] = mapped_column(Boolean, default=True)
    show_institution: Mapped[bool] = mapped_column(Boolean, default=True)

class View(Base):
    __tablename__ = "views"
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    action: Mapped[ViewAction] = mapped_column(pg_enum(ViewAction), default=ViewAction.shown)
    target_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    reshown: Mapped[bool] = mapped_column(Boolean, default=False)  # показ без реакції вже повертали один раз
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_views_viewer_action", "viewer_id", "action"),)

class Like(Base):
    __tablename__ = "likes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message: Mapped[str | None] = mapped_column(String(300))
    media_kind: Mapped[MessageMediaKind | None] = mapped_column(pg_enum(MessageMediaKind))
    media_file_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[LikeStatus] = mapped_column(pg_enum(LikeStatus), default=LikeStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("from_id", "to_id"),
        Index("ix_likes_to_status", "to_id", "status", "created_at"),
    )

class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # менший id
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # більший id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"), CheckConstraint("user_a_id < user_b_id", name="ck_matches_order"))

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # NULL — системна скарга (safety)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[ReportReason] = mapped_column(pg_enum(ReportReason))
    text: Mapped[str | None] = mapped_column(String(500))
    context: Mapped[ReportContext] = mapped_column(pg_enum(ReportContext))
    status: Mapped[ReportStatus] = mapped_column(pg_enum(ReportStatus), default=ReportStatus.open)
    moderator_tg_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("reporter_id", "target_id"), Index("ix_reports_target_status", "target_id", "status"))

class Block(Base):
    __tablename__ = "blocks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    gesture: Mapped[GestureCode] = mapped_column(pg_enum(GestureCode))
    video_note_file_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[ModerationStatus] = mapped_column(pg_enum(ModerationStatus), default=ModerationStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_verifications_status", "status", "created_at"),)

class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(pg_enum(NotificationKind))
    payload: Mapped[dict] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[OutboxStatus] = mapped_column(pg_enum(OutboxStatus), default=OutboxStatus.pending)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)  # скільки разів ставили в чергу bot
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_outbox_status_sched", "status", "scheduled_for"),)

class ReactionBonus(Base):
    __tablename__ = "reaction_bonuses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    on_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[BonusSource] = mapped_column(pg_enum(BonusSource))
    source_ref: Mapped[str] = mapped_column(String(64))  # напр. id запрошеного користувача
    __table_args__ = (UniqueConstraint("user_id", "source", "source_ref"),)

class UserActivityDay(Base):
    __tablename__ = "user_activity_days"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)  # за Europe/Kyiv; upsert при першому запиті за добу

class ModAction(Base):
    __tablename__ = "mod_actions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    moderator_tg_id: Mapped[int] = mapped_column(BigInteger)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    queue_kind: Mapped[AdminQueueKind] = mapped_column(pg_enum(AdminQueueKind))
    item_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[AdminAction] = mapped_column(pg_enum(AdminAction))
    reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Дані поза БД (Redis):

| Ключ | Тип | TTL | Призначення |
| --- | --- | --- | --- |
| `fsm:*` | — | — | стан FSM бота (aiogram `RedisStorage`) |
| `feed:batch:{user_id}` | list[int] | 6 год | пачка кандидатів |
| `feed:seen:{user_id}` | set[int] | без TTL | показані ID (дзеркало `views`); при зростанні бази — заміна на Bloom-фільтр (RedisBloom) через ADR, джерело істини лишається `views` |
| `feed:undo:{user_id}` | string (target_id) | 60 с | останній пропуск для «Повернути» |
| `lim:react:{user_id}:{yyyymmdd}` | int | 48 год | лічильник реакцій |
| `lim:msg:{user_id}:{yyyymmdd}` | int | 48 год | лічильник повідомлень до лайків |
| `rate:react:{user_id}` | sorted set | 120 с | таймстемпи реакцій для детектора ритму |
| `captcha:{challenge_id}` | hash | 300 с | капча |
| `dup:msg:{sha1}:{yyyymmdd}` | set[user_id отримувачів] | 48 год | детектор розсилок |
| `exposure:{user_id}:{yyyymmdd}` | int | 48 год | скільки разів анкету показали за добу |
| `notify:sent:{dedupe_key}` | string | 7 днів | ідемпотентність надсилання в `bot-worker` |

---

## 6. Спільні типи (`svoi_contracts`)

Усі моделі — `pydantic.BaseModel` з `model_config = ConfigDict(extra="forbid", frozen=True)`. Дати — `datetime` з tz (UTC). API локалізує всі `title`/`name` мовою користувача (`users.lang`).

### 6.1. Енуми (`enums.py`)

Усі — `StrEnum`, значення збігаються з іменем.

```python
Lang = uk | ru | en
UserStatus = onboarding | active | hidden | banned | deleted
OnboardingStep = lang | consent | age | name | gender | city | goals | interests | clarify | institution | height | prompts | media | preview | done
Gender = male | female | hidden
Pool = minor | adult
GoalCode = friends | walks | sport | study | gaming | creative | chat
MediaKind = photo | video
MessageMediaKind = voice | video_note
ModerationStatus = pending | approved | rejected
InstitutionType = university | college | other
GenderFilter = all | male | female
RadiusMode = city | km25 | km50 | km100 | region | country | any_online   # region — уся область міста користувача
DistanceBucket = same_city | km5 | km25 | km100
NotifyFrequency = instant | hourly | daily
ViewAction = shown | like | like_msg | skip | undo | report | block
ReactionType = like | like_msg | skip
LikeStatus = pending | matched | declined | expired
LikeDecision = accept | decline
ReportReason = spam | fake | nsfw | abuse | underage | scam | other
ReportContext = feed | incoming | contact | system   # system — тільки для системних скарг, у ReportIn заборонено
ReportStatus = open | accepted | rejected
FeedEmptyReason = no_candidates | limit_reached | profile_hidden | profile_incomplete | banned
IcebreakerTemplate = common_interest | same_institution | common_goal
GestureCode = three_fingers | thumb_up | peace | wave | ok_sign | point_up
AdminQueueKind = reports | photos | verifications | custom_tags | texts
AdminAction = ok | delete_media | delete_text | ban_7d | ban_forever | move_to_minor_pool | approve | reject
NotificationKind = likes | match | reminder | new_people | moderation
ReminderKind = day3 | day7
ModerationResultKind = media_rejected | text_removed | banned | unbanned | verified | verification_rejected | tag_approved | tag_rejected
OutboxStatus = pending | enqueued | sent | failed | cancelled
BonusSource = referral | admin
RebuildReason = filters_changed | profile_changed | expand | refill | daily
RiskLevel = low | high
ContentField = name | prompt | like_message | custom_interest | report_text
ContentBlockReason = link | mention | phone | stopword | age_mismatch
```

### 6.2. Помилки (`errors.py`)

```python
class ErrorCode(StrEnum):
    validation_error = "validation_error"     # 422
    not_found = "not_found"                   # 404
    conflict = "conflict"                     # 409, напр. крок онбордингу не поточний
    forbidden = "forbidden"                   # 403
    banned = "banned"                         # 403, details: {"until": datetime | None}
    age_too_young = "age_too_young"           # 400
    age_locked = "age_locked"                 # 400, вік уже не можна змінити
    profile_incomplete = "profile_incomplete" # 400, details: {"missing": list[str]}
    content_blocked = "content_blocked"       # 400, details: ContentBlockDetails
    media_forbidden = "media_forbidden"       # 400, медіа в повідомленні для пулу minor
    limit_reached = "limit_reached"           # 429, details: Limits
    rate_limited = "rate_limited"             # 429
    captcha_required = "captcha_required"     # 403
    undo_unavailable = "undo_unavailable"     # 409
    media_limit = "media_limit"               # 400
    internal = "internal"                     # 500

class ContentBlockDetails(BaseModel):
    field: ContentField
    reason: ContentBlockReason

class ApiError(BaseModel):
    code: ErrorCode
    message: str            # англійською, для логів; бот показує свій текст за code
    details: dict | None = None
```

### 6.3. Картки і спільні моделі (`cards.py`)

```python
class InterestChip(BaseModel):
    id: int
    title: str
    note: str | None = None        # локалізована нотатка уточнення: "граю"
    common: bool = False           # True, якщо інтерес є і в того, хто дивиться

class CommonBlock(BaseModel):
    interest_titles: list[str]
    same_institution: bool
    match_percent: int             # 0..100

class MediaRef(BaseModel):
    id: int
    kind: MediaKind
    file_id: str
    moderation_status: ModerationStatus   # у чужих картках завжди approved

class PromptAnswer(BaseModel):
    prompt_id: int
    title: str
    text: str

class ProfileCard(BaseModel):
    user_id: int
    name: str
    age: int
    verified: bool
    gender: Gender | None          # None, якщо hidden
    city_name: str
    distance: DistanceBucket | None  # None, якщо в когось немає geo або show_distance=False або пул minor поза містом
    goals: list[GoalCode]
    interests: list[InterestChip]  # спільні першими
    institution_name: str | None
    height_cm: int | None
    prompts: list[PromptAnswer]
    media: list[MediaRef]          # чужа картка: тільки approved; своя: усі
    common: CommonBlock | None     # тільки в стрічці і вхідних лайках
    completeness: int | None       # тільки своя картка

class ProfileCardShort(BaseModel):
    user_id: int
    name: str
    age: int
    city_name: str

class Icebreaker(BaseModel):
    template: IcebreakerTemplate
    interest_title: str | None = None
    institution_name: str | None = None
    goal: GoalCode | None = None

class MatchResult(BaseModel):
    match_id: int
    partner: ProfileCard
    partner_username: str | None
    partner_tg_id: int
    icebreaker: Icebreaker | None

class Limits(BaseModel):
    reactions_left: int
    messages_left: int
    resets_at: datetime

class Counters(BaseModel):
    incoming_likes: int

class UserState(BaseModel):
    user_id: int
    tg_id: int
    status: UserStatus
    lang: Lang
    onboarding_step: OnboardingStep
    pool: Pool | None
    needs_username: bool           # True, якщо tg_username порожній
    captcha_required: bool
    is_admin: bool
    counters: Counters

class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
```

---

## 7. Контракти API

### 7.1. Загальні правила

- Базовий шлях: `http://api:8000/v1`. API не публікується назовні.
- Автентифікація: `Authorization: Bearer <INTERNAL_API_TOKEN>`; ідентифікація користувача: `X-Tg-User-Id: <tg_id>`. Без токена — 401. Невідомий `tg_id` на будь-якому ендпоінті, крім `POST /users/start`, — 404 `not_found`.
- Кожен запит оновлює `users.last_active_at` (не частіше ніж раз на хвилину).
- Забанений користувач на будь-якому ендпоінті, крім `GET /users/me`, отримує 403 `banned`.
- Тіньово забанений користувач отримує звичайні відповіді; його анкета, лайки і повідомлення нікому не доставляються.
- Адмін-ендпоінти (`/admin/*`) доступні тільки для `tg_id` з `ADMIN_TG_IDS`, інакше 403 `forbidden`.
- Внутрішні ендпоінти (`/internal/*`) викликає тільки `bot-worker`.
- Помилки: тіло `ApiError`, HTTP-статус з розділу 6.2. Валідація pydantic → 422 `validation_error`.
- Списки: `Page[T]`, курсор непрозорий, `limit` за замовчуванням 20.
- Під час онбордингу кожен успішний `PUT` поточного кроку переводить `onboarding_step` на наступний крок за порядком `OnboardingStep`. `PUT` для вже пройденого кроку (редагування) крок не змінює.
- Опційні кроки онбордингу: `clarify`, `institution`, `height`, `prompts`, `media`. Їх пропускають через `POST /onboarding/skip`.

### 7.2. Ендпоінти

Моделі запитів і відповідей лежать у `svoi_contracts/api/<домен>.py` з тими самими іменами.

#### S1 — старт, мова, згода, вік, ім'я, стать (`users`, `profiles`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/users/start` | `StartIn` | `UserState` | `banned` |
| GET | `/users/me` | — | `UserState` | — |
| PUT | `/users/me/lang` | `LangIn` | `UserState` | — |
| POST | `/users/me/consent` | — | `UserState` | `conflict` |
| PUT | `/profile/age` | `AgeIn` | `UserState` | `age_too_young`, `age_locked`, `validation_error` |
| PUT | `/profile/name` | `NameIn` | `UserState` | `content_blocked`, `validation_error` |
| PUT | `/profile/gender` | `GenderIn` | `UserState` | — |
| POST | `/onboarding/skip` | `SkipIn` | `UserState` | `conflict` |

```python
class StartIn(BaseModel):
    tg_username: str | None
    tg_first_name: str | None
    tg_language_code: str | None      # для дефолтної мови
    has_tg_profile_photo: bool        # для ризик-скорингу
    referral_code: str | None = None  # з /start <payload>

class LangIn(BaseModel): lang: Lang
class AgeIn(BaseModel): age: int      # 0..150, бізнес-межі перевіряє домен
class NameIn(BaseModel): name: str
class GenderIn(BaseModel): gender: Gender
class SkipIn(BaseModel): step: OnboardingStep
```

#### S2 — місто і геолокація (`catalog`, `profiles`)

| Метод | Шлях | Тіло / query | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/catalog/cities/search` | `q: str (min 2)`, `limit: int = 5` | `list[CityOut]` | — |
| GET | `/catalog/cities/by-location` | `lat: float`, `lon: float` | `CityOut` | `not_found` |
| PUT | `/profile/city` | `CityIn` | `UserState` | `not_found` |

```python
class CityOut(BaseModel):
    id: int
    name: str
    region: str
    country_code: str

class CityIn(BaseModel):
    city_id: int
    lat: float | None = None   # якщо користувач надіслав геолокацію
    lon: float | None = None
```

#### S3 — цілі та інтереси (`catalog`, `profiles`)

| Метод | Шлях | Тіло / query | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/catalog/goals` | — | `list[GoalOut]` | — |
| PUT | `/profile/goals` | `GoalsIn` | `UserState` | `validation_error` |
| GET | `/catalog/interest-categories` | — | `list[CategoryOut]` | — |
| GET | `/catalog/interests` | `category_id: int` | `list[InterestOut]` | `not_found` |
| PUT | `/profile/interests` | `InterestsIn` | `UserState` | `validation_error` |
| POST | `/catalog/interests/custom` | `CustomInterestIn` | `CustomInterestOut` | `content_blocked`, `validation_error` |

```python
class GoalOut(BaseModel): code: GoalCode; title: str; emoji: str
class GoalsIn(BaseModel): codes: list[GoalCode]                     # GOALS_COUNT
class CategoryOut(BaseModel): id: int; code: str; emoji: str; title: str
class InterestOut(BaseModel): id: int; category_id: int; title: str
class InterestsIn(BaseModel): interest_ids: list[int]               # INTERESTS_COUNT, без дублікатів
class CustomInterestIn(BaseModel): title: str                       # CUSTOM_INTEREST_LEN
class CustomInterestOut(BaseModel):
    matched: InterestOut | None   # знайдено існуючий тег (similarity ≥ 0.6) — бот додає його до вибору
    pending: bool                 # створено кастомний тег на модерації; у анкеті з'явиться після approve
```

#### S4 — уточнення, заклад, зріст, «про себе», медіа, завершення (`profiles`, `catalog`)

| Метод | Шлях | Тіло / query | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/profile/clarifications` | — | `list[ClarificationOut]` (≤ `CLARIFICATIONS_MAX`) | — |
| PUT | `/profile/interests/{interest_id}/note` | `NoteIn` | `UserState` | `not_found`, `validation_error` |
| GET | `/catalog/institutions/search` | `city_id: int`, `q: str = ""`, `limit: int = 8` | `list[InstitutionOut]` | — |
| PUT | `/profile/institution` | `InstitutionIn` | `UserState` | `not_found` |
| PUT | `/profile/height` | `HeightIn` | `UserState` | `validation_error` |
| GET | `/catalog/prompts` | — | `list[PromptOut]` | — |
| PUT | `/profile/prompts` | `PromptsIn` | `UserState` | `content_blocked`, `validation_error` |
| POST | `/profile/media` | `MediaIn` | `MediaRef` | `media_limit` |
| DELETE | `/profile/media/{media_id}` | — | `UserState` | `not_found` |
| PUT | `/profile/media/order` | `MediaOrderIn` | `list[MediaRef]` | `validation_error` |
| POST | `/onboarding/complete` | — | `UserState` | `profile_incomplete` |

```python
class OptionOut(BaseModel): key: str; title: str
class ClarificationOut(BaseModel):
    interest_id: int
    interest_title: str
    question_key: str          # ключ i18n у боті: clarify.<question_key>
    options: list[OptionOut]
class NoteIn(BaseModel): option_key: str
class InstitutionOut(BaseModel): id: int; name: str; short_name: str | None; type: InstitutionType
class InstitutionIn(BaseModel): institution_id: int | None    # None — прибрати
class HeightIn(BaseModel): height_cm: int | None               # None — прибрати
class PromptOut(BaseModel): id: int; title: str
class PromptAnswerIn(BaseModel): prompt_id: int; text: str     # PROMPT_TEXT_MAX
class PromptsIn(BaseModel): answers: list[PromptAnswerIn]      # ≤ PROMPTS_MAX; [] — прибрати
class MediaIn(BaseModel): kind: MediaKind; file_id: str; file_unique_id: str
class MediaOrderIn(BaseModel): ids: list[int]
```

Обов'язкові поля для `POST /onboarding/complete`: `age`, `name`, `gender`, `city_id`, ≥1 мета, ≥3 інтереси. Успіх → `status = active`, `onboarding_step = done`, створюються `filters` і `settings` з дефолтами.

#### S5 — картка, «Моя анкета», приховати, видалити

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/profile/me/card` | — | `ProfileCard` (з `completeness`) | `profile_incomplete` |
| POST | `/profile/reset` | — | `UserState` | — |
| POST | `/profile/hide` | — | `UserState` | — |
| POST | `/profile/unhide` | — | `UserState` | `conflict` |
| DELETE | `/users/me` | — | `204` | — |

- Редагування полів — ті самі `PUT` з S1–S4.
- `POST /profile/reset` — `onboarding_step = age`, статус `onboarding`; лайки, контакти і покази зберігаються.
- `DELETE /users/me` видаляє всі дані користувача. Якщо `status = banned`, зберігається запис `users` з `tg_id` і статусом `banned`, решта видаляється.

#### S6 — фільтри і налаштування (`prefs`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/filters` | — | `FiltersOut` | — |
| PUT | `/filters` | `FiltersIn` | `FiltersOut` | `validation_error` |
| GET | `/settings` | — | `SettingsOut` | — |
| PUT | `/settings` | `SettingsIn` | `SettingsOut` | `validation_error` |

```python
class FiltersOut(BaseModel):
    age_min: int; age_max: int
    age_bounds: tuple[int, int]   # дозволені межі для пулу: (16, 17) або (18, 99)
    gender: GenderFilter; radius: RadiusMode; verified_only: bool
class FiltersIn(BaseModel):
    age_min: int; age_max: int; gender: GenderFilter; radius: RadiusMode; verified_only: bool
class SettingsOut(BaseModel):
    notify_frequency: NotifyFrequency; quiet_from: time; quiet_to: time
    show_distance: bool; show_institution: bool
class SettingsIn(SettingsOut): ...
```

#### S7 — стрічка (`matching`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/feed/next` | — | `FeedResponse` | — |
| POST | `/feed/expand` | `ExpandIn` | `FeedResponse` | `validation_error` |

```python
class FeedItem(BaseModel):
    kind: Literal["item"] = "item"
    card: ProfileCard
    can_undo: bool
class FeedEmpty(BaseModel):
    kind: Literal["empty"] = "empty"
    reason: FeedEmptyReason
    expand_options: list[RadiusMode]     # ширші за поточний radius
    resets_at: datetime | None           # для limit_reached
FeedResponse = Annotated[FeedItem | FeedEmpty, Field(discriminator="kind")]
class ExpandIn(BaseModel): radius: RadiusMode
```

- `GET /feed/next` записує показ (`views`, `action = shown`) до повернення відповіді.
- Вхідні лайки не йдуть через `/feed/next`; бот показує їх першими через S9.

#### S8 — реакції (`reactions`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/reactions` | `ReactionIn` | `ReactionOut` | `limit_reached`, `rate_limited`, `content_blocked`, `media_forbidden`, `captcha_required`, `conflict` |
| POST | `/reactions/undo` | — | `FeedItem` | `undo_unavailable` |
| GET | `/limits` | — | `Limits` | — |

```python
class MessageMedia(BaseModel):
    kind: MessageMediaKind
    file_id: str
    duration_s: int                       # ≤ LIKE_MEDIA_MAX_SECONDS
class ReactionIn(BaseModel):
    target_id: int
    type: ReactionType
    message: str | None = None            # ≤ LIKE_MESSAGE_MAX; обов'язково message або media для like_msg
    media: MessageMedia | None = None
class ReactionOut(BaseModel):
    match: MatchResult | None             # якщо target уже лайкнув тебе — одразу взаємність
    limits: Limits
```

`conflict` — реакція на анкету, яку не показували цьому користувачу, або повторна реакція.

#### S9 — вхідні лайки, взаємність, контакти (`likes`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/likes/incoming/count` | — | `CountOut` | — |
| GET | `/likes/incoming/next` | — | `IncomingResponse` | — |
| POST | `/likes/{like_id}/respond` | `RespondIn` | `RespondOut` | `not_found`, `conflict` |
| GET | `/matches/{match_id}` | — | `MatchResult` | `not_found` |
| GET | `/contacts` | `cursor`, `limit` | `Page[ContactOut]` | — |
| DELETE | `/contacts/{match_id}` | — | `204` | `not_found` |

```python
class CountOut(BaseModel): count: int
class IncomingLike(BaseModel):
    kind: Literal["like"] = "like"
    like_id: int
    card: ProfileCard
    message: str | None
    media: MessageMedia | None
class NoIncoming(BaseModel):
    kind: Literal["none"] = "none"
IncomingResponse = Annotated[IncomingLike | NoIncoming, Field(discriminator="kind")]
class RespondIn(BaseModel): decision: LikeDecision
class RespondOut(BaseModel): match: MatchResult | None
class ContactOut(BaseModel):
    match_id: int
    partner: ProfileCardShort
    partner_username: str | None
    partner_tg_id: int
    matched_at: datetime
```

#### S10 — скарги, блоки, модерація (`moderation`)

| Метод | Шлях | Тіло / query | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/reports` | `ReportIn` | `204` | `conflict` (уже скаржився), `content_blocked` |
| POST | `/blocks` | `BlockIn` | `204` | — |
| DELETE | `/blocks/{target_id}` | — | `204` | `not_found` |
| GET | `/admin/queue` | `kind: AdminQueueKind` | `AdminQueueItem \| None` | `forbidden` |
| GET | `/admin/queue/stats` | — | `dict[AdminQueueKind, int]` | `forbidden` |
| POST | `/admin/actions` | `AdminActionIn` | `204` | `forbidden`, `not_found`, `conflict` |
| GET | `/admin/users/{tg_id}` | — | `AdminUserOut` | `forbidden`, `not_found` |
| GET | `/admin/metrics` | `days: int = 7` (1..90) | `MetricsOut` | `forbidden`, `validation_error` |

```python
class ReportIn(BaseModel):
    target_id: int
    reason: ReportReason
    text: str | None = None              # обов'язково для other; ≤ REPORT_TEXT_MAX
    context: ReportContext
class BlockIn(BaseModel): target_id: int
class ReportBrief(BaseModel): reason: ReportReason; text: str | None; created_at: datetime
class AdminQueueItem(BaseModel):
    item_id: int                          # id report | media | verification | interest | profile_prompt
    kind: AdminQueueKind
    target_user_id: int
    target_tg_id: int
    target_card: ProfileCard              # повна, з pending-медіа
    reports: list[ReportBrief]
    media: MediaRef | None                # для photos
    verification_file_id: str | None      # для verifications
    verification_gesture: GestureCode | None
    custom_interest_title: str | None     # для custom_tags
    flagged_text: str | None              # для texts
    created_at: datetime
class AdminActionIn(BaseModel):
    kind: AdminQueueKind
    item_id: int
    action: AdminAction
    reason: str | None = None
class MetricsOut(BaseModel):
    period_from: date
    period_to: date
    starts: int                        # нові users за період
    onboarding_completed: int
    onboarding_rate: float             # completed / starts
    likes_total: int
    matches_total: int
    mutual_rate: float                 # лайки, що стали matched / усі лайки
    d1_retention: float                # частка нових, активних наступного дня
    d7_retention: float                # частка нових, активних на 7-й день
    reports_per_1000_views: float
    confirmed_reports_rate: float      # accepted / (accepted + rejected)
    users_total: int                   # v5: усі рядки users зараз
    users_by_status: dict[UserStatus, int]   # кожен статус, і з нулем
    users_by_pool: dict[Pool, int]     # анкети з віком
    verified_total: int
    shadow_banned_total: int
    bot_blocked_total: int
    active_today: int                  # user_activity_days за сьогодні (Europe/Kyiv)
    active_7d: int                     # різні користувачі за останні 7 днів
    active_30d: int
    views_total: int                   # покази за період
    skips_total: int                   # пропуски за період
    likes_with_message: int            # лайки з повідомленням за період
    reports_total: int                 # скарги користувачів за період (без системних)
    likes_all_time: int
    matches_all_time: int
    likes_pending: int                 # лайки, що зараз чекають відповіді
class AdminUserOut(BaseModel):
    user_id: int; tg_id: int; status: UserStatus; shadow_banned: bool
    banned_until: datetime | None; risk_score: int; card: ProfileCard | None
    reports_total: int; mod_actions: list[str]
```

#### S11 — антибот (`safety`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/users/me/captcha` | — | `CaptchaChallenge` | `conflict` (капча не потрібна) |
| POST | `/users/me/captcha/verify` | `CaptchaAnswerIn` | `UserState` | `not_found` (протухла), `validation_error` |

```python
class CaptchaChallenge(BaseModel):
    challenge_id: str
    target_emoji: str
    options: list[str]                    # CAPTCHA_OPTIONS емодзі у випадковому порядку
class CaptchaAnswerIn(BaseModel): challenge_id: str; answer: str
```

Ознаки віку < 18 у тексті промпту в пулі adult не блокують збереження: промпт зберігається зі статусом `pending`, анкета отримує `hidden_by_moderation = true`, створюється системна скарга `underage`. Ендпоінт повертає звичайний `UserState`. У повідомленні до лайку ті самі ознаки дають `content_blocked` з `age_mismatch` і системну скаргу.

Фільтр контенту не має окремого ендпоінта: застосовується доменом `safety` в `PUT /profile/name`, `PUT /profile/prompts`, `POST /reactions`, `POST /catalog/interests/custom`, `POST /reports` і повертає `content_blocked` з `ContentBlockDetails`.

#### S12 — верифікація (`verification`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/verification/start` | — | `GestureOut` | `conflict` (уже верифікований або є pending) |
| POST | `/verification/submit` | `VerificationIn` | `VerificationOut` | `not_found`, `conflict` |
| GET | `/verification/status` | — | `VerificationOut` | — |

```python
class GestureOut(BaseModel): verification_id: int; gesture: GestureCode
class VerificationIn(BaseModel): verification_id: int; video_note_file_id: str
class VerificationOut(BaseModel): status: ModerationStatus | None   # None — не подавав
```

`conflict` у `/verification/start` повертає `details: {"reason": "already_verified" | "pending" | "no_photo"}`; `no_photo` — немає жодного схваленого фото для порівняння.

#### S13 — сповіщення (`notifications`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| POST | `/internal/users/{tg_id}/bot-blocked` | — | `204` | `not_found` |
| POST | `/internal/notifications/{dedupe_key}/sent` | — | `204` | `not_found` |

Налаштування частоти і тихих годин — `PUT /settings` (S6).

#### S14 — рефералка (`referrals`)

| Метод | Шлях | Тіло | Відповідь | Помилки |
| --- | --- | --- | --- | --- |
| GET | `/referral` | — | `ReferralOut` | — |

```python
class ReferralOut(BaseModel):
    code: str                 # бот будує посилання https://t.me/<bot>?start=r_<code>
    invited_count: int
    bonus_per_invite: int     # REFERRAL_BONUS_REACTIONS
```

Реферальний код приходить у `StartIn.referral_code`. Бонус нараховується обом після `POST /onboarding/complete` запрошеного.

---

## 8. Контракти черги (arq)

Дві черги: `api` (споживач `api-worker`, бекенд) і `bot` (споживач `bot-worker`, фронтенд). Payload — pydantic-моделі з `svoi_contracts/jobs.py`, серіалізуються `model_dump(mode="json")`. Ім'я функції arq = назва топіка.

```python
class JobBase(BaseModel):
    dedupe_key: str
    core_version: int = CORE_VERSION

# Черга bot (продюсер: api-worker; споживач: bot-worker)
class NotifyLikes(JobBase):         # топік "bot.notify_likes"
    user_id: int; tg_id: int; lang: Lang; count: int
class NotifyMatch(JobBase):         # топік "bot.notify_match"
    match_id: int; recipient_user_id: int; tg_id: int; lang: Lang
class NotifyReminder(JobBase):      # топік "bot.notify_reminder"
    user_id: int; tg_id: int; lang: Lang; kind: ReminderKind
class NotifyNewPeople(JobBase):     # топік "bot.notify_new_people"
    user_id: int; tg_id: int; lang: Lang; interest_title: str; count: int
class NotifyModeration(JobBase):    # топік "bot.notify_moderation"
    user_id: int; tg_id: int; lang: Lang; result: ModerationResultKind; until: datetime | None = None
class DemoPing(JobBase):            # топік "bot.demo", тільки ENV=local|test: перевірка черги в скелеті
    note: str

# Черга api (продюсер: api; споживач: api-worker)
class ModeratePhoto(JobBase):       # топік "api.moderate_photo"
    media_id: int
class RebuildFeed(JobBase):         # топік "api.rebuild_feed"
    user_id: int; reason: RebuildReason
```

Cron у `api-worker` (без payload, ідемпотентні за побудовою):

| Топік | Розклад (Europe/Kyiv) | Що робить |
| --- | --- | --- |
| `api.notify_schedule` | кожні 5 хв | збирає `notification_outbox` зі статусом `pending` і `scheduled_for ≤ now`, ставить джоби в чергу `bot` |
| `api.likes_expire` | щодня 03:00 | `pending`-лайки старші за `LIKE_EXPIRE_DAYS` → `expired` |
| `api.tags_recalc_idf` | щодня 04:00 | перераховує `interests.idf` |
| `api.age_tick` | щодня 00:10 | +1 рік у річницю `age_set_at`, оновлення `pool` |
| `api.reminders_scan` | щогодини | створює outbox-нагадування day3/day7 |
| `api.new_people_scan` | щодня 18:00 | створює дайджест «нові люди з твоїм інтересом» |

Правила для всіх джобів:

- **Ідемпотентність обов'язкова.** Повторний запуск з тим самим payload дає рівно один ефект.
- Постановка в чергу завжди з `_job_id=dedupe_key`: arq не ставить дубль, поки джоб у черзі.
- `bot-worker` перед `send_message` робить `SET notify:sent:{dedupe_key} NX EX 604800`. Ключ уже є → вихід без надсилання. Telegram-помилка мережі або 5xx → ключ видаляється, ретрай arq.
- Ретраї arq: максимум 5, бекоф 10 с × номер спроби. Після останньої — лог у Sentry. `api.notify_schedule` повторно ставить у чергу outbox-записи зі статусом `enqueued`, старші за `OUTBOX_REENQUEUE_MINUTES`, до `OUTBOX_MAX_ATTEMPTS` разів, потім ставить `failed`. Повторна постановка безпечна: `bot-worker` відсікає дубль за `notify:sent:{dedupe_key}`.
- Telegram 403 (користувач заблокував бота) → `POST /internal/users/{tg_id}/bot-blocked`, ретрай не робиться.
- Успішне надсилання → `POST /internal/notifications/{dedupe_key}/sent`.
- `core_version` у payload менше за поточну → джоб обробляється, якщо модель валідна; невалідний payload → лог, без ретраю.

Формат `dedupe_key`:

| Топік | Ключ |
| --- | --- |
| `bot.notify_likes` | `likes:{user_id}:{window_start_iso}` |
| `bot.notify_match` | `match:{match_id}:{recipient_user_id}` |
| `bot.notify_reminder` | `reminder:{user_id}:{kind}:{last_active_date}` |
| `bot.notify_new_people` | `newpeople:{user_id}:{yyyymmdd}` |
| `bot.notify_moderation` | `mod:{queue_kind}:{item_id}:{action}` |
| `bot.demo` | `demo:{uuid}` |
| `api.moderate_photo` | `photo:{media_id}` |
| `api.rebuild_feed` | `feed:{user_id}:{reason}:{yyyymmddHHMM}` |

---

## 9. Примітиви UI бота (`apps/bot/svoi_bot/ui`)

Власник — тимлід. Фічі не пишуть власних клавіатур, рендерингу карток і обробки помилок API, а використовують ці модулі. Бракує примітива — `CONTRACT GAP`.

| Модуль | API примітива | Призначення |
| --- | --- | --- |
| `callbacks.py` | `NavCb(screen: str, arg: str = "")`, `PickCb(field: str, value: str)`, `ToggleCb(field: str, value: str)`, `PageCb(field: str, page: int)`, `DoneCb(field: str)`, `ReactCb(action: str, target_id: int)`, `LikeCb(action: str, like_id: int)`, `ReportCb(target_id: int, reason: str, context: str)`, `AdminCb(action: str, kind: str, item_id: int)` | фабрики `aiogram.filters.callback_data.CallbackData`, ліміт 64 байти |
| `keyboards.py` | `inline_choice(options: Sequence[Option], field: str, columns: int = 2, back: bool = False, skip: bool = False) -> InlineKeyboardMarkup` | одиничний вибір |
| | `multi_select(options, selected: set[str], field: str, columns: int = 2, min_count: int, max_count: int, page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup` | мультивибір з ✅, лічильником, пагінацією, кнопкою «Готово», неактивною поза межами |
| | `main_menu(counters: Counters) -> ReplyKeyboardMarkup` | головне меню, лічильник вхідних лайків |
| | `feed_keyboard() -> ReplyKeyboardMarkup` | `❤️` `💌` `👎` `💤` |
| | `location_request(skip_label: str) -> ReplyKeyboardMarkup` | кнопка `request_location` |
| | `confirm(yes: str, no: str, field: str) -> InlineKeyboardMarkup` | так / ні |
| | `remove() -> ReplyKeyboardRemove` | прибрати reply-клавіатуру |
| `cards.py` | `render_card(card: ProfileCard, mode: CardMode) -> RenderedCard` | текст + медіа картки; `CardMode = own \| feed \| incoming \| match \| admin` |
| | `send_card(bot, chat_id, rendered: RenderedCard, markup) -> list[Message]` | одне фото/відео з підписом, кілька — media group + окреме повідомлення з кнопками; обрізання підпису до 1024 символів |
| `screen.py` | `Screen(bot, state)`: `show(text, markup)`, `replace(text, markup)`, `clear()` | патерн «одне повідомлення на кроці»: inline-кроки редагують повідомлення, id зберігається в FSM |
| `progress.py` | `step_header(step: OnboardingStep) -> str` | «Крок 3 з 10» |
| `i18n.py` | `_(key, **params)`, `lazy_(key)`, `set_locale(lang)` | gettext; ключі `розділ.екран.елемент` |
| `errors.py` | `render_api_error(err: ApiError) -> str` | текст помилки за `ErrorCode` і `ContentBlockReason` |
| `format.py` | `goal_label(code)`, `distance_label(bucket)`, `gesture_label(code)`, `reason_label(reason)` | локалізовані підписи енумів |

```python
@dataclass(frozen=True)
class Option:
    value: str
    label: str

@dataclass(frozen=True)
class RenderedCard:
    text: str
    media: list[MediaRef]
    parse_mode: str = "HTML"
```

Формат картки (`render_card`, мова uk):

```
Назар, 18 ✅ · Могилів-Подільський · до 5 км
🎯 Шукає: друзів, напарника для спорту
🏷 CS2 · футбол (граю) · гітара (граю) · аніме
🎓 МПРЕК
📏 182 см
🌅 Ідеальні вихідні — це катка з друзями і вечір біля річки

✨ У вас спільного: CS2, футбол, один заклад · збіг 78%
```

Правила: порожні поля не виводяться; спільні інтереси першими; блок «спільного» тільки в `feed` і `incoming`; `own` додає рядок «Анкета заповнена на N%» і підказку, чого бракує; відстань тільки корзиною.

API-клієнт (`apps/bot/svoi_bot/api_client`, власник — тимлід):

- `ApiClient` — `Protocol` з методом на кожен ендпоінт розділу 7, типи з `svoi_contracts`. Назви: `start`, `get_me`, `set_lang`, `consent`, `set_age`, ..., `admin_action`.
- `HttpApiClient` — httpx, таймаут 5 с, 1 ретрай на мережеву помилку тільки для GET, `ApiError` → виняток `ApiException(err: ApiError)`.
- `FakeApiClient` — in-memory реалізація на фікстурах `packages/contracts/fixtures`. Валідує кожен запит моделлю контракту і падає `ContractViolation` на невалідних даних. Вміє: `fail_next(method, error: ApiError)`, `timeout_next(method)`, `calls: list[Call]` для асертів.
- Перемикач: `BOT_USE_FAKE_API=true` у `.env`.

Middlewares (власник — тимлід):

- `UserContextMiddleware` — на першому апдейті сесії викликає `start`, кладе `UserState` у `data["user_state"]`, кешує на 60 с у FSM-даних; маршрутизує в онбординг, якщо `status = onboarding`; показує екран бану, якщо `banned`; перенаправляє на капчу, якщо `captcha_required`.
- `I18nMiddleware` — мова з `UserState.lang`.
- `ThrottleMiddleware` — не більше 2 апдейтів на секунду від одного користувача на рівні бота, зайві ігноруються.

---

## 10. Інфраструктура і владіння

| Що | Власник | Правило |
| --- | --- | --- |
| `docs/tech.md`, `CLAUDE.md` | тимлід | append-only, бамп версії |
| `packages/contracts` | тимлід | тільки через `contract-change` |
| `apps/api/svoi_api/db`, `apps/api/migrations` | тимлід | міграції генеруються з моделей, застосовуються в кроці деплою; у PR-гейті проганяються на ефемерному Postgres |
| `apps/api/svoi_api/seed`, `packages/contracts/fixtures` | тимлід | детермінований сид (фіксований random seed); фікстури для `FakeApiClient` генеруються тим самим скриптом; `fixtures/clarifications.json` — замкнений список `question_key`, для кожного бот зобов'язаний мати переклад (тест `test_all_clarification_keys_translated`); сид містить приховану категорію `other` для кастомних тегів (не повертається в `/catalog/interest-categories`) |
| `apps/api/svoi_api/config.py`, `apps/bot/svoi_bot/config.py`, `.env.example` | тимлід | pydantic-settings; усе зовнішнє за фейками, старт без реальних секретів |
| `apps/api/svoi_api/core`, `deps.py`, `main.py`, `clients/` | тимлід | `clients/`: інтерфейс + фейк для кожного зовнішнього сервісу |
| `apps/bot/svoi_bot/ui`, `api_client`, `middlewares`, `main.py` | тимлід | |
| `apps/api/svoi_api/domains/*`, `jobs/` хендлери доменів | бекенд | |
| `apps/bot/svoi_bot/features/*`, `workers/`, `admin/features/*`, `locales` | фронтенд (тимлід) | |
| `infra/`, `.github/` | тимлід | |

Зовнішні клієнти бекенду (інтерфейс + фейк у скелеті):

| Інтерфейс | Реальна реалізація | Фейк |
| --- | --- | --- |
| `TelegramFilesClient.download(file_id) -> bytes` | Bot API `getFile` + завантаження | повертає байти з `fixtures/images/*` за file_id, вміє 500 і таймаут |
| `NsfwClassifier.score(image: bytes) -> float` | локальна open-source NSFW-модель в окремому контейнері | детермінований бал з імені фікстури |
| `ImageHasher.phash(image: bytes) -> str` | бібліотека `imagehash` (локально) | — (не зовнішній) |

`.env.example`:

```
ENV=local
BOT_TOKEN=000:fake
BOT_MODE=polling                 # polling | webhook
WEBHOOK_BASE_URL=
WEBHOOK_SECRET=change-me
BOT_USE_FAKE_API=true
API_BASE_URL=http://api:8000/v1
INTERNAL_API_TOKEN=change-me
DATABASE_URL=postgresql+asyncpg://svoi:svoi@postgres:5432/svoi
REDIS_URL=redis://redis:6379/0
ADMIN_TG_IDS=
USE_FAKE_CLIENTS=true
NSFW_URL=http://nsfw:8080
NEW_ACCOUNT_TG_ID_MIN=0          # tg_id вище → «дуже новий акаунт» для ризик-скорингу; 0 — вимкнено
SENTRY_DSN=
```

---

## 11. Стратегія тестів

Тести прив'язані до слайса і PR, не до стадії. Стадія — це кілька слайсів і кілька PR, окремої сутності «тести на стадію» немає. Слайс мерджиться тільки з тестами, гейт червоний без них.

Головна пастка: нейромережа пише код, потім пише тести, які підтверджують, що код робить те, що робить, разом з багами. Тести зелені й нічого не перевіряють. Тому правило: **тести виводяться з критеріїв приймання задачі, не з реалізації**. Тест кодує контракт, а не дзеркалить код.

Обов'язкові типи тестів на слайс:

- **Контрактні на стиках.** Найцінніші. Бекенд: відповідь кожного ендпоінта слайса валідується моделлю з `svoi_contracts`; кожен джоб, який ставить слайс, валідується payload-моделлю з `jobs.py`. Фронтенд: `FakeApiClient` — це і є тестовий шов, він валідує запит бота моделлю контракту і падає, якщо слайс шле сміття.
- **Ідемпотентність джобів.** На кожен хендлер — тест, який запускає його двічі з тим самим payload і перевіряє, що ефект рівно один (одне повідомлення, один запис, одна зміна статусу). Інакше подвійні сповіщення і подвійні бонуси.
- **Шлях помилки.** Зовнішній клієнт повернув 500, таймаут, ретрай. Бекенд — через фейки `clients/`; фронтенд — через `FakeApiClient.fail_next` / `timeout_next`: бот показує зрозумілий текст і не губить стан FSM.
- **Property-based на чистій доменній логіці (hypothesis).** Скоринг, фільтри підбору, фільтр контенту, ліміти, корзини відстані, вікна тихих годин. Генеруєш входи, перевіряєш інваріанти.

Інструменти:

- бекенд: `pytest` + `httpx.AsyncClient` на app factory, справжній Postgres з PostGIS (сервіс-контейнер у CI, локально docker), транзакція на тест з rollback;
- фронтенд: `BotHarness` (`apps/bot/tests/harness.py`) — `Dispatcher` + мок-сесія Bot, яка збирає всі вихідні методи; API — `FakeApiClient`. Методи: `send_text`, `send_command`, `press(callback_data)`, `send_location`, `send_photo`, `send_voice`, `send_video_note`, `last_message()`, `sent()`, `state()`;
- воркери: виклик функції хендлера напряму з фейковим `ctx`.

Якщо встановлено skill `engineering:testing-strategy`, сесія використовує його для фіксації підходу в описі PR.

---

## 12. Правила коду

- Python 3.12, `from __future__ import annotations` не потрібен; повні анотації типів, mypy `--strict` без `type: ignore` (виняток — з коментарем причини).
- ruff: правила `E,F,I,B,UP,SIM,ASYNC,S,PL,RUF`, довжина рядка 100.
- Тільки async-код у сервісах, репозиторіях, хендлерах.
- Шари бекенду: `router` (HTTP, без логіки) → `service` (бізнес-правила, транзакції) → `repo` (SQL) ; чиста логіка без I/O — у `rules.py`. Router не ходить у `repo` напряму.
- Доменні винятки — `DomainError(code: ErrorCode, details)`; маппінг у `ApiError` робить `core/errors.py`.
- Домени не імпортують один одного напряму, крім через `service` публічні функції, перелічені в `__init__.py` домену.
- Час — `core/time.now()` (UTC), щоб тести підміняли годинник.
- Бот: хендлер не містить тексту і клавіатур — вони у `views.py` фічі; `views.py` використовує тільки примітиви з `ui/`.
- Усі тексти користувача — через `_()`, ключі в `locales`. Мова за замовчуванням uk; ru і en обов'язкові до релізу MVP.
- Жодних секретів у коді і логах; `tg_username` і тексти анкет не логуються.
- Жодних `print`; логер `structlog` з контекстом `user_id`, `request_id`.
- Публічні функції доменів і примітиви UI мають docstring одним рядком.

---

## 13. Конвенція комітів, PR і коментарів

Застосовують усі сесії: тимліда і розробників.

- Мова — тільки англійська: коміти, заголовки й описи PR, коментарі в коді.
- **Формат коміту фіксований, завжди** Conventional Commits: `type(scope): summary`. `type` з закритого набору `feat|fix|test|refactor|chore|docs`. `scope` — домен або фіча (`profiles`, `feed`, `onboarding`, `ci`, `contracts`). `summary` в імперативі, з малої літери, без крапки в кінці, до ~50 символів. Тіло коміту — тільки щоб пояснити *чому*, не *що*.
- **Сесія комітить сама по ходу роботи**, маленькими логічними комітами після кожного осмисленого кроку, а не одним комітом наприкінці. Кожен коміт за можливості проходить тайпчек.
- Гілка: `<роль>/<LINEAR-ID>-<slug>`, роль: `lead`, `fe`, `be`. Приклад: `be/SVO-14-feed-scoring`.
- PR: заголовок короткий і містить ID задачі Linear: `SVO-14 feed: candidate scoring`. Тіло: що робить слайс, які контракти і типи зачіпає (з версією ядра), чим покрито тестами.
- **Коментарі в коді** короткі й по суті, пояснюють *чому*, а не переказують очевидний код. Закоментованого коду в PR немає.
- Дисципліна `stop-slop` на всю цю прозу: активний стан, імператив, без em-dash, без філерів.

---

## 14. Definition of Done однієї задачі

- ruff і mypy зелені;
- тести зелені і написані за доктриною розділу 11: виведені з критеріїв приймання; для кожного джоба — тест ідемпотентності; на стику слайса — контрактний тест; шлях помилки;
- `docker build` проходить;
- міграції (якщо змінювалась схема — тільки тимлід) проходять на ефемерному Postgres, `alembic check` без розбіжностей;
- PR прив'язаний до задачі Linear, гілка за конвенцією;
- нові тексти бота є в uk (ru, en — до релізу стадії);
- жодних вигаданих типів: усе з `tech.md` поточної версії;
- рев'ю пройдено, CI зелений, змерджено, задеплоєно на VPS.

---

## 15. Слайси і дорожня карта

Кожен слайс — одна фіча з двома PR: `-BE` (бекенд: домен + ендпоінти + тести) і `-FE` (фронтенд: фіча бота + тексти + тести). Обидва PR пишуться проти контракту з розділу 7, паралельно: фронтенд — проти `FakeApiClient`, бекенд — проти тестів контракту. Інтеграція перевіряється на VPS після мерджу обох.

### Етап 0 — скелет (тимлід, частину робить бекенд за делегуванням)

Розробники не починають слайси S2+, поки чек-лист «скелет готовий» не зелений повністю:

- [ ] CI зелений на тривіальному PR;
- [ ] `packages/contracts` поточної версії ядра у `main`, `CORE_VERSION` дорівнює версії в заголовку, тест версії зелений;
- [ ] моделі БД і перша міграція в `main`, міграції проходять на ефемерному Postgres у CI;
- [ ] сид дає каталоги і 50 анкет (40 adult, 10 minor) у 3 містах; фікстури для `FakeApiClient` згенеровані;
- [ ] FastAPI app factory, автентифікація, маппінг помилок, `/health` у `main`;
- [ ] черги `api` і `bot` ганяють демо-джоб від продюсера до споживача;
- [ ] фейки зовнішніх клієнтів віддають сид-дані і вміють помилку;
- [ ] бот: `main.py`, middlewares, примітиви `ui/` у `main`; роут `/kitchen_sink` (тільки `ENV=local|test`) показує всі примітиви;
- [ ] `FakeApiClient` і `BotHarness` у `main`;
- [ ] еталонний слайс S1 (BE + FE) у `main` і відповідає на `/start` на VPS;
- [ ] CODEOWNERS і branch protection увімкнені.

### MVP

| Слайс | Фіча | BE-домен | FE-фіча |
| --- | --- | --- | --- |
| S1 (еталон) | старт, мова, правила, вік, ім'я, стать, відновлення онбордингу з того самого кроку | `users`, `profiles` | `start`, `onboarding` |
| S2 | місто текстом з виправленням опечаток, геолокація → місто | `catalog`, `profiles` | `city` |
| S3 | цілі, категорії, інтереси, свій тег | `catalog`, `profiles` | `interests` |
| S4 | уточнення, заклад, зріст, «про себе» через промпти, фото/відео, попередній перегляд, завершення | `profiles`, `catalog`, `moderation` (фото) | `about`, `onboarding` |
| S5 | картка, «Моя анкета», редагування полів, заповнити заново, приховати, видалити, правило віку 24 год, авто-рік | `profiles`, `users` | `my_profile` |
| S6 | фільтри і налаштування | `prefs` | `settings` |
| S7 | стрічка: жорсткі фільтри, скоринг, пачки, мікс, без повторів, розширення пошуку (місто → область → країна) | `matching` | `feed` |
| S8 | лайк, лайк з повідомленням (текст/голос/кружок), пропуск, ліміти | `reactions`, `safety` (фільтр тексту) | `feed` |
| S9 | вхідні лайки першими, відповідь, взаємність з username, контакти, сповіщення про лайк і взаємність (миттєві) | `likes`, `notifications` (базові) | `likes`, `contacts`, `workers` |
| S10 | скарги, блок, автоприховування, адмін-розділ бота: черги, дії, бани, тіньовий бан | `moderation` | `report`, `admin` |
| S10b | метрики для адмін-розділу бота (`/metrics`), облік активних днів | `metrics` | `admin` |
| S11a | фільтр контенту, детектор розсилок, перевірка віку в тексті, пули (вже в S1/S7), ліміти ритму | `safety` | обробка `content_blocked`, `rate_limited` |

### Версія 1.1

| Слайс | Фіча | BE | FE |
| --- | --- | --- | --- |
| S7b | пошук за радіусом за координатами, корзини відстані на картці | `matching` | `settings`, `feed` |
| S7c | відсоток збігу і блок «У вас спільного» на картці | `matching` | `ui/cards` (тимлід), `feed` |
| S8b | «↩️ Повернути» | `reactions` | `feed` |
| S9b | айсбрейкер при взаємності | `likes` | `likes` |
| S11b | ризик-скоринг і капча | `safety` | `captcha` |
| S12 | верифікація відеокружком | `verification`, `moderation` | `verification`, `admin` |
| S13 | розумні сповіщення: батчинг, частота, тихі години, нагадування day3/day7, дайджест нових людей | `notifications` | `workers` |
| S14 | реферальне посилання і бонуси | `referrals`, `reactions` | `referral` |

### Версія 2 (контракти заморожуються на старті v2 окремою версією ядра)

| Слайс | Фіча |
| --- | --- |
| S15 | питання дня з відповіддю в анкеті |
| S16 | компанії за інтересами (3–5 людей, бот створює групу) |
| S17 | події: створити зустріч, «🙋 Іду», радіус 10 км, тільки свій пул |
| S18 | анонімний чат через бота для тих, у кого немає username |
| S19 | монетизація: буст анкети на добу, перегляд лайкнувших без черги, безлімітне «Повернути» |

### Запуск і метрики

- Запуск в одному місті або закладі; перші 200–300 анкет через місцеві чати й канали; лише потім наступне місто.
- Метрики з першого дня (слайс S10b, `GET /admin/metrics`, команда `/metrics` в адмін-розділі бота): частка завершених онбордингів від `/start`; частка взаємних лайків від усіх лайків; повернення через 1 і 7 днів; скарги на 1000 показів і частка підтверджених.

---

## 16. Процес CONTRACT GAP

Бракує контракту, типу, поля, примітиву UI, топіка або константи:

1. Сесія зупиняється і не пише код з вигаданим типом. Видає блок:

```
CONTRACT GAP
Core version: v1
Slice: S8-FE
Need: <що потрібно — поле, ендпоінт, тип, примітив>
Why: <навіщо, який критерій приймання без цього не виконати>
Proposed shape:
<pydantic-модель / сигнатура / таблиця>
Workaround until resolved: <локальна заглушка, яка не потрапляє в спільні файли>
```

2. Розробник відкриває issue з міткою `contract-change`, вставляє блок, продовжує роботу на локальній заглушці всередині своєї фічі або домену.
3. Тимлід додає контракт у `tech.md`, бампає версію, оновлює `svoi_contracts` (і моделі БД та міграцію, якщо треба), закриває issue посиланням на PR.
4. Розробник підтягує `main`, прибирає заглушку.

Тулінг: CODEOWNERS + branch protection вимагають рев'ю тимліда на зміни `docs/tech.md`, `CLAUDE.md`, `packages/contracts`, `apps/api/svoi_api/db`, `apps/api/migrations`, `apps/api/svoi_api/{core,clients,seed}`, `apps/bot/svoi_bot/{ui,api_client,middlewares}`, `infra`, `.github`.
