# CLAUDE.md — «Свої»

@docs/tech.md

## Правила для кожної сесії

- `docs/tech.md` — єдине джерело істини (імпортовано вище). Підкоряйся йому дослівно.
- Перевір версію ядра в заголовку `docs/tech.md`. Задача посилається на старішу версію — перечитай changelog перед роботою.
- Контракти не вигадуй: схема БД, моделі API (`svoi_contracts`), енуми, топіки черги, примітиви UI, константи — тільки з ядра.
- Бракує контракту → СТОП. Видай блок `CONTRACT GAP` за розділом 16 `docs/tech.md`. Код з вигаданим типом не пиши. Продовжуй на локальній заглушці всередині своєї фічі або домену.
- Одна задача за раз, сфокусований дифф.
- Слайс повторює структуру еталонного слайса S1 (`apps/api/svoi_api/domains/{users,profiles}`, `apps/bot/svoi_bot/features/{start,onboarding}`).

## Одна людина, одна роль

З 2026-11-09 в команді одна людина: тимлід пише і бот, і бекенд. Окремих ролей `fe`/`be` більше немає.

- Бот (`apps/bot`) → працюй за `docs/FRONTEND.md`.
- API (`apps/api`) → працюй за `docs/BACKEND.md`.
- Гілка: `lead/SVO-<n>-<slug>` (старі `fe/*` і `be/*` теж валідні). На `main` код не пиши.
- Контракти, моделі БД і міграції змінюй сам, але тільки разом з `docs/tech.md`: нова версія ядра і рядок у changelog. Правило «не вигадувати контракт» лишається: спершу ядро, потім код.
- PR мерджиться без апруву, коли CI зелений (branch protection вимагає тільки перевірки).

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
