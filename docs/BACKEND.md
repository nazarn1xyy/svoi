# BACKEND.md — бекенд

Файл для бекендера і його сесії нейромережі. Ти пишеш API, бізнес-логіку, алгоритм підбору, безпеку, модерацію і фонові джоби. Бот, тексти й клавіатури пише фронтенд (тимлід).

Ядро: `docs/tech.md`, поточна версія **v2**.

Як читати цей файл:

1. Розділи 1–5 — правила: що таке контракт, де лежать файли, що твоє, як влаштований домен і запит.
2. Розділ 6 — довідник роутерів: для кожного ендпоінта Request, Response, що змінюється в БД, помилки.
3. Розділ 7 — робочий цикл і тести.
4. Додаток — детальні бізнес-правила і критерії приймання кожного слайсу.

---

## 0. Прочитай першим

- `docs/tech.md` — джерело істини. Підкоряйся йому дослівно. У Claude Code ядро підтягується через `CLAUDE.md` автоматично; в іншій сесії приклади `tech.md` до цього файлу.
- Перед задачею звір версію ядра в заголовку `tech.md` з версією в задачі. Ядро новіше — перечитай changelog.
- Нічого не вигадуй: таблиці, поля, моделі запитів і відповідей, енуми, топіки, константи — тільки з `tech.md` і `svoi_contracts`.
- Одна задача за раз, сфокусований дифф.
- Чогось бракує або незрозуміло, як працює ендпоінт — не придумуй, пиши `CONTRACT GAP` (розділ 5) або питай тимліда.

---

## 1. Що таке контракт

**Контракт** — це домовленість між ботом і бекендом, яку жоден з них не міняє сам. Бот шле рівно те, що описано, бекенд віддає рівно те, що описано. Тоді бот, написаний проти фейкового API, запрацює з твоїм справжнім API без доробок.

Контракт складається з:

| Що | Де лежить | Що там |
| --- | --- | --- |
| Моделі запитів і відповідей | `packages/contracts/svoi_contracts/api/<домен>.py` | `StartIn`, `AgeIn`, `FeedItem`, … — pydantic-класи. **Готові, писати їх не треба** |
| Спільні моделі | `svoi_contracts/cards.py` | `UserState`, `ProfileCard`, `MatchResult`, `Limits`, `Page[T]` |
| Енуми | `svoi_contracts/enums.py` | `OnboardingStep`, `Gender`, `Pool`, `ReactionType`, … |
| Помилки | `svoi_contracts/errors.py` | `ErrorCode`, `ApiError`, `ContentBlockDetails` |
| Константи | `svoi_contracts/constants.py` | `AGE_MIN`, `REACTIONS_PER_DAY`, … Код імпортує, не хардкодить |
| Payload джобів | `svoi_contracts/jobs.py` | `ModeratePhoto`, `RebuildFeed`, `NotifyMatch`, … |
| Таблиці БД | `apps/api/svoi_api/db/models.py` | SQLAlchemy-моделі `User`, `Profile`, `Like`, … |
| Міграції | `apps/api/migrations/` | Alembic, генерує тимлід |
| Сид і фікстури | `apps/api/svoi_api/seed/`, `packages/contracts/fixtures/` | каталоги, 845 міст, 50 демо-анкет |
| Опис усього цього словами | `docs/tech.md`, розділи 4–8 | |

Усі моделі успадковують `Contract` (`svoi_contracts/base.py`): `extra="forbid"` (зайве поле в тілі → 422) і `frozen=True`. Скаляри запитів суворі (`StrictInt`, `StrictStr`, `StrictBool`): `{"age": "18"}` — це 422, а не 18.

> **Стан на 2026-11-09.** Моделі контрактів (`svoi_contracts`) — у PR #6, моделі БД і перша міграція — у PR #7, сид — у PR #8. Поки вони не змерджені в `main`, у твоїй гілці цих файлів немає. Спершу дочекайся мерджу і підтягни `main`.

Як імпортувати:

```python
from svoi_contracts.api.profile import SkipIn
from svoi_contracts.cards import UserState
from svoi_contracts.enums import OnboardingStep
from svoi_contracts.errors import ErrorCode
from svoi_contracts.constants import AGE_MIN
from svoi_api.db.models import User, Profile
```

---

## 2. Що твоє, а що ні

> **З 2026-11-09 бекенд і бот пише одна людина (тимлід).** Поділ нижче лишається як карта шарів: «не твоє» тепер означає «міняй разом з `docs/tech.md` і новою версією ядра», а не «чекай чужого рев'ю».

**Твоє (пишеш сам, рев'ю звичайне):**

- `apps/api/svoi_api/domains/<домен>/` — `__init__.py`, `router.py`, `service.py`, `repo.py`, `rules.py`, `jobs.py` для всіх доменів з розділу 6;
- `apps/api/tests/domains/<домен>/` — тести;
- рядок реєстрації своїх джобів у `apps/api/svoi_api/jobs/worker.py`.

**Твоє за делегуванням тимліда (рев'ю тимліда обов'язкове, CODEOWNERS):**

- B0.1 `main.py` (app factory, підключення роутерів), `deps.py` (`current_user`, `admin_user`, сесія БД), `core/errors.py` (`DomainError` → `ApiError`, pydantic → 422), `/health`;
- B0.2 `core/queue.py` (`enqueue`), `jobs/worker.py` з демо-джобом і cron;
- B0.3 `clients/` (`TelegramFilesClient`, `NsfwClassifier`, `ImageHasher` + фейки);
- B0.4 еталонний слайс S1-BE.

**Не твоє (тільки читаєш):**

- `packages/contracts/**` — моделі вже готові. Потрібна зміна → `CONTRACT GAP`;
- `apps/api/svoi_api/db/models.py`, `apps/api/migrations/` — **міграцій не пишеш взагалі**. Потрібна колонка → `CONTRACT GAP`;
- `docs/`, `seed/`, `infra/`, `.github/`, `config.py`;
- `apps/bot/**` — фронтенд;
- чужий домен напряму: домени спілкуються тільки через публічні функції `service`, перелічені в `domains/<домен>/__init__.py`.

---

## 3. Як влаштований домен

Кожен домен — папка `apps/api/svoi_api/domains/<домен>/`:

| Файл | Що робить | Чого не робить |
| --- | --- | --- |
| `router.py` | FastAPI `APIRouter`: приймає `XxxIn`, викликає `service`, повертає `XxxOut` | бізнес-логіки, SQL |
| `service.py` | бізнес-правила, транзакція, кидає `DomainError` | HTTP, SQL напряму |
| `repo.py` | SQL-запити через SQLAlchemy | правил |
| `rules.py` | чисті функції без I/O (порядок кроків, скоринг, фільтр тексту) — їх тестує hypothesis | БД, Redis, час |
| `jobs.py` | хендлери джобів черги `api` | |
| `__init__.py` | публічні функції `service`, які можуть викликати інші домени | |

Приклад повністю: `POST /onboarding/skip` (домен `users`).

```python
# domains/users/rules.py
from svoi_contracts.enums import OnboardingStep

OPTIONAL_STEPS = frozenset({
    OnboardingStep.clarify, OnboardingStep.institution, OnboardingStep.height,
    OnboardingStep.prompts, OnboardingStep.media,
})
_ORDER = list(OnboardingStep)


def next_step(step: OnboardingStep) -> OnboardingStep:
    """Step after this one in OnboardingStep order."""
    return _ORDER[_ORDER.index(step) + 1]


# domains/users/service.py
from svoi_contracts.errors import ErrorCode
from svoi_api.core.errors import DomainError
from svoi_api.domains.users import repo, rules


async def skip_step(session: AsyncSession, user: User, step: OnboardingStep) -> UserState:
    """Skip the current optional onboarding step."""
    if step not in rules.OPTIONAL_STEPS or step != user.onboarding_step:
        raise DomainError(ErrorCode.conflict, {"current": user.onboarding_step})
    user.onboarding_step = rules.next_step(step)
    await session.commit()
    return await repo.user_state(session, user)


# domains/users/router.py
from fastapi import APIRouter
from svoi_contracts.api.profile import SkipIn
from svoi_contracts.cards import UserState

router = APIRouter(tags=["users"])


@router.post("/onboarding/skip", response_model=UserState)
async def skip(body: SkipIn, user: CurrentUser, session: DbSession) -> UserState:
    """POST /onboarding/skip."""
    return await service.skip_step(session, user, body.step)
```

`CurrentUser` і `DbSession` — залежності з `deps.py` (B0.1). Шаблон той самий для всіх ендпоінтів: router розпаковує запит → service перевіряє правила і пише в БД → repo збирає відповідь.

---

## 4. Як проходить будь-який запит

### 4.1. Заголовки

Бот ходить на `http://api:8000/v1/...` з заголовками:

```
Authorization: Bearer <INTERNAL_API_TOKEN>
X-Tg-User-Id: <tg_id>
Content-Type: application/json        # тільки коли є тіло
```

- **Хто робить запит, визначає заголовок `X-Tg-User-Id`, а не шлях і не тіло.** Тому `GET /users/me`, а не `/users/me/{tg_id}`: `me` — «користувач із заголовка». `deps.current_user` читає заголовок, знаходить `users` за `tg_id` і віддає в роутер.
- `tg_id` у шляху є тільки там, де він означає **іншу** людину: `GET /admin/users/{tg_id}` і `POST /internal/users/{tg_id}/bot-blocked`.
- `/internal/*` викликає `bot-worker` без `X-Tg-User-Id`, тільки з токеном.

### 4.2. Що робить `deps.current_user` до твого коду

1. Немає або хибний токен → `401`.
2. Немає користувача з таким `tg_id` → `404 not_found` (крім `POST /users/start`).
3. `status = banned` → `403 banned` з `details: {"until": ...}` (крім `GET /users/me`). Бан з `banned_until` у минулому знімається.
4. Оновлює `users.last_active_at` не частіше ніж раз на хвилину, пише день у `user_activity_days`.
5. Для `/admin/*`: `tg_id` не в `ADMIN_TG_IDS` → `403 forbidden`.

Твій ендпоінт отримує вже перевіреного `User`.

### 4.3. Помилки

У коді кидаєш `DomainError(ErrorCode.xxx, details)`. `core/errors.py` перетворює його на HTTP-статус і тіло `ApiError`:

```json
{"code": "conflict", "message": "step is not current", "details": {"current": "height"}}
```

| `code` | HTTP | Коли |
| --- | --- | --- |
| `validation_error` | 422 | pydantic не пропустив тіло або бізнес-межа (вік > 99, радіус без geo) |
| `not_found` | 404 | немає об'єкта або він не твій |
| `conflict` | 409 | дія не в тому стані (крок не поточний, уже скаржився, вже відповів) |
| `forbidden` | 403 | не адмін |
| `banned` | 403 | бан, `details.until` |
| `age_too_young` | 400 | вік < 16 |
| `age_locked` | 400 | вік змінювати вже не можна |
| `profile_incomplete` | 400 | `details.missing: [...]` |
| `content_blocked` | 400 | `details: {"field": ..., "reason": ...}` |
| `media_forbidden` | 400 | медіа в повідомленні для пулу minor |
| `media_limit` | 400 | уже 3 медіа |
| `limit_reached` | 429 | `details` = `Limits` |
| `rate_limited` | 429 | занадто швидкі реакції |
| `captcha_required` | 403 | треба пройти капчу |
| `undo_unavailable` | 409 | «Повернути» вже недоступне |
| `internal` | 500 | непередбачена помилка |

Бот показує свій текст за `code`, `message` — англійською для логів.

### 4.4. Онбординг: машина кроків

Це головне для S1–S4, без цього `consent` і `skip` не написати.

- `users.onboarding_step` — поточний крок. Порядок — порядок `OnboardingStep`:
  `lang → consent → age → name → gender → city → goals → interests → clarify → institution → height → prompts → media → preview → done`.
- Кожен ендпоінт кроку перевіряє `onboarding_step` користувача:

| Ендпоінт викликали, коли крок… | Що робити |
| --- | --- |
| …дорівнює кроку ендпоінта | зберегти дані, `onboarding_step` = наступний крок |
| …вже пройдений (редагування анкети) | зберегти дані, крок не міняти |
| …ще попереду | `409 conflict`, нічого не зберігати |

- Опційні кроки (`clarify`, `institution`, `height`, `prompts`, `media`) можна пропустити через `POST /onboarding/skip`.
- Відповідь — завжди `UserState` після зміни. Бот за `onboarding_step` малює наступний екран.
- Користувач з `status != onboarding` (анкета вже завершена) редагує будь-які поля без перевірки кроку.
- `POST /onboarding/complete` крок не перевіряє: перевіряє обов'язкові поля, ставить `onboarding_step = done` і `status = active`.

| Ендпоінт | Крок |
| --- | --- |
| `PUT /users/me/lang` | `lang` |
| `POST /users/me/consent` | `consent` (тільки поточний, редагування немає) |
| `PUT /profile/age` | `age` |
| `PUT /profile/name` | `name` |
| `PUT /profile/gender` | `gender` |
| `PUT /profile/city` | `city` |
| `PUT /profile/goals` | `goals` |
| `PUT /profile/interests` | `interests` |
| `PUT /profile/interests/{id}/note`, `POST /onboarding/skip {"step": "clarify"}` | `clarify` |
| `PUT /profile/institution` | `institution` |
| `PUT /profile/height` | `height` |
| `PUT /profile/prompts` | `prompts` |
| `POST /profile/media` (крок не міняє), `POST /onboarding/skip {"step": "media"}` | `media` |
| `POST /onboarding/complete` | `preview` (бот кличе з екрана перегляду) |

Уточнення (`clarify`) і медіа (`media`) приймають кілька запитів поспіль, тому `PUT .../note` і `POST /profile/media` крок **не** просувають. Крок закриває бот через `POST /onboarding/skip` («Готово» або «Пропустити»).

### 4.5. Як збирається `UserState`

`UserState` повертають майже всі ендпоінти S1–S5. Збирає одна функція в `users/repo.py`:

| Поле | Звідки |
| --- | --- |
| `user_id`, `tg_id`, `status`, `lang`, `onboarding_step` | `users` |
| `pool` | `profiles.pool` |
| `needs_username` | `users.tg_username IS NULL` |
| `captcha_required` | S11b; до нього `false` |
| `is_admin` | `tg_id in ADMIN_TG_IDS` |
| `counters.incoming_likes` | кількість вхідних `pending`-лайків (S9); до S9 — `0` |

```json
{
  "user_id": 2, "tg_id": 914462173, "status": "onboarding", "lang": "uk",
  "onboarding_step": "consent", "pool": null, "needs_username": false,
  "captcha_required": false, "is_admin": false, "counters": {"incoming_likes": 0}
}
```

---

## 5. CONTRACT GAP

Бракує поля, таблиці, ендпоінта, енуму, константи, топіка → **СТОП**. Видай блок:

```
CONTRACT GAP
Core version: v2
Slice: S7-BE
Need: <що потрібно>
Why: <який критерій приймання без цього не виконати>
Proposed shape:
<pydantic-модель / SQLAlchemy-колонка / сигнатура>
Workaround until resolved: <локальна заглушка в межах твого домену>
```

Код з вигаданим типом не пиши. Відкрий issue з міткою `contract-change`, встав блок, продовжуй на заглушці всередині `domains/<твій домен>/`. Тимлід додасть контракт у `tech.md`, підніме версію, оновить `svoi_contracts`, моделі і міграцію. Після мерджу підтягни `main` і прибери заглушку.

Незрозуміло, як має працювати ендпоінт, хоча все є? Це не GAP — це питання тимліду. Не вгадуй.

---

## 6. Довідник роутерів

### 6.1. Роутери за доменами

Кожен домен має один `router.py`, підключений у `main.py` з префіксом `/v1`.

| Домен | Файл | Ендпоінти |
| --- | --- | --- |
| `users` | `domains/users/router.py` | `POST /users/start`, `GET /users/me`, `PUT /users/me/lang`, `POST /users/me/consent`, `POST /onboarding/skip`, `POST /onboarding/complete`, `DELETE /users/me` |
| `profiles` | `domains/profiles/router.py` | `PUT /profile/age`, `/name`, `/gender`, `/city`, `/goals`, `/interests`, `/interests/{id}/note`, `/institution`, `/height`, `/prompts`; `GET /profile/clarifications`; `POST/DELETE/PUT /profile/media…`; `GET /profile/me/card`; `POST /profile/reset`, `/hide`, `/unhide` |
| `catalog` | `domains/catalog/router.py` | `GET /catalog/cities/search`, `/cities/by-location`, `/goals`, `/interest-categories`, `/interests`, `/institutions/search`, `/prompts`; `POST /catalog/interests/custom` |
| `prefs` | `domains/prefs/router.py` | `GET/PUT /filters`, `GET/PUT /settings` |
| `matching` | `domains/matching/router.py` | `GET /feed/next`, `POST /feed/expand` |
| `reactions` | `domains/reactions/router.py` | `POST /reactions`, `POST /reactions/undo`, `GET /limits` |
| `likes` | `domains/likes/router.py` | `GET /likes/incoming/count`, `/likes/incoming/next`, `POST /likes/{like_id}/respond`, `GET /matches/{match_id}`, `GET /contacts`, `DELETE /contacts/{match_id}` |
| `moderation` | `domains/moderation/router.py` | `POST /reports`, `POST /blocks`, `DELETE /blocks/{target_id}`, `GET /admin/queue`, `/admin/queue/stats`, `POST /admin/actions`, `GET /admin/users/{tg_id}` |
| `metrics` | `domains/metrics/router.py` | `GET /admin/metrics` |
| `safety` | `domains/safety/router.py` | `POST /users/me/captcha`, `POST /users/me/captcha/verify` |
| `verification` | `domains/verification/router.py` | `POST /verification/start`, `/verification/submit`, `GET /verification/status` |
| `notifications` | `domains/notifications/router.py` | `POST /internal/users/{tg_id}/bot-blocked`, `POST /internal/notifications/{dedupe_key}/sent` |
| `referrals` | `domains/referrals/router.py` | `GET /referral` |

`POST /onboarding/complete` живе в `users`, бо міняє `users.status`, але перевіряє поля анкети через публічну функцію `profiles.service`.

### 6.2. Формат опису ендпоінта

- **Коли** — у який момент бот робить запит;
- **Request** — модель з `svoi_contracts` (вже готова) і приклад JSON; `—` — тіла немає, вистачає заголовків з 4.1;
- **Response** — статус, модель і приклад;
- **БД** — що читати і що писати;
- **Логіка** — кроки;
- **Помилки** — коли яку кидати.

Детальні правила і критерії приймання — у Додатку, розділ слайса `S<n>-BE`.

### 6.3. S1 — старт, мова, згода, вік, ім'я, стать

Моделі (`svoi_contracts.api.users`, `svoi_contracts.api.profile`):

```python
class StartIn(Contract):
    tg_username: StrictStr | None
    tg_first_name: StrictStr | None
    tg_language_code: StrictStr | None      # мова за замовчуванням
    has_tg_profile_photo: StrictBool        # для ризик-скорингу
    referral_code: StrictStr | None = None  # з /start r_<code>

class LangIn(Contract):   lang: Lang
class AgeIn(Contract):    age: StrictInt     # 0..150; бізнес-межі перевіряєш ти
class NameIn(Contract):   name: StrictStr
class GenderIn(Contract): gender: Gender
class SkipIn(Contract):   step: OnboardingStep
```

#### `POST /users/start` — реєстрація або повернення

- **Коли:** перше повідомлення людини в сесії бота (`/start`, `/start r_<code>`, будь-яке повідомлення після перезапуску).
- **Request:** `StartIn`
  ```json
  {"tg_username": "ira", "tg_first_name": "Ira", "tg_language_code": "uk", "has_tg_profile_photo": true, "referral_code": null}
  ```
- **Response:** `200 UserState`.
- **БД:**
  - новий `tg_id` → `INSERT users` (`tg_id`, `tg_username`, `tg_first_name`, `lang`, `referral_code`, `referred_by_id`) + `INSERT profiles` (тільки `user_id`, решта `NULL`);
  - існуючий → `UPDATE users SET tg_username, tg_first_name, bot_blocked = false`.
- **Логіка:**
  1. Знайти `users` за `X-Tg-User-Id`. Тут невідомий `tg_id` — норма, не 404.
  2. Новий: `lang` = `uk`, якщо `tg_language_code` = `uk`; `ru`, якщо `ru`; інакше `uk`. `referral_code` — 8 символів base32, унікальний. `referred_by_id` — `users.id` власника коду, якщо код існує і не свій.
  3. `status = onboarding`, `onboarding_step = lang` — дефолти таблиці.
  4. Повернути `UserState`.
- **Помилки:** `403 banned` — користувач забанений (`details.until`).

#### `GET /users/me` — поточний стан

- **Коли:** бот оновлює кеш стану (раз на 60 с) або після дії, що могла змінити лічильники.
- **Request:** —
- **Response:** `200 UserState`.
- **БД:** тільки читання.
- **Логіка:** зібрати `UserState` (розділ 4.5). Єдиний ендпоінт, де забанений отримує `200`, щоб бот показав екран бану.

#### `PUT /users/me/lang` — мова

- **Коли:** крок `lang` або «Налаштування → Мова».
- **Request:** `LangIn` — `{"lang": "ru"}`
- **Response:** `200 UserState`.
- **БД:** `UPDATE users SET lang`; на кроці `lang` ще `onboarding_step = consent`.
- **Логіка:** правило кроку з 4.4. Усі `title`/`name` у наступних відповідях — цією мовою.
- **Помилки:** `422` — мова не `uk|ru|en`.

#### `POST /users/me/consent` — згода з правилами

- **Коли:** кнопка «Погоджуюсь» на кроці `consent`.
- **Request:** — (тіла немає; хто погоджується — із заголовка).
- **Response:** `200 UserState` з `onboarding_step = "age"`.
- **БД:** `UPDATE users SET consent_at = now(), onboarding_step = 'age'`.
- **Логіка:**
  1. `user.onboarding_step != consent` → `409 conflict`. Згоду не «редагують».
  2. Записати `consent_at`, перевести на `age`.
- **Помилки:** `409 conflict`.

#### `PUT /profile/age` — вік

- **Коли:** користувач ввів число на кроці `age` або змінює вік у «Моїй анкеті».
- **Request:** `AgeIn` — `{"age": 18}`
- **Response:** `200 UserState`, у ньому вже є `pool` (`minor` або `adult`).
- **БД:** `profiles.age`, `age_set_at` (перше введення), `age_edits` (+1 при зміні), `pool`, `age_rejected_at` (при віці < 16); `users.onboarding_step`.
- **Логіка (по порядку):**
  1. Правило кроку (4.4).
  2. `age_rejected_at` молодше 30 днів → `age_locked`.
  3. `age < 16` → записати `age_rejected_at = now`, `age_too_young`.
  4. `age > 99` → `validation_error`.
  5. Віку ще не було → `age`, `age_set_at = now`, `pool = adult` при `age ≥ 18`, інакше `minor`.
  6. Вік уже є → дозволено один раз (`age_edits = 0`) і тільки протягом 24 год від `age_set_at`; перехід `minor → adult` заборонений завжди; інакше `age_locked`.
- **Помилки:** `400 age_too_young`, `400 age_locked`, `422 validation_error`.

#### `PUT /profile/name` — ім'я

- **Request:** `NameIn` — `{"name": "Ira"}`
- **Response:** `200 UserState`.
- **БД:** `profiles.name`, крок.
- **Логіка:** обрізати пробіли; 2–20 символів; тільки літери, пробіл, дефіс, апостроф; без цифр; `safety.check_text(field=name)`.
- **Помилки:** `400 content_blocked` (`{"field": "name", "reason": "link"}`), `422 validation_error`, `409 conflict` (крок ще попереду).

#### `PUT /profile/gender` — стать

- **Request:** `GenderIn` — `{"gender": "female"}` (`male | female | hidden`)
- **Response:** `200 UserState`.
- **БД:** `profiles.gender`, крок.
- **Помилки:** `409 conflict`.

#### `POST /onboarding/skip` — пропустити опційний крок

- **Коли:** кнопка «Пропустити» або «Готово» на кроках `clarify`, `institution`, `height`, `prompts`, `media`.
- **Request:** `SkipIn` — `{"step": "height"}`; `step` — крок, який бот зараз показує.
- **Response:** `200 UserState` з наступним кроком (`height` → `prompts`, `media` → `preview`).
- **БД:** `UPDATE users SET onboarding_step = <наступний>`. Дані анкети не чіпаються.
- **Логіка:**
  1. `step` не опційний (`lang`, `age`, `city`, …) → `409 conflict`.
  2. `step != user.onboarding_step` → `409 conflict` (захист від подвійного натискання і старих кнопок).
  3. `onboarding_step` = наступний за порядком `OnboardingStep`.
- **Помилки:** `409 conflict`.
- Повний код — приклад у розділі 3.

---

### 6.4. S2 — місто

```python
class CityOut(Contract): id: int; name: str; region: str; country_code: str
class CityIn(Contract):  city_id: StrictInt; lat: float | None = None; lon: float | None = None
```

#### `GET /catalog/cities/search?q=вінн&limit=5` — пошук міста

- **Коли:** користувач пише назву міста текстом.
- **Request:** query `q` (мінімум 2 символи), `limit` (за замовчуванням 5).
- **Response:** `200 list[CityOut]`; нічого не знайдено → `[]`.
  ```json
  [{"id": 12, "name": "Вінниця", "region": "Вінницька область", "country_code": "UA"}]
  ```
- **БД:** читання `cities`; `similarity()` з `pg_trgm` по `name_uk/ru/en`, поріг 0.3, сортування за схожістю, потім за `population`. `name` і `region` — мовою користувача.
- **Помилки:** `422` — `q` коротше 2 символів.

#### `GET /catalog/cities/by-location?lat=48.44&lon=27.79` — місто за геолокацією

- **Коли:** користувач натиснув «Надіслати геолокацію».
- **Response:** `200 CityOut` — найближче місто в радіусі 30 км (`ST_DWithin`).
- **Помилки:** `404 not_found` — поруч немає міста.

#### `PUT /profile/city` — зберегти місто

- **Request:** `CityIn` — `{"city_id": 12, "lat": 48.44, "lon": 27.79}`; `lat/lon` тільки якщо була геолокація.
- **Response:** `200 UserState`.
- **БД:** `profiles.city_id`; `profiles.geo` = точка, округлена до 2 знаків, або `NULL` без координат; крок; джоб `RebuildFeed(reason=profile_changed)`.
- **Помилки:** `404 not_found` — немає такого `city_id`; `422` — координати далі 50 км від міста.

---

### 6.5. S3 — цілі та інтереси

```python
class GoalOut(Contract):           code: GoalCode; title: str; emoji: str
class GoalsIn(Contract):           codes: list[GoalCode]       # 1..7
class CategoryOut(Contract):       id: int; code: str; emoji: str; title: str
class InterestOut(Contract):       id: int; category_id: int; title: str
class InterestsIn(Contract):       interest_ids: list[StrictInt]  # 3..15, без дублів
class CustomInterestIn(Contract):  title: StrictStr            # 2..30 символів
class CustomInterestOut(Contract): matched: InterestOut | None; pending: bool
```

#### `GET /catalog/goals` — список цілей

- **Response:** `200 list[GoalOut]`, усі 7 `GoalCode`:
  ```json
  [{"code": "friends", "title": "Знайти друзів", "emoji": "👫"}]
  ```
- **БД:** немає. Назви й емодзі — словник у `catalog/rules.py` (uk, ru, en).

#### `PUT /profile/goals` — вибрані цілі

- **Request:** `GoalsIn` — `{"codes": ["friends", "sport"]}`
- **Response:** `200 UserState`.
- **БД:** `DELETE profile_goals WHERE user_id` + `INSERT` нового набору; крок; `RebuildFeed(profile_changed)`.
- **Помилки:** `422` — 0 або більше 7, дублі.

#### `GET /catalog/interest-categories` — категорії

- **Response:** `200 list[CategoryOut]` за `position`, без прихованої `other`.

#### `GET /catalog/interests?category_id=1` — теги категорії

- **Response:** `200 list[InterestOut]`, тільки `moderation_status = approved`.
- **Помилки:** `404 not_found` — немає категорії.

#### `PUT /profile/interests` — вибрані інтереси

- **Request:** `InterestsIn` — `{"interest_ids": [101, 102, 205]}`
- **Response:** `200 UserState`.
- **БД:** повна заміна `profile_interests`; `note_key` інтересів, що лишились у наборі, зберігається; перерахунок `completeness`, `snapshot_hash`; крок; `RebuildFeed(profile_changed)`.
- **Помилки:** `422` — менше 3 або більше 15, дублі, неіснуючий чи не `approved` id.

#### `POST /catalog/interests/custom` — свій тег

- **Request:** `CustomInterestIn` — `{"title": "бордгейми"}`
- **Response:** `200 CustomInterestOut`:
  - знайдено схожий `approved` тег (similarity ≥ 0.6) → `{"matched": {"id": 140, "category_id": 3, "title": "Настолки"}, "pending": false}`; бот сам додасть його до вибору;
  - не знайдено → `{"matched": null, "pending": true}`.
- **БД:** у другому випадку `INSERT interests` (`is_custom = true`, `moderation_status = pending`, категорія `other`, `created_by_id`, однакова назва в трьох мовах). Тег з'явиться в анкеті після схвалення модератором (S10).
- **Помилки:** `400 content_blocked`, `422`.

---

### 6.6. S4 — уточнення, заклад, зріст, промпти, медіа, завершення

```python
class OptionOut(Contract):        key: str; title: str
class ClarificationOut(Contract): interest_id: int; interest_title: str; question_key: str; options: list[OptionOut]
class NoteIn(Contract):           option_key: StrictStr
class InstitutionOut(Contract):   id: int; name: str; short_name: str | None; type: InstitutionType
class InstitutionIn(Contract):    institution_id: StrictInt | None   # None — прибрати
class HeightIn(Contract):         height_cm: StrictInt | None        # None — прибрати
class PromptOut(Contract):        id: int; title: str
class PromptAnswerIn(Contract):   prompt_id: StrictInt; text: StrictStr  # ≤ 300
class PromptsIn(Contract):        answers: list[PromptAnswerIn]      # ≤ 2; [] — прибрати
class MediaIn(Contract):          kind: MediaKind; file_id: StrictStr; file_unique_id: StrictStr
class MediaOrderIn(Contract):     ids: list[StrictInt]
# відповіді: MediaRef, UserState — svoi_contracts.cards
```

#### `GET /profile/clarifications` — питання-уточнення

- **Коли:** крок `clarify`, після кожної відповіді бот питає знову.
- **Response:** `200 list[ClarificationOut]`, не більше 2; порожній список — питань не лишилось.
  ```json
  [{"interest_id": 25, "interest_title": "Гітара", "question_key": "guitar_play", "options": [{"key": "plays", "title": "граю"}, {"key": "listens", "title": "слухаю"}, {"key": "learning", "title": "вчуся"}]}]
  ```
- **БД:** інтереси користувача, для яких є рядок у `clarifications` і ще немає `note_key`, за `priority`. `question_key` — ключ перекладу в боті, тому береться тільки з таблиці.

#### `PUT /profile/interests/{interest_id}/note` — відповідь на уточнення

- **Request:** path `interest_id` (напр. `25`), тіло `NoteIn` — `{"option_key": "plays"}`
- **Response:** `200 UserState`. Крок **не** змінюється (4.4).
- **БД:** `UPDATE profile_interests SET note_key`.
- **Помилки:** `404 not_found` — інтересу немає в анкеті або для нього немає уточнення; `422` — `option_key` немає в `options`.

#### `GET /catalog/institutions/search?city_id=12&q=мпрек&limit=8` — заклади

- **Response:** `200 list[InstitutionOut]`
  ```json
  [{"id": 7, "name": "Могилів-Подільський промислово-економічний фаховий коледж", "short_name": "МПРЕК", "type": "college"}]
  ```
- **БД:** `institutions WHERE city_id`; порожній `q` → за кількістю анкет із цим закладом, потім за назвою; з `q` — trigram по `name`.

#### `PUT /profile/institution` — заклад

- **Request:** `{"institution_id": 7}` або `{"institution_id": null}` — прибрати.
- **Response:** `200 UserState`.
- **БД:** `profiles.institution_id`, `completeness`, крок.
- **Помилки:** `404 not_found`.

#### `PUT /profile/height` — зріст

- **Request:** `{"height_cm": 182}` або `{"height_cm": null}`.
- **Response:** `200 UserState`.
- **БД:** `profiles.height_cm`, крок.
- **Помилки:** `422` — поза 120–230.

#### `GET /catalog/prompts` — навідні запитання

- **Response:** `200 list[PromptOut]` з `prompts WHERE active`: `[{"id": 3, "title": "Ідеальні вихідні — це…"}]`.

#### `PUT /profile/prompts` — відповіді на промпти

- **Request:** `PromptsIn`
  ```json
  {"answers": [{"prompt_id": 3, "text": "катка з друзями і вечір біля річки"}]}
  ```
- **Response:** `200 UserState`.
- **БД:** повна заміна `profile_prompts`; `completeness`; крок.
- **Логіка:** кожен текст через `safety.check_text(field=prompt)`. Ознаки віку < 18 у пулі adult не блокують: промпт `pending`, `profiles.hidden_by_moderation = true`, системна скарга `underage` (S11).
- **Помилки:** `400 content_blocked`, `422` — неіснуючий `prompt_id`, більше 2 відповідей, текст > 300.

#### `POST /profile/media` — додати фото або відео

- **Коли:** користувач надіслав фото чи відео на кроці `media` або в «Моїй анкеті». Файл лежить у Telegram, бот передає тільки його `file_id`.
- **Request:** `MediaIn` — `{"kind": "photo", "file_id": "AgACAgIAAxk...", "file_unique_id": "AQADBb4x..."}`
- **Response:** `200 MediaRef`
  ```json
  {"id": 55, "kind": "photo", "file_id": "AgACAgIAAxk...", "moderation_status": "pending"}
  ```
- **БД:** `INSERT media` (`position` — наступна вільна, `moderation_status = pending`). Фото → джоб `ModeratePhoto(media_id)`; відео → одразу в ручну чергу `photos`. Крок не змінюється.
- **Помилки:** `400 media_limit` — уже 3 медіа.

#### `DELETE /profile/media/{media_id}` — видалити медіа

- **Response:** `200 UserState`.
- **БД:** `DELETE media`, ущільнити `position` решти.
- **Помилки:** `404 not_found` — немає або не твоє.

#### `PUT /profile/media/order` — новий порядок

- **Request:** `MediaOrderIn` — `{"ids": [57, 55, 56]}`, рівно всі медіа користувача.
- **Response:** `200 list[MediaRef]` у новому порядку.
- **БД:** `UPDATE media SET position`.
- **Помилки:** `422` — не той набір id.

#### `POST /onboarding/complete` — завершити анкету

- **Коли:** кнопка «Все вірно» на екрані перегляду анкети (крок `preview`).
- **Request:** —
- **Response:** `200 UserState` з `status = "active"`, `onboarding_step = "done"`.
- **БД:** `users.status`, `onboarding_step`; `INSERT filters` (вік ±3 у межах пулу, `gender = all`, `radius = city`); `INSERT settings` (дефолти); `reaction_bonuses` для рефералки (S14); `RebuildFeed(profile_changed)`.
- **Логіка:** перевірити `age`, `name`, `gender`, `city_id`, ≥1 мету, ≥3 інтереси. Чогось бракує → `profile_incomplete`.
- **Помилки:** `400 profile_incomplete` з `details: {"missing": ["city", "interests"]}`. Ключі `missing`: `age`, `name`, `gender`, `city`, `goals`, `interests`.

---

### 6.7. S5 — картка, «Моя анкета», приховати, видалити

#### `GET /profile/me/card` — своя анкета

- **Коли:** «👤 Моя анкета», попередній перегляд перед `complete`.
- **Response:** `200 ProfileCard` (`svoi_contracts.cards`) у режимі `own`: усі медіа й промпти з їхнім `moderation_status`, `completeness` 0..100, `common = null`.
  ```json
  {"user_id": 2, "name": "Ira", "age": 18, "verified": false, "gender": "female", "city_name": "Вінниця",
   "distance": null, "goals": ["friends"], "interests": [{"id": 101, "title": "CS2", "note": "граю", "common": false}],
   "institution_name": null, "height_cm": null, "prompts": [], "media": [], "common": null, "completeness": 40}
  ```
- **Логіка:** `profiles.service.build_card(viewer, target, mode)` — одна функція на всі режими (S5 у Додатку).
- **Помилки:** `400 profile_incomplete` — ще немає віку, імені або міста.

#### `POST /profile/reset` — «Заповнити заново»

- **Response:** `200 UserState` з `status = onboarding`, `onboarding_step = age`.
- **БД:** тільки `users.status`, `onboarding_step`. Вік, лайки, контакти, покази лишаються.

#### `POST /profile/hide` / `POST /profile/unhide` — приховати / показати анкету

- **Response:** `200 UserState` (`status = hidden` / `active`).
- **Помилки:** `unhide` не з `hidden` → `409 conflict`.

#### `DELETE /users/me` — видалити все

- **Response:** `204`, тіла немає.
- **БД:** `DELETE users` (каскад видаляє решту). Забанений: лишити рядок `users` з `tg_id` і `status = banned`, решту видалити.

---

### 6.8. S6 — фільтри і налаштування

```python
class FiltersOut(Contract):
    age_min: int; age_max: int
    age_bounds: tuple[int, int]     # (16, 17) або (18, 99)
    gender: GenderFilter; radius: RadiusMode; verified_only: bool
class FiltersIn(Contract):
    age_min: StrictInt; age_max: StrictInt; gender: GenderFilter; radius: RadiusMode; verified_only: StrictBool
class SettingsOut(Contract):
    notify_frequency: NotifyFrequency; quiet_from: time; quiet_to: time
    show_distance: StrictBool; show_institution: StrictBool
class SettingsIn(SettingsOut): ...
```

#### `GET /filters` / `PUT /filters`

- **Request (PUT):** `{"age_min": 18, "age_max": 22, "gender": "all", "radius": "city", "verified_only": false}`
- **Response:** `200 FiltersOut` — те саме плюс `"age_bounds": [18, 99]`.
- **БД:** `filters`; після PUT — `RebuildFeed(filters_changed)`.
- **Помилки:** `422` — вік поза `age_bounds` або `age_min > age_max`; `km25|km50|km100` без `geo` → `422` з `details: {"reason": "no_geo"}`.

#### `GET /settings` / `PUT /settings`

- **Request (PUT) і Response:**
  ```json
  {"notify_frequency": "instant", "quiet_from": "23:00:00", "quiet_to": "08:00:00", "show_distance": true, "show_institution": true}
  ```
  `quiet_from == quiet_to` — тихих годин немає.
- **БД:** `settings`.

---

### 6.9. S7 — стрічка

```python
class FeedItem(Contract):  kind: Literal["item"] = "item"; card: ProfileCard; can_undo: bool
class FeedEmpty(Contract): kind: Literal["empty"] = "empty"; reason: FeedEmptyReason
                           expand_options: list[RadiusMode]; resets_at: datetime | None
FeedResponse = FeedItem | FeedEmpty   # розрізняє поле kind
class ExpandIn(Contract):  radius: RadiusMode
```

#### `GET /feed/next` — наступна анкета

- **Коли:** «🔍 Дивитися анкети» і після кожної реакції.
- **Response:** `200 FeedResponse`, один з двох варіантів:
  ```json
  {"kind": "item", "card": {"user_id": 37, "name": "Max", "...": "ProfileCard у режимі feed, з common"}, "can_undo": false}
  ```
  ```json
  {"kind": "empty", "reason": "no_candidates", "expand_options": ["region", "country"], "resets_at": null}
  ```
  Порожня стрічка — це `200`, не помилка. `reason`: `no_candidates`, `limit_reached` (з `resets_at`), `profile_hidden`, `profile_incomplete`, `banned`.
- **БД:** читає `profiles`, `filters`, `views`, `likes`, `blocks`, `matches`, `reports`; Redis `feed:batch`, `feed:seen`, `exposure`. Пише `views(viewer, target, action = shown)` **до** відповіді.
- **Логіка:** жорсткі фільтри → скоринг → пачка → видача (S7 у Додатку).

#### `POST /feed/expand` — розширити пошук

- **Коли:** кнопка «Шукати в області» чи «по країні» на порожній стрічці.
- **Request:** `ExpandIn` — `{"radius": "region"}`; значення з `expand_options`.
- **Response:** `200 FeedResponse` — перша анкета з новим радіусом.
- **БД:** `filters.radius`, перебудова `feed:batch`.
- **Помилки:** `422` — радіуса немає в `expand_options`.

---

### 6.10. S8 — реакції

```python
class MessageMedia(Contract): kind: MessageMediaKind; file_id: StrictStr; duration_s: StrictInt  # ≤ 30
class ReactionIn(Contract):
    target_id: StrictInt              # user_id з картки, не tg_id
    type: ReactionType                # like | like_msg | skip
    message: StrictStr | None = None  # ≤ 300
    media: MessageMedia | None = None # для like_msg треба message або media
class ReactionOut(Contract): match: MatchResult | None; limits: Limits
```

#### `POST /reactions` — лайк, лайк з повідомленням, пропуск

- **Коли:** ❤️, 💌 (+ текст, голосове або кружок), 👎 під карткою.
- **Request:**
  ```json
  {"target_id": 37, "type": "like"}
  ```
  ```json
  {"target_id": 37, "type": "like_msg", "message": "Привіт! Теж граєш у CS2?"}
  ```
  ```json
  {"target_id": 37, "type": "like_msg", "media": {"kind": "voice", "file_id": "AwACAgIAAxk...", "duration_s": 12}}
  ```
- **Response:** `200 ReactionOut`
  ```json
  {"match": null, "limits": {"reactions_left": 99, "messages_left": 20, "resets_at": "2026-11-09T22:00:00Z"}}
  ```
  Якщо `target` уже лайкнув тебе, `match` — `MatchResult` (картка, `partner_username`, `partner_tg_id`, `icebreaker`).
- **БД:** `views.action`, `views.acted_at`; `likes` (`pending` або `matched`); `matches`; `notification_outbox` (`likes` або `match` для другої сторони); Redis `lim:react`, `lim:msg`, `rate:react`, `feed:undo`.
- **Логіка:** перевірити, що анкету показували; ліміти; ритм; фільтр тексту; взаємність (S8 у Додатку).
- **Помилки:** `429 limit_reached` (`details` = `Limits`), `429 rate_limited`, `400 content_blocked`, `400 media_forbidden` (медіа в пулі minor), `403 captcha_required`, `409 conflict` (анкету не показували або реакція вже була).

#### `POST /reactions/undo` — «↩️ Повернути»

- **Request:** —
- **Response:** `200 FeedItem` — пропущена анкета, `can_undo = false`.
- **БД:** Redis `feed:undo:{user_id}` (живе 60 с), `views.action = undo`.
- **Помилки:** `409 undo_unavailable`.

#### `GET /limits`

- **Response:** `200 Limits` — `{"reactions_left": 80, "messages_left": 18, "resets_at": "2026-11-09T22:00:00Z"}`.

---

### 6.11. S9 — вхідні лайки, взаємність, контакти

```python
class CountOut(Contract):     count: int
class IncomingLike(Contract): kind: Literal["like"] = "like"; like_id: int; card: ProfileCard
                              message: str | None; media: MessageMedia | None
class NoIncoming(Contract):   kind: Literal["none"] = "none"
class RespondIn(Contract):    decision: LikeDecision   # accept | decline
class RespondOut(Contract):   match: MatchResult | None
class ContactOut(Contract):   match_id: int; partner: ProfileCardShort; partner_username: str | None
                              partner_tg_id: int; matched_at: datetime
```

#### `GET /likes/incoming/count`

- **Response:** `200 {"count": 3}` — кількість `pending`-лайків до тебе від видимих авторів.

#### `GET /likes/incoming/next` — наступний вхідний лайк

- **Коли:** «💌 Хто мене лайкнув» і перед стрічкою: вхідні показуються першими.
- **Response:**
  ```json
  {"kind": "like", "like_id": 812, "card": {"...": "ProfileCard у режимі incoming"}, "message": "Привіт!", "media": null}
  ```
  або `{"kind": "none"}`. Найстаріший лайк першим.

#### `POST /likes/{like_id}/respond` — відповісти на лайк

- **Request:** `{"decision": "accept"}` або `{"decision": "decline"}`
- **Response:** `200 RespondOut` — при `accept` `{"match": MatchResult}`, при `decline` `{"match": null}`.
- **БД:** `accept` → `INSERT matches` (`user_a_id < user_b_id`), обидва лайки `matched`, outbox `match` для автора. `decline` → лайк `declined`, автору нічого.
- **Помилки:** `404 not_found` — лайк не тобі; `409 conflict` — уже відповів.

#### `GET /matches/{match_id}` — деталі взаємності

- **Коли:** користувач відкрив сповіщення про взаємність.
- **Response:** `200 MatchResult` — картка партнера, його поточний `tg_username` як `partner_username`, `partner_tg_id`, `icebreaker`.
- **Помилки:** `404 not_found` — ти не учасник.

#### `GET /contacts?cursor=&limit=20` — список взаємностей

- **Response:** `200 Page[ContactOut]`
  ```json
  {"items": [{"match_id": 9, "partner": {"user_id": 37, "name": "Max", "age": 18, "city_name": "Вінниця"}, "partner_username": "max", "partner_tg_id": 5551, "matched_at": "2026-11-08T17:00:00Z"}], "next_cursor": null}
  ```
- **БД:** `matches` без `removed_by_id`, нові першими; курсор — закодована пара `(created_at, id)`.

#### `DELETE /contacts/{match_id}`

- **Response:** `204`. **БД:** `matches.removed_by_id = user_id`; контакт зникає в обох. **Помилки:** `404`.

---

### 6.12. S10, S10b — скарги, блоки, адмін-розділ

```python
class ReportIn(Contract):  target_id: StrictInt; reason: ReportReason; text: StrictStr | None = None; context: ReportContext
class BlockIn(Contract):   target_id: StrictInt
class AdminActionIn(Contract): kind: AdminQueueKind; item_id: StrictInt; action: AdminAction; reason: StrictStr | None = None
# відповіді: AdminQueueItem, AdminUserOut, MetricsOut — svoi_contracts.api.admin
```

#### `POST /reports` — скарга

- **Request:** `{"target_id": 37, "reason": "spam", "text": null, "context": "feed"}`; для `reason = other` потрібен `text`; `context = system` від бота заборонений (модель уже не пропустить).
- **Response:** `204`.
- **БД:** `INSERT reports`; `views.action = report`; автоприховування `profiles.hidden_by_moderation` за сумою ваг або одразу при `underage`.
- **Помилки:** `409 conflict` — уже скаржився на цю людину; `400 content_blocked` — у тексті.

#### `POST /blocks` / `DELETE /blocks/{target_id}`

- **Request (POST):** `{"target_id": 37}`. **Response:** `204`.
- **БД:** `INSERT blocks`, матч між ними отримує `removed_by_id`, `views.action = block`. `DELETE` видаляє рядок блоку, матч не відновлюється.
- **Помилки (DELETE):** `404 not_found`.

Усі `/admin/*` — тільки для `X-Tg-User-Id` з `ADMIN_TG_IDS`, інакше `403 forbidden`. Перевіряє `deps.admin_user`.

#### `GET /admin/queue?kind=photos` — наступний елемент черги

- **Response:** `200 AdminQueueItem` або `200 null`, коли черга порожня. Найстаріший елемент.
  ```json
  {"item_id": 55, "kind": "photos", "target_user_id": 37, "target_tg_id": 5551, "target_card": {"...": "ProfileCard admin"},
   "reports": [], "media": {"id": 55, "kind": "photo", "file_id": "AgAC...", "moderation_status": "pending"},
   "verification_file_id": null, "verification_gesture": null, "custom_interest_title": null, "flagged_text": null,
   "created_at": "2026-11-09T10:00:00Z"}
  ```
  `item_id` — id скарги, медіа, верифікації, тега або промпту залежно від `kind`.

#### `GET /admin/queue/stats`

- **Response:** `200 {"reports": 2, "photos": 5, "verifications": 0, "custom_tags": 1, "texts": 0}` — завжди всі п'ять ключів.

#### `POST /admin/actions` — рішення модератора

- **Request:** `{"kind": "photos", "item_id": 55, "action": "delete_media", "reason": null}`
- **Response:** `204`.
- **БД:** зміни за дією (S10 у Додатку) + `INSERT mod_actions` + outbox `moderation` користувачу.
- **Помилки:** `404 not_found`; `409 conflict` — елемент уже оброблено.

#### `GET /admin/users/{tg_id}` — команда `/user <tg_id>`

- `{tg_id}` — людина, яку шукає адмін; адмін — у заголовку.
- **Response:** `200 AdminUserOut` — `user_id`, `tg_id`, `status`, `shadow_banned`, `banned_until`, `risk_score`, `card`, `reports_total`, `mod_actions` (рядки історії).
- **Помилки:** `404 not_found`.

#### `GET /admin/metrics?days=7` — команда `/metrics`

- **Response:** `200 MetricsOut` — старти, завершені онбординги, лайки, взаємності, retention D1/D7, скарги на 1000 показів.
- **Помилки:** `422` — `days` поза 1..90.

---

### 6.13. S11 — капча

```python
class CaptchaChallenge(Contract): challenge_id: str; target_emoji: str; options: list[str]
class CaptchaAnswerIn(Contract):  challenge_id: StrictStr; answer: StrictStr
```

#### `POST /users/me/captcha` — видати капчу

- **Коли:** `UserState.captcha_required = true` або реакція повернула `captcha_required`.
- **Response:** `200 {"challenge_id": "c1f9...", "target_emoji": "🐱", "options": ["🐶", "🐱", "🦊", "🐻", "🐼", "🐸"]}`
- **БД:** Redis `captcha:{challenge_id}` з TTL 300 с.
- **Помилки:** `409 conflict` — капча не потрібна.

#### `POST /users/me/captcha/verify` — відповідь

- **Request:** `{"challenge_id": "c1f9...", "answer": "🐱"}`
- **Response:** `200 UserState`: правильно → `captcha_required = false`; неправильно → `captcha_required = true`, бот попросить нову.
- **БД:** видалити ключ капчі; правильно → `users.captcha_passed_at`, `risk_score − 30`; неправильно → лічильник помилок +1.
- **Помилки:** `404 not_found` — капча протухла або не існує.

---

### 6.14. S12 — верифікація

```python
class GestureOut(Contract):       verification_id: int; gesture: GestureCode
class VerificationIn(Contract):   verification_id: StrictInt; video_note_file_id: StrictStr
class VerificationOut(Contract):  status: ModerationStatus | None   # None — не подавав
```

#### `POST /verification/start` — видати жест

- **Response:** `200 {"verification_id": 4, "gesture": "peace"}`.
- **БД:** `INSERT verifications` (`pending`, без файлу).
- **Помилки:** `409 conflict`, `details.reason`: `already_verified` | `pending` | `no_photo` (немає схваленого фото для порівняння).

#### `POST /verification/submit` — надіслати кружок

- **Request:** `{"verification_id": 4, "video_note_file_id": "DQACAgIAAxk..."}`
- **Response:** `200 {"status": "pending"}`.
- **БД:** `verifications.video_note_file_id`; запис з'являється в черзі `verifications`.
- **Помилки:** `404 not_found` — не твій запис; `409 conflict` — файл уже надіслано.

#### `GET /verification/status`

- **Response:** `200 {"status": "approved"}` (`pending`, `rejected` або `null` — не подавав).

---

### 6.15. S13 — внутрішні (викликає `bot-worker`)

Без `X-Tg-User-Id`, тільки з токеном.

#### `POST /internal/users/{tg_id}/bot-blocked`

- **Коли:** Telegram відповів 403 на сповіщення: людина заблокувала бота.
- **Response:** `204`.
- **БД:** `users.bot_blocked = true`; `pending`-outbox цього користувача → `cancelled`.
- **Помилки:** `404 not_found`.

#### `POST /internal/notifications/{dedupe_key}/sent`

- **Коли:** `bot-worker` успішно доставив сповіщення.
- **Response:** `204`.
- **БД:** `notification_outbox.status = sent` за `dedupe_key`. Ключ приходить URL-кодованим (`match%3A9%3A37`), FastAPI розкодує сам.
- **Помилки:** `404 not_found`.

---

### 6.16. S14 — рефералка

#### `GET /referral`

- **Response:** `200 {"code": "AB12CD34", "invited_count": 2, "bonus_per_invite": 20}`.
- **БД:** `users.referral_code`; `invited_count` — запрошені (`referred_by_id = ти`) зі статусом `active`. Посилання `https://t.me/<bot>?start=r_<code>` будує бот.

---

## 7. Робочий цикл і тести

### 7.1. Цикл задачі

1. Задача Linear → гілка `be/SVO-<n>-<slug>`.
2. Коміти маленькі, англійською: `feat(users): add onboarding skip`. Формат — розділ 13 `tech.md`.
3. PR: заголовок `SVO-<n> <domain>: <summary>`, тіло — що робить, які ендпоінти й моделі зачіпає (версія ядра), чим покрито тестами.
4. CI зелений → рев'ю тимліда → squash-merge → автодеплой на VPS.
5. Перевір ендпоінти через бота на VPS, коли фронтенд-частина слайса змерджена.

### 7.2. Тести на слайс

- **З критеріїв приймання**, не з коду: спершу перенеси кожен критерій з Додатку в назву тесту, потім пиши реалізацію.
- **Контрактні:** відповідь кожного ендпоінта валідується моделлю (`assert_contract(response, UserState)` у `tests/conftest.py`), кожен джоб — payload-моделлю з `jobs.py`. Якщо відповідь не проходить модель, бот на ній впаде.
- **Шлях помилки:** кожен код з колонки «Помилки» — окремий тест зі статусом і `code`.
- **Ідемпотентність:** кожен джоб і cron двічі з тим самим payload → рівно один ефект.
- **Property-based (hypothesis)** на всьому з `rules.py`.
- Справжній Postgres з PostGIS, транзакція на тест з rollback; час через `core/time.now()`.

### 7.3. Як перевірити ендпоінт проти бота

Бот ходить в API через `apps/bot/svoi_bot/api_client/http.py`; список усіх ендпоінтів з методом, шляхом, моделлю тіла і відповіді — `apps/bot/svoi_bot/api_client/base.py` (`_OPS`). Бот без бекенду працює на `FakeApiClient` (`fake.py`): якщо сумніваєшся, як має поводитись ендпоінт, подивись, що робить фейк, і спитай тимліда, якщо він розходиться з цим файлом.

---

## Додаток. Бізнес-правила і критерії приймання слайсів

Формат: домени · ендпоінти · правила · критерії приймання · тести. Константи — з `svoi_contracts.constants` (у тексті без префікса).

### S1-BE — старт, мова, згода, вік, ім'я, стать (еталон, MVP)

**Домени.** `users`, `profiles`.

**Ендпоінти.** `POST /users/start`, `GET /users/me`, `PUT /users/me/lang`, `POST /users/me/consent`, `PUT /profile/age`, `PUT /profile/name`, `PUT /profile/gender`, `POST /onboarding/skip`.

**Правила.**

- Один `tg_id` — одна анкета: `users.tg_id` унікальний, `profiles.user_id` — первинний ключ; дублікатів не буває за побудовою.
- `start`: створює `users` і порожній `profiles`, якщо `tg_id` новий; генерує унікальний `referral_code` (8 символів base32). На кожному виклику оновлює `tg_username`, `tg_first_name`, скидає `bot_blocked = false`. Мова за замовчуванням з `tg_language_code`: `uk` → uk, `ru` → ru, інше → uk.
- `referral_code` у `StartIn` записується в `referred_by_id` тільки для нового користувача, якщо код існує і не належить йому самому.
- Порядок кроків — порядок `OnboardingStep`. Успішний `PUT` поточного кроку переводить на наступний. `PUT` пройденого кроку не змінює крок. `PUT` майбутнього кроку → `conflict`.
- `consent`: ставить `consent_at`; тільки з кроку `consent`.
- Вік:
  - `age < AGE_MIN` → `age_rejected_at = now`, `age_too_young`;
  - `age_rejected_at` молодше `AGE_REJECT_COOLDOWN_DAYS` → `age_locked` на будь-яке значення;
  - `age > AGE_MAX` → `validation_error`;
  - перше введення: `age_set_at = now`, `pool` за `ADULT_AGE`;
  - редагування: дозволене один раз (`age_edits = 0`) і тільки протягом `AGE_EDIT_WINDOW_HOURS` від `age_set_at`; зміна, яка переводить з `minor` в `adult`, завжди `age_locked`; інакше `age_locked`.
- Ім'я: довжина `NAME_LEN`, тільки літери Unicode, пробіл, дефіс, апостроф; без цифр; проходить фільтр `safety.check_text(field=name)`.
- `skip`: тільки для `clarify`, `institution`, `height`, `prompts`, `media` і тільки якщо крок поточний; інакше `conflict`.
- `UserState.needs_username = tg_username is None`; `captcha_required` — з S11 (до S11b завжди `false`); `is_admin` — `tg_id in ADMIN_TG_IDS`; `counters.incoming_likes` — з S9 (до S9 — 0).

**Критерії приймання.** Повторний `start` не створює дубль; вік 15 → `age_too_young`, потім вік 18 → `age_locked`; вік 17 після онбордингу не можна змінити на 18; `PUT /profile/name` до кроку `name` → `conflict`; ім'я з посиланням → `content_blocked`.

**Тести.** Контракт `UserState` на кожному ендпоінті; повний прохід кроків; таблиця переходів (параметризовано: поточний крок × ендпоінт → новий крок або `conflict`). Property: для будь-якого `age` у [0, 150] і будь-якої історії введень пул завжди відповідає `ck_profiles_pool`, а перехід minor → adult через редагування неможливий.

---

### S2-BE — місто і геолокація (MVP)

**Домени.** `catalog`, `profiles`.

**Ендпоінти.** `GET /catalog/cities/search`, `GET /catalog/cities/by-location`, `PUT /profile/city`.

**Правила.**

- Пошук: нормалізація запиту (нижній регістр, `ё→е`, апострофи `ʼ'’` уніфіковано, обрізка пробілів); `similarity()` з `pg_trgm` по `name_uk`, `name_ru`, `name_en`; сортування за схожістю, потім за населенням; поріг схожості 0.3; назва локалізується мовою користувача.
- `by-location`: найближче місто в радіусі 30 км (`ST_DWithin` + сортування за відстанню, PostGIS-індекс); немає → `not_found`.
- `PUT /profile/city`: `lat`/`lon` округлюються до `GEO_ROUND_DECIMALS` і пишуться в `geo`; координати далі за 50 км від міста → `validation_error`; без координат `geo = NULL` (старі координати іншого міста видаляються).
- Зміна міста → `RebuildFeed(reason=profile_changed)`.

**Критерії приймання.** «Могилів», «могилев», «Mohyliv» знаходять Могилів-Подільський; координати в БД мають не більше 2 знаків після коми; без координат `geo` порожнє.

**Тести.** Контракт `CityOut`; пошук з опечатками на сиді; `by-location` біля і далеко від міст. Property: для будь-яких координат округлення відхиляється від оригіналу не більше ніж на 0.005° за кожною віссю.

---

### S3-BE — цілі та інтереси (MVP)

**Домени.** `catalog`, `profiles`.

**Ендпоінти.** `GET /catalog/goals`, `PUT /profile/goals`, `GET /catalog/interest-categories`, `GET /catalog/interests`, `PUT /profile/interests`, `POST /catalog/interests/custom`.

**Правила.**

- Цілі: заголовки й емодзі для `GoalCode` — словник у `catalog/rules.py` (uk, ru, en). Кількість `GOALS_COUNT`, без дублікатів.
- Категорії: усі, крім прихованої `other`, за `position`.
- Інтереси: тільки `approved`. `PUT /profile/interests` — повна заміна набору; кількість `INTERESTS_COUNT`; кожен id існує і `approved`. Нотатки (`note_key`) збережених інтересів, які лишились у наборі, не губляться.
- Свій тег: довжина `CUSTOM_INTEREST_LEN`; `safety.check_text(field=custom_interest)`; пошук існуючого `approved` тега зі `similarity ≥ 0.6` мовою користувача → `matched`; інакше створити `Interest(is_custom=True, moderation_status=pending, category=other, created_by_id=user)` з однаковою назвою в усіх трьох мовах → `pending=True`. Схвалення модератором додає тег в анкету автора (S10).
- Після змін — перерахунок `completeness`, `snapshot_hash`, `RebuildFeed(reason=profile_changed)`.

**Критерії приймання.** 2 або 16 інтересів → `validation_error`; повторне збереження зберігає нотатки; «шахи» знаходить існуючий тег «Шахи»; новий тег не з'являється в каталозі до схвалення.

**Тести.** Контракт на кожному ендпоінті; заміна набору зі збереженням нотаток; кастомний тег у двох гілках; `content_blocked` для тега з посиланням.

---

### S4-BE — уточнення, заклад, зріст, промпти, медіа, завершення (MVP)

**Домени.** `profiles`, `catalog`, `moderation` (модерація фото).

**Ендпоінти.** `GET /profile/clarifications`, `PUT /profile/interests/{id}/note`, `GET /catalog/institutions/search`, `PUT /profile/institution`, `PUT /profile/height`, `GET /catalog/prompts`, `PUT /profile/prompts`, `POST /profile/media`, `DELETE /profile/media/{id}`, `PUT /profile/media/order`, `POST /onboarding/complete`. Джоб `api.moderate_photo`.

**Правила.**

- Уточнення: інтереси користувача з рядком у `clarifications` і без `note_key`, за `priority`, не більше `CLARIFICATIONS_MAX`. `option_key` має бути в `options`, інакше `validation_error`. Нотатка в картці — локалізований `title` варіанта.
- Заклади: тільки в місті користувача; порожній `q` → за кількістю анкет з цим закладом, потім за назвою; з `q` — trigram.
- Зріст: `HEIGHT_CM` або `None`.
- Промпти: до `PROMPTS_MAX`, текст до `PROMPT_TEXT_MAX`, повна заміна; `safety.check_text(field=prompt)` (посилання, @, телефон, стоп-слова → `content_blocked`). Ознаки віку < 18 у пулі adult → правило з розділу S11 (збереження з `pending`, приховування, системна скарга).
- Медіа: `MEDIA_MAX`, інакше `media_limit`; `position` — наступна вільна; статус `pending`. Фото → `ModeratePhoto`. Відео → одразу в ручну чергу `photos` (без NSFW-моделі). `DELETE` ущільнює позиції. `order` — перестановка рівно всіх id користувача, інакше `validation_error`.
- `api.moderate_photo`: пропуск, якщо статус не `pending` або `nsfw_score` уже є (ідемпотентність). Завантаження через `TelegramFilesClient` → `phash` → `nsfw_score`. `score ≥ NSFW_REJECT` → `rejected` + outbox `moderation(media_rejected)`; `score < NSFW_REVIEW` і немає дубліката → `approved`; інакше лишається `pending` і з'являється в черзі `photos`. Дублікат `phash` (відстань ≤ `PHASH_DUP_DISTANCE`) з медіа іншого користувача → `pending` + ризик +20 (S11).
- `complete`: перевірка обов'язкових полів (`age`, `name`, `gender`, `city_id`, ≥1 мета, ≥3 інтереси), інакше `profile_incomplete` з `details.missing`. Успіх: `status = active`, `onboarding_step = done`; `filters`: `age_min/max` = вік ± `DEFAULT_AGE_RANGE_DELTA`, обрізані межами пулу (minor 16–17, adult 18–99), `gender = all`, `radius = city`; `settings` з дефолтами; бонус рефералки (S14); `RebuildFeed(reason=profile_changed)`; час онбордингу для ризику (S11).

**Критерії приймання.** Уточнення не повертає вже відповідені; 4-те медіа → `media_limit`; фото з балом 0.9 відхилене, 0.6 — у ручній черзі, 0.2 — схвалене; `complete` без інтересів → `profile_incomplete` з `missing = ["interests"]`; фільтр віку для 17-річного — 16–17.

**Тести.** Контракт на кожному ендпоінті. `moderate_photo`: **ідемпотентність** (двічі → один виклик класифікатора, один outbox); шлях помилки (фейк `TelegramFilesClient` 500 → ретрай, статус лишається `pending`; таймаут); контракт payload `ModeratePhoto`. Property: дефолтний діапазон віку для будь-якого віку в [16, 99] лежить у межах пулу і містить сам вік.

---

### S5-BE — картка, «Моя анкета», приховати, видалити, авто-рік (MVP)

**Домени.** `profiles`, `users`.

**Ендпоінти.** `GET /profile/me/card`, `POST /profile/reset`, `POST /profile/hide`, `POST /profile/unhide`, `DELETE /users/me`. Cron `api.age_tick`.

**Правила.**

- Центральна функція `profiles.service.build_card(viewer_id, target_id, mode) -> ProfileCard`, яку використовують S7, S9, S10. Правила:
  - чужа картка: тільки `approved` медіа і промпти; своя (`own`) і `admin`: усі з `moderation_status`;
  - `gender = None`, якщо `hidden`;
  - `distance`: тільки якщо в обох є `geo` і в цілі `show_distance = true`; корзина за `DISTANCE_BUCKETS_KM`, однакове місто → `same_city`; понад 100 км → `None`; у пулі minor — тільки `same_city` або `None`;
  - `institution_name = None`, якщо `show_institution = false`;
  - `interests`: спільні з глядачем першими, `common = true`;
  - `common` (тільки `feed`, `incoming`): назви спільних інтересів, `same_institution`, `match_percent` з S7 (до S7c — `None` для блоку);
  - `completeness` тільки для `own`.
- `completeness`: обов'язкові поля 40, ≥1 схвалене фото 25, ≥1 промпт 15, заклад 10, зріст або хоча б одна нотатка 10.
- `reset`: `status = onboarding`, `onboarding_step = age`; вік не скидається (правило `age_locked` зберігається); лайки, контакти, покази лишаються.
- `hide`: `status = hidden`; `unhide`: тільки з `hidden` → `active`.
- `DELETE /users/me`: видалити всі рядки користувача (каскад); якщо `status = banned` — лишити `users` з `tg_id` і `status = banned`, решту видалити.
- `api.age_tick`: для профілів, у яких сьогодні річниця `age_set_at` і `age_incremented_on != today`: `age += 1`, `age_incremented_on = today`, перерахунок `pool` (17 → 18 переводить у adult і переставляє фільтр віку в межі adult).

**Критерії приймання.** Чужа картка не містить pending-медіа; картка 17-річного не показує відстань в іншому місті; `age_tick` двічі за день додає рік один раз; видалення забаненого лишає бан.

**Тести.** Контракт `ProfileCard` у всіх режимах; **ідемпотентність** `age_tick`. Property: для будь-якої пари профілів `build_card` не повертає неапрувлені медіа в чужому режимі, і `distance` у пулі minor завжди `same_city` або `None`.

---

### S6-BE — фільтри і налаштування (MVP; радіус — 1.1)

**Домен.** `prefs`.

**Ендпоінти.** `GET/PUT /filters`, `GET/PUT /settings`.

**Правила.** `age_bounds` за пулом; `age_min ≤ age_max` у межах, інакше `validation_error`; радіус `km25|km50|km100` без `geo` → `validation_error` з `details: {"reason": "no_geo"}`; тихі години: `quiet_from == quiet_to` означає «без тихих годин». Зміна фільтрів → `RebuildFeed(reason=filters_changed)`.

**Тести.** Контракт; межі для обох пулів; `no_geo`. Property: для будь-яких вхідних значень збережений фільтр або відхилений, або лежить у межах пулу.

---

### S7-BE — стрічка і алгоритм підбору (MVP; радіус — S7b, відсоток — S7c)

**Домен.** `matching`.

**Ендпоінти.** `GET /feed/next`, `POST /feed/expand`. Джоб `api.rebuild_feed`.

#### Етап 1. Жорсткі фільтри (SQL, `matching/repo.py`)

Кандидат `t` для глядача `v` проходить, якщо всі умови істинні:

1. `t.pool = v.pool` — **у SQL обов'язково**, не тільки в Python;
2. `t.user_id != v.user_id`; `t.status = active`; `t.shadow_banned = false`; `t.hidden_by_moderation = false`; `t.bot_blocked = false`; `t.last_active_at > now − INACTIVE_CUTOFF_DAYS`;
3. немає блоку ні в один бік;
4. немає показу `views(v, t)` з дією, що виключає (правила повторів нижче);
5. немає лайка `v → t` у будь-якому статусі; немає `pending`-лайка `t → v` (такі йдуть у вхідні S9); немає `declined`-лайка `t → v` (відхилений автор більше не показується тому, хто відхилив);
6. немає матчу між `v` і `t`;
7. немає скарги `v` на `t`;
8. взаємні фільтри: `t.age ∈ [v.age_min, v.age_max]` і `v.age ∈ [t.age_min, t.age_max]`; стать — фільтр `v` приймає стать `t` і фільтр `t` приймає стать `v` (стать `hidden` проходить тільки фільтр `all`); `v.verified_only → t.verified`;
9. географія за `v.radius`: `city` — `t.city_id = v.city_id`; `km25/km50/km100` — `ST_DWithin(t.geo, v.geo, R)` (S7b); `region` — місто `t` в області міста `v`; `country` — та сама країна; `any_online` — без обмеження, але тільки кандидати з метою `gaming` або `chat`, якщо такі цілі є у `v`.

Умови 3–7 — через `NOT EXISTS` у SQL; перед запитом кандидати додатково відсіваються за `feed:seen:{v}` у Redis. Вибірка: до 500 кандидатів, сортування за `last_active_at desc`.

#### Етап 2. Скоринг (чиста функція `matching/rules.py: score(v, t, ctx) -> ScoreBreakdown`)

Базові фактори, кожен у [0, 1]:

- **interests**: `Jw = Σidf(спільні) / Σidf(об'єднання)`; `C = |категорії обох без спільного тега| / |об'єднання категорій|`; `interests = Jw + CATEGORY_PARTIAL_MATCH · C · (1 − Jw)`.
- **geo**: обидва з `geo` і радіус у км → `max(0, 1 − d / R)`; інакше те саме місто 1.0, та сама область 0.5, інше 0.2.
- **goals**: `|спільні цілі| / |об'єднання|`.
- **institution**: той самий заклад 1.0; обидва мають заклад одного `type` — `SAME_INSTITUTION_TYPE_SCORE`; інакше 0.
- **activity**: за `ACTIVITY_SCORE` за годинами з `last_active_at`, далі 0.
- **age**: `max(0, 1 − |Δвік| / AGE_SCORE_SPAN_YEARS)`.
- **quality**: (`0.4` якщо є схвалене фото + `0.3` якщо є промпт + `0.3` якщо `verified`) × (`0.5`, якщо є відкриті скарги, інакше 1).

Ваги `SCORE_WEIGHTS`. Якщо в обох є мета `gaming` і `v.radius = any_online`, вага geo = `GEO_WEIGHT_ONLINE_GOAL`; після заміни ваги нормалізуються до суми 1.

`base = Σ вага · фактор`. `match_percent = round(100 · base)` (S7c).

Поправки (тільки для ранжування, не для відсотка):

- новачок (`t.created_at > now − NEWBIE_BOOST_HOURS`) → `+NEWBIE_BOOST`;
- перекспонування: `−min(0.2, 0.002 · exposure_today(t))` (лічильник Redis `exposure:{t}:{date}`, +1 на кожен показ);
- відкриті скарги: `−0.1` за кожну, максимум `−0.3`;
- рефералка (S14): запрошений і той, хто запросив, протягом 48 год → `+1.0`;
- підсумок обрізається до [0, 1] (рефералка — до 2.0, щоб бути першою).

#### Етап 3. Пачка і видача

- `rebuild_batch(v, rng)`: кандидати → скоринг → сортування → три кошики: верхні 30%, середні 40%, нижні 30%; набір `FEED_BATCH_SIZE` за `FEED_MIX` (70/20/10) з перемішуванням усередині кошика; `rng` детермінований для тестів. Пачка — у `feed:batch:{v}`, без уже показаних і без тих, що вже в пачці.
- `GET /feed/next`:
  1. профіль `hidden` → `FeedEmpty(profile_hidden)`; онбординг → `profile_incomplete`; ліміт реакцій вичерпано → `limit_reached` з `resets_at`;
  2. спершу один раз повернути «показаний без реакції» (`views.action = shown`, `acted_at IS NULL`, `reshown = false`, `shown_at < now − 30 хв`) → `reshown = true`;
  3. далі — з пачки; у пачці ≤ `FEED_REFILL_AT` → `RebuildFeed(reason=refill)`; пачка порожня → синхронний `rebuild_batch`;
  4. перед відповіддю — запис `views(v, t, shown)`, `target_snapshot_hash`, `feed:seen`, `exposure`;
  5. кандидатів немає → `FeedEmpty(no_candidates, expand_options)`.
- `expand_options`: ширші за поточний `radius` з набору `[km50, region, country]` (км — тільки якщо в `v` є `geo`) + `any_online`, якщо в `v` є мета `gaming`.
- `POST /feed/expand`: `radius` має бути серед `expand_options`, інакше `validation_error`; зберегти у `filters`, перебудувати пачку, повернути `FeedResponse`.

#### Правила повторів

| Дія у `views` | Повтор |
| --- | --- |
| `like`, `like_msg` | ніколи (виключено також лайком) |
| `report`, `block` | ніколи, в обидва боки для блоку |
| `skip` | через `SKIP_REPEAT_DAYS`, тільки якщо `profiles.snapshot_hash` цілі змінився відносно `views.target_snapshot_hash` і нових кандидатів немає |
| `undo` | картка повертається одразу (S8b), реакція дозволена знову |
| `shown`, без реакції | один раз на початку наступної сесії (`reshown`) |

`api.rebuild_feed`: перебудова пачки; ідемпотентний за побудовою (перезаписує список).

**Критерії приймання.** Кандидат з іншого пулу не повертається ніколи; заблокований — ніколи; один і той самий кандидат не повертається двічі як новий; відхилений автор лайка не з'являється в стрічці того, хто відхилив; при порожній стрічці повертаються правильні `expand_options`.

**Тести.** Контракт `FeedResponse`. SQL-тести жорстких фільтрів (параметризовано по кожній умові). **Ідемпотентність** `rebuild_feed`. Property (hypothesis) на `rules.py`: `base ∈ [0, 1]`; `interests(a, b) == interests(b, a)`; додавання спільного інтересу не зменшує `interests`; ваги після нормалізації дають суму 1; мікс пачки ніколи не перевищує `FEED_BATCH_SIZE` і не містить дублікатів. Property на рівні сервісу (з генерацією профілів у тестовій БД, обмежена кількість прикладів): жоден повернутий кандидат не порушує жодної умови етапу 1.

---

### S8-BE — реакції і ліміти (MVP; «Повернути» — S8b)

**Домени.** `reactions`, `safety`.

**Ендпоінти.** `POST /reactions`, `POST /reactions/undo`, `GET /limits`.

**Правила.**

- Реакція дозволена тільки на ціль, яку показали цьому користувачу (`views` з `action ∈ {shown, undo}`), інакше `conflict`; повторна реакція → `conflict`.
- Ліміти: кожна реакція (включно зі `skip`) +1 до `lim:react`; `like_msg` ще +1 до `lim:msg`. Межа: `REACTIONS_PER_DAY + Σ reaction_bonuses за сьогодні`, `MESSAGES_PER_DAY`. Доба — за `LIMITS_RESET_TZ`. Перевищення → `limit_reached` з `Limits`.
- Ритм: таймстемп у `rate:react:{v}`; якщо протягом `RAPID_REACTION_STREAK_S` усі інтервали ≤ `RAPID_REACTION_INTERVAL_S` → ризик +30 (S11b) і `rate_limited`; ризик ≥ `RISK_CAPTCHA_THRESHOLD` без пройденої капчі → `captcha_required`.
- `like`: якщо є `pending`-лайк `t → v` → створити матч (`user_a_id < user_b_id`), обидва лайки `matched`, outbox `match` для `t`, у відповіді `MatchResult` для `v`. Інакше — лайк `pending`, outbox `likes` для `t` (S9/S13).
- `like_msg`: обов'язково `message` або `media`; `safety.check_text(field=like_message)`; пул minor + `media` → `media_forbidden`; `duration_s > LIKE_MEDIA_MAX_SECONDS` → `validation_error`; детектор розсилок (S11a).
- Тіньовий бан автора: лайк записується, але outbox не створюється і лайк не потрапляє у вхідні цілі.
- `skip`: `views.action = skip`; ключ `feed:undo:{v} = t` з TTL `UNDO_WINDOW_SECONDS`.
- `undo` (S8b): ключ є → `views.action = undo`, видалити ключ, повернути `FeedItem` з карткою `t` і `can_undo = false`; ліміт реакцій не повертається; ключа немає → `undo_unavailable`.
- `FeedItem.can_undo = true`, якщо ключ `feed:undo:{v}` існує.

**Критерії приймання.** 101-ша реакція за добу → `limit_reached`; з бонусом +20 — 121-ша; взаємний лайк повертає `match` і створює один outbox для другої сторони; голосове в пулі minor → `media_forbidden`; «Повернути» через 61 с → `undo_unavailable`.

**Тести.** Контракт `ReactionOut`, `Limits`; гонка: два паралельні `like` з обох боків створюють рівно один матч (унікальний індекс + обробка `IntegrityError`); тіньовий бан не створює outbox. Property: для будь-якої послідовності реакцій лічильник ≤ межі, і `reactions_left = межа − використано ≥ 0`.

---

### S9-BE — вхідні лайки, взаємність, контакти, базові сповіщення (MVP; айсбрейкер — S9b)

**Домени.** `likes`, `notifications` (базово).

**Ендпоінти.** `GET /likes/incoming/count`, `GET /likes/incoming/next`, `POST /likes/{id}/respond`, `GET /matches/{id}`, `GET /contacts`, `DELETE /contacts/{id}`, `POST /internal/users/{tg_id}/bot-blocked`, `POST /internal/notifications/{dedupe_key}/sent`. Cron `api.likes_expire`, `api.notify_schedule`.

**Правила.**

- Вхідні: `pending`-лайки до `v` від авторів, які `active`, не `shadow_banned`, не заблоковані, у тому самому пулі; від найстаріших. `count` — та сама вибірка. Картка в режимі `incoming`.
- `respond accept` → матч, обидва лайки `matched`, outbox `match` для автора, `RespondOut.match` для `v`. `decline` → лайк `declined`; автор нічого не отримує. Лайк не до `v` або не `pending` → `not_found` / `conflict`.
- `GET /matches/{id}` — тільки учаснику, `partner` — інша сторона, `partner_username` — поточний `tg_username`.
- Айсбрейкер (S9b): спільний інтерес з найбільшим `idf` → `common_interest`; інакше той самий заклад → `same_institution`; інакше спільна мета → `common_goal`; інакше `None`.
- Контакти: матчі без `removed_by_id`, нові першими, курсор за `(created_at, id)`. `DELETE` → `removed_by_id = v`, зникає в обох.
- `api.likes_expire`: `pending` старші за `LIKE_EXPIRE_DAYS` → `expired`, без сповіщень.
- Outbox (MVP, без батчингу): запис з `scheduled_for = now`, одразу `enqueue` у чергу `bot` і статус `enqueued`, `attempts = 1`. `api.notify_schedule` бере `pending` з `scheduled_for ≤ now` і повторно ставить `enqueued`, старші за `OUTBOX_REENQUEUE_MINUTES` (до `OUTBOX_MAX_ATTEMPTS`, потім `failed`).
- `bot-blocked` → `users.bot_blocked = true`, скасувати `pending`-outbox (`cancelled`). `sent` → `status = sent`.

**Критерії приймання.** Вхідний лайк від тіньово забаненого не видно; accept створює рівно один матч і один outbox; видалений контакт зникає в обох; лайк 15-денної давнини стає `expired`.

**Тести.** Контракт на кожному ендпоінті і payload `NotifyLikes`, `NotifyMatch`. **Ідемпотентність**: `likes_expire` двічі; `notify_schedule` двічі за той самий стан → кожен outbox поставлений один раз; `respond` двічі → другий `conflict`, один матч. Шлях помилки: падіння `enqueue` (Redis недоступний) лишає outbox `pending`, cron підбирає.

---

### S10-BE — скарги, блоки, модерація (MVP)

**Домен.** `moderation`.

**Ендпоінти.** `POST /reports`, `POST /blocks`, `DELETE /blocks/{id}`, `GET /admin/queue`, `GET /admin/queue/stats`, `POST /admin/actions`, `GET /admin/users/{tg_id}`.

**Правила.**

- Скарга: одна на пару `reporter → target` (`conflict`); `context = system` у `ReportIn` → `validation_error`; `other` без тексту → `validation_error`; текст через `safety.check_text(field=report_text)`; `views.action = report`.
- Вага скарги = `report_weight` автора × 1.5, якщо `context = contact` (людина вже спілкувалась і бачила проблему), інакше × 1.
- Автоприховування: сума ваг відкритих скарг різних авторів ≥ `REPORTS_AUTOHIDE` → `hidden_by_moderation = true`. Причина `underage` → приховування одразу.
- Блок: запис `blocks`, матч між ними отримує `removed_by_id`, `views.action = block`. Розблокування видаляє запис (матч не відновлюється).
- Черги (`GET /admin/queue` повертає найстаріший елемент):
  - `reports` — цілі з відкритими скаргами; спершу з `underage`, потім за кількістю скарг; `item_id` — id останньої скарги;
  - `photos` — `media.pending` з балом у [NSFW_REVIEW, NSFW_REJECT), дублікати `phash`, відео;
  - `verifications` — `pending` з `video_note_file_id`;
  - `custom_tags` — кастомні `interests.pending`;
  - `texts` — `profile_prompts.pending`.
- Дії (`POST /admin/actions`), кожна → `mod_actions` + outbox `moderation`:
  - `ok` (reports, texts) — скарги `rejected`, `report_weight` авторів × 0.9 (мінімум 0.3); промпти `approved`; зняти `hidden_by_moderation`, якщо відкритих скарг не лишилось;
  - `delete_media` — у `reports` усі медіа цілі, у `photos` — конкретне; outbox `media_rejected`;
  - `delete_text` — промпти цілі видаляються; outbox `text_removed`;
  - `ban_7d` / `ban_forever` — `status = banned`, `banned_until`, скарги `accepted`, pending-лайки від цілі `expired`; outbox `banned`;
  - `move_to_minor_pool` — `age = 17`, `pool = minor`, `age_edits = 1`, фільтр віку 16–17, матчі з adult `removed_by_id`, pending-лайки з adult `expired`; скарги `accepted`;
  - `approve` / `reject` — для `photos`, `verifications` (S12), `custom_tags` (approve додає тег в анкету автора; outbox `tag_approved`/`tag_rejected`), `texts`.
  - повторна дія над уже закритим елементом → `conflict`.

**Критерії приймання.** Три скарги від різних людей ховають анкету; одна скарга `underage` ховає одразу; перенесення в пул minor розриває всі зв'язки з adult; не-адмін отримує 403.

**Тести.** Контракт усіх моделей; кожна дія (параметризовано) змінює рівно ті записи, що описані; **ідемпотентність**: повторна дія → `conflict`, один outbox. Property: для будь-якого набору скарг з вагами автоприховування настає тоді й лише тоді, коли сума ≥ порогу або є `underage`.

---

### S10b-BE — метрики (MVP)

**Домен.** `metrics`.

**Ендпоінти.** `GET /admin/metrics`.

**Правила.** `deps.current_user` при першому запиті користувача за добу (Europe/Kyiv) робить upsert у `user_activity_days` (публічна функція `metrics.service.touch_day`). Метрики рахуються SQL-запитами за період `[today − days + 1, today]`: `starts` — нові `users`; `onboarding_completed` — з них ті, що мають `onboarding_step = done`; `mutual_rate` — лайки періоду зі статусом `matched` / усі лайки періоду; `d1/d7_retention` — частка нових користувачів з рядком активності на день +1 / +7 (когорта — ті, для кого цей день уже настав); `reports_per_1000_views` — скарги користувачів (без системних) / покази × 1000; `confirmed_reports_rate` — `accepted / (accepted + rejected)`. Ділення на 0 → 0.0.

**Критерії приймання.** Повторні запити користувача за добу дають один рядок активності; метрики на сиді збігаються з ручним підрахунком у тесті.

**Тести.** Контракт `MetricsOut`; ідемпотентність `touch_day`; ділення на 0. Property: усі частки в [0, 1].

---

### S11-BE — безпека: фільтр контенту, ризик, капча, тіньовий бан, вік у тексті

**Домен.** `safety`. **S11a (MVP):** фільтр контенту, вік у тексті, детектор розсилок, тіньовий бан. **S11b (1.1):** ризик-скоринг і капча.

**Ендпоінти.** `POST /users/me/captcha`, `POST /users/me/captcha/verify` (S11b). Публічні функції домену: `check_text(text, field, profile) -> ContentBlockReason | None`, `detect_age_mention(text) -> int | None`, `add_risk(user_id, points, reason)`, `register_message(user_id, recipient_id, text)`.

**Фільтр контенту (`safety/rules.py`, чисті функції).**

- Нормалізація: нижній регістр; гомогліфи латиниця ↔ кирилиця (`a/а`, `e/е`, `o/о`, `p/р`, `c/с`, `x/х`, `i/і`); leet (`0→о`, `3→з`, `4→ч`, `6→б`, `@→а`); видалення повторів і розділювачів усередині слів (`т.е.м.к.и` → `темки`).
- `link`: `http(s)://`, `www.`, `t.me`, `telegram.me`, домени з поширеними TLD (`.com .ua .ru .net .org .io .me .link .xyz`), обфускація пробілами і крапками.
- `mention`: `@` + 4+ символів слова.
- `phone`: 9+ цифр з допустимими `+ - ( ) пробіл`.
- `stopword`: список у `safety/stopwords.py` з варіантами uk/ru: темки, заробіток/заработок, підробіток/подработка, казино, ставки, крипта/крипто, інвестиції під %, пиши в лс/пиши в особисті, onlyfans та інші; тест на кожен варіант.
- Порядок перевірки: link → mention → phone → stopword → age.

**Вік у тексті.** `detect_age_mention`: «мені 17», «мне 17», «17 років/лет/год», «(17)», «17!», «в 9/10/11 класі/классе», «школяр/школярка/школьник/школьница». Повертає вік або 13–17 для шкільних ознак. Для профілю в пулі adult знайдений вік < 18:

- `field = prompt` → зберегти з `pending`, `hidden_by_moderation = true`, системна скарга (`reporter_id = NULL`, `reason = underage`, `context = system`, `text` = фрагмент);
- `field = like_message` → `content_blocked` з `age_mismatch` + системна скарга;
- `field = name` → `content_blocked` з `age_mismatch`.

**Детектор розсилок.** `register_message`: `sha1` нормалізованого тексту → `dup:msg:{sha1}:{date}` (множина отримувачів). ≥ `DUP_MESSAGE_THRESHOLD` різних отримувачів → `shadow_banned = true`, ризик +30.

**Ризик-скоринг (S11b).** Бали: немає `tg_username` +15; немає фото профілю Telegram +15; дуже новий акаунт (`tg_id` > `NEW_ACCOUNT_TG_ID_MIN` з конфігу) +20; онбординг швидше за `FAST_ONBOARDING_SECONDS` +20; спрацювання стоп-слова в будь-якому полі +30; дублікат `phash` +20; підозрілий ритм реакцій +30; `CAPTCHA_FAILS_RISK` помилок капчі поспіль +10. `captcha_required = risk_score ≥ RISK_CAPTCHA_THRESHOLD` і (`captcha_passed_at IS NULL` або ризик зріс після проходження). Пройдена капча знижує `risk_score` на 30 (не нижче 0). Поріг `NEW_ACCOUNT_TG_ID_MIN` — у `config.py` (тимлід), не константа продукту.

**Капча (S11b).** `POST /users/me/captcha`: 6 різних емодзі з фіксованого набору 20, одна — ціль; `captcha:{id}` з TTL `CAPTCHA_TTL_SECONDS`; без `captcha_required` → `conflict`. `verify`: немає ключа → `not_found`; неправильно → видалити ключ, лічильник помилок +1, `UserState` з `captcha_required = true`; правильно → `captcha_passed_at = now`, ризик −30.

**Критерії приймання.** «пиши в т е л е г у @vasya» блокується як `mention`; «t . me/abc» — як `link`; «+38 (067) 123-45-67» — як `phone`; «т3мки» — як `stopword`; промпт «мені 17, шукаю друзів» в adult зберігається на модерацію і ховає анкету; той самий текст 5 різним людям → тіньовий бан.

**Тести.** Таблиця прикладів на кожну причину (позитивні й негативні: «Гітара», «Київ 2026», «люблю @-мистецтво» не блокуються). Property (hypothesis): `check_text` ніколи не падає на довільному Unicode; нормалізація ідемпотентна (`norm(norm(x)) == norm(x)`); вставка посилання в будь-яку позицію будь-якого тексту дає `link`. Контракт `CaptchaChallenge`; капча правильно/неправильно/протухла.

---

### S12-BE — верифікація (1.1)

**Домени.** `verification`, `moderation`.

**Ендпоінти.** `POST /verification/start`, `POST /verification/submit`, `GET /verification/status`.

**Правила.** `start`: `conflict` з `reason` = `already_verified` | `pending` (є `pending` з файлом) | `no_photo` (немає схваленого фото); інакше випадковий `GestureCode`, запис `Verification(pending)` без файлу. `submit`: тільки свій запис без файлу, інакше `not_found`/`conflict`; запис з'являється в черзі `verifications`. `approve` → `users.verified = true`, outbox `verified`; `reject` → outbox `verification_rejected`. Верифікація впливає на `quality` у скорингу і фільтр `verified_only`.

**Тести.** Контракт; усі три `conflict`; повний цикл з дією модератора; повторне `approve` → `conflict`.

---

### S13-BE — розумні сповіщення (1.1)

**Домен.** `notifications`.

**Cron.** `api.notify_schedule`, `api.reminders_scan`, `api.new_people_scan`.

**Правила (`notifications/rules.py`, чисті функції).**

- `next_delivery(now, settings, kind) -> datetime`:
  - `likes`: `instant` → `now`; `hourly` → початок наступної години; `daily` → найближчі `DAILY_DIGEST_HOUR:00` за `settings.tz`;
  - `match`, `moderation`: завжди `now`;
  - будь-який результат у тихих годинах (з переходом через північ) → переноситься на `quiet_to`; `quiet_from == quiet_to` → тихих годин немає.
- Батчинг лайків: один outbox на вікно; `dedupe_key = likes:{user_id}:{window_start_iso}`; новий лайк у тому самому вікні оновлює `payload.count` (upsert), якщо запис ще `pending`.
- Нагадування: `active`, не `bot_blocked`, не активний 3 дні → `day3`; 7 днів → `day7`; одне кожного виду на період неактивності (`dedupe_key` з датою останньої активності); після `day7` — нічого.
- Дайджест нових людей: щодня; для активних користувачів рахує нові `active` анкети за 24 год у тому самому місті й пулі зі спільним інтересом; інтерес з найбільшою кількістю; `count ≥ NEW_PEOPLE_MIN`; не більше `NEW_PEOPLE_DIGEST_PER_DAY`.
- Усі записи outbox проходять `next_delivery` і тихі години.

**Критерії приймання.** Лайк о 23:30 при тихих годинах 23:00–08:00 і частоті `instant` доставляється о 08:00; 5 лайків за годину при `hourly` дають одне сповіщення з `count = 5`; нагадування `day3` не повторюється.

**Тести.** **Ідемпотентність** кожного cron (двічі → ті самі записи outbox). Property (hypothesis): для будь-яких `now`, `settings`, `kind` результат `next_delivery` ≥ `now`, ≤ `now + 24 год` і не потрапляє в тихі години; для будь-якої послідовності лайків у вікні існує рівно один outbox з правильним `count`.

---

### S14-BE — рефералка (1.1)

**Домени.** `referrals`, `reactions`, `matching`.

**Ендпоінти.** `GET /referral`.

**Правила.** `referred_by_id` записується в S1. Після `complete` запрошеного — два записи `reaction_bonuses` (обом, `amount = REFERRAL_BONUS_REACTIONS`, `on_date` = сьогодні за Києвом, `source = referral`, `source_ref = <id запрошеного>`); унікальний індекс не дає подвійного бонусу. `invited_count` — запрошені зі статусом `active`. Буст у стрічці — поправка S7 протягом 48 год, тільки якщо пара проходить жорсткі фільтри (різні пули не бачать одне одного).

**Критерії приймання.** Повторне `complete` (після `reset`) не дає другого бонусу; запрошений у стрічці того, хто запросив, перший, якщо проходить фільтри.

**Тести.** Контракт `ReferralOut`; **ідемпотентність** нарахування; self-referral ігнорується.

---

### v2 (S15–S19)

Контракти заморожуються новою версією ядра на старті v2: питання дня (таблиці питань і відповідей, поле в картці), компанії за інтересами (підбір груп 3–5 людей за містом, пулом, інтересом і метою), події (зустрічі з радіусом 10 км і списком учасників, тільки свій пул), анонімний чат (ретрансляція через бота з фільтром контенту), монетизація (Telegram Stars, буст, безлімітне «Повернути»).
