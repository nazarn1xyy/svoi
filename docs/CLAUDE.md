# CLAUDE.md — «Свої»

@docs/tech.md

## Правила для кожної сесії

- `docs/tech.md` — єдине джерело істини (імпортовано вище). Підкоряйся йому дослівно.
- Перевір версію ядра в заголовку `docs/tech.md`. Задача посилається на старішу версію — перечитай changelog перед роботою.
- Контракти не вигадуй: схема БД, моделі API (`svoi_contracts`), енуми, топіки черги, примітиви UI, константи — тільки з ядра.
- Бракує контракту → СТОП. Видай блок `CONTRACT GAP` за розділом 16 `docs/tech.md`. Код з вигаданим типом не пиши. Продовжуй на локальній заглушці всередині своєї фічі або домену.
- Одна задача за раз, сфокусований дифф.
- Слайс повторює структуру еталонного слайса S1 (`apps/api/svoi_api/domains/{users,profiles}`, `apps/bot/svoi_bot/features/{start,onboarding}`).

## Визнач роль за назвою гілки (`git branch --show-current`)

- `lead/*` або `fe/*` → прочитай `docs/FRONTEND.md` і працюй за ним.
- `be/*` → прочитай `docs/BACKEND.md` і працюй за ним.
- `main` або інша назва → не пиши код. Попроси створити гілку `<lead|fe|be>/SVO-<n>-<slug>` під задачу Linear.

## Заборонено без рев'ю тимліда

`docs/`, `CLAUDE.md`, `packages/contracts/`, `apps/api/svoi_api/db/`, `apps/api/migrations/`, `apps/api/svoi_api/{core,clients,seed}/`, `apps/api/svoi_api/config.py`, `apps/bot/svoi_bot/{ui,api_client,middlewares}/`, `infra/`, `.github/`. Роль `be` міграцій не пише взагалі.

## Коміти, PR, коментарі

Англійською. Коміт: `type(scope): summary`, `type` ∈ `feat|fix|test|refactor|chore|docs`, імператив, з малої літери, без крапки, до ~50 символів. Комітить по ходу роботи маленькими кроками. PR: `SVO-<n> <scope>: <summary>`. Коментарі пояснюють «чому». Тести виводяться з критеріїв приймання, не з коду (розділ 11 `docs/tech.md`).

## Команди

- `uv sync` — залежності
- `docker compose -f infra/docker-compose.yml up -d postgres redis` — БД і Redis локально
- `uv run ruff check . && uv run ruff format --check .` — лінт
- `uv run mypy packages apps` — типи
- `uv run pytest apps/api` / `uv run pytest apps/bot` — тести
- `uv run alembic -c apps/api/alembic.ini upgrade head` — міграції (тільки тимлід генерує нові)
- `uv run python -m svoi_api.seed` — сид і фікстури
