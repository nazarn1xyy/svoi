# BACKEND.md — бекенд

Файл для сесії нейромережі бекендера. Ти пишеш API, бізнес-логіку, алгоритм підбору, безпеку, модерацію, фонові джоби. Бот, тексти й клавіатури пише фронтенд (тимлід).

Ядро: `docs/tech.md`, поточна версія **v4**.

---

## 0. Прочитай першим

- `docs/tech.md` — джерело істини. Підкоряйся йому дослівно. У Claude Code ядро підтягується через `CLAUDE.md` автоматично; в іншій сесії приклади `tech.md` до цього файлу.
- Перед задачею звір версію ядра в заголовку `tech.md` з версією, на яку посилається задача. Ядро новіше — перечитай changelog.
- Контракти не вигадуються: схема БД, моделі запитів і відповідей, енуми, топіки, payload, константи — тільки з `tech.md` і `svoi_contracts`.
- Одна задача за раз, сфокусований дифф.
- Твій слайс повторює структуру еталонного слайса S1-BE: `apps/api/svoi_api/domains/users` і `domains/profiles` (`router.py` → `service.py` → `repo.py`, чиста логіка в `rules.py`). Не вигадуй свою розкладку.

---

## 1. CONTRACT GAP

Бракує поля, таблиці, ендпоінта, енуму, константи, топіка → **СТОП**. Видай блок:

```
CONTRACT GAP
Core version: v1
Slice: S7-BE
Need: <що потрібно>
Why: <який критерій приймання без цього не виконати>
Proposed shape:
<pydantic-модель / SQLAlchemy-колонка / сигнатура>
Workaround until resolved: <локальна заглушка в межах твого домену>
```

Код з вигаданим типом не пиши. Відкрий issue з міткою `contract-change`, встав блок, продовжуй на заглушці всередині `domains/<твій домен>/`. Тимлід додасть контракт у `tech.md`, бампне версію, оновить `svoi_contracts`, моделі і міграцію. Після мерджу підтягни `main` і прибери заглушку.

---

## 2. Що тобі належить

- `apps/api/svoi_api/domains/*` — усі домени з розділу 3.3 `tech.md`: `router.py`, `service.py`, `repo.py`, `rules.py`, `jobs.py`;
- реєстрація хендлерів своїх джобів у `jobs/worker.py` (рядок у реєстрі, без зміни інфраструктури воркера);
- тести `apps/api/tests/domains/<domain>/`.

На етапі 0 за делегуванням тимліда (рев'ю тимліда обов'язкове, CODEOWNERS):

- B0.1 FastAPI app factory (`main.py`), `deps.py`: перевірка `Authorization: Bearer <INTERNAL_API_TOKEN>` (401), `current_user` за `X-Tg-User-Id` (404 для невідомого, 403 `banned`, оновлення `last_active_at` не частіше ніж раз на хвилину, ліниве зняття протермінованого бану з outbox `unbanned`), `admin_user` (`ADMIN_TG_IDS`, 403), `core/errors.py` (`DomainError` → `ApiError`, pydantic → 422 `validation_error`), `/health` (БД + Redis);
- B0.2 `core/queue.py`: `async def enqueue(job: JobBase, queue: Literal["api", "bot"]) -> None` з `_job_id=job.dedupe_key`; `jobs/worker.py` з демо-джобом і реєстром cron з розділу 8 `tech.md`;
- B0.3 `clients/`: `TelegramFilesClient`, `NsfwClassifier` (Protocol + реальна + фейк з `fail_next`, `timeout_next`), `ImageHasher`;
- B0.4 S1-BE (еталонний слайс бекенду, розділ 6).

## 3. Що НЕ чіпати

- `apps/api/svoi_api/db/models.py` і `apps/api/migrations/` — **міграцій не пишеш взагалі**. Потрібна колонка — `CONTRACT GAP`.
- `packages/contracts`, `docs/`, `seed/`, `infra/`, `.github/`, `config.py` — через тимліда.
- `apps/bot/*` — фронтенд. Там тільки рев'ю PR тимліда.
- Чужий домен напряму: домени спілкуються тільки через публічні функції `service`, перелічені в `domains/<domain>/__init__.py`.

---

## 4. Робочий цикл задачі

1. Задача Linear → гілка `be/SVO-<n>-<slug>`.
2. Коміти по ходу роботи, маленькі, англійською: `feat(matching): add hard filters query`. Формат з розділу 13 `tech.md`, кожен коміт за можливості проходить mypy.
3. PR: заголовок `SVO-<n> <domain>: <summary>`, тіло — що робить слайс, які ендпоінти й моделі контракту зачіпає (версія ядра), чим покрито тестами.
4. CI зелений → рев'ю тимліда → squash-merge → автодеплой на VPS.
5. Перевір ендпоінти на VPS через бота, коли фронтенд-частина слайса змерджена.

---

## 5. Тести на слайс

Доктрина з розділу 11 `tech.md`. Коротко для бекенду:

- **Тести з критеріїв приймання**, не з коду. Спершу перенеси кожен критерій задачі в назву тесту, потім пиши реалізацію.
- **Контрактні.** Відповідь кожного ендпоінта слайса валідується моделлю `svoi_contracts` (`Model.model_validate(response.json())`); кожен поставлений джоб — payload-моделлю з `jobs.py`. Хелпер `assert_contract(response, Model)` у `tests/conftest.py`.
- **Ідемпотентність.** Кожен хендлер джоба і кожен cron — запуск двічі з тим самим payload → рівно один ефект (один запис, одна зміна статусу, один outbox).
- **Шлях помилки.** Фейк клієнта повертає 500 і таймаут → джоб ретраїться або коректно падає, стан БД консистентний.
- **Property-based (hypothesis)** на всьому з `rules.py`: скоринг, фільтри, фільтр контенту, ліміти, корзини відстані, тихі години, вікна батчингу.
- Справжній Postgres з PostGIS, транзакція на тест з rollback; годинник через `core/time.now()` з фікстурою підміни.
- PR без тестів не проходить гейт. Якщо встановлено skill `engineering:testing-strategy` — фіксуй ним підхід у PR.

---

## 6. Бекенд-слайси

Формат задачі: ціль · домен · ендпоінти й моделі (розділ 7 `tech.md`) · правила · критерії приймання · тести. Константи — з `svoi_contracts.constants` (у тексті без префікса).

---

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

- **interests**: `Jw = Σidf(спільні) / Σidf(об'єднання)`; `C = |спільні категорії| / |об'єднання категорій|` (рахуються всі спільні категорії, і зі спільним тегом теж: інакше перетворення пари «одна категорія» на спільний тег знижувало б бал, а property нижче вимагає протилежного); `interests = Jw + CATEGORY_PARTIAL_MATCH · C · (1 − Jw)`.
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
